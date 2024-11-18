import numpy as np
import torch
import pyaudio
import threading
import traceback
import time
from queue import Queue, Empty as QueueEmpty
from dataclasses import dataclass
from scipy.io.wavfile import write

@dataclass
class VoiceCommand:
    text: str
    speed: float = 1.25

class VoiceActivityDetection:
    def __init__(self, sampling_rate=16000):
        print("Initializing VAD...")
        self.model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad"
        )
        self.model.eval()  # Ensure model is in evaluation mode
        
        (
            self.get_speech_timestamps,
            self.save_audio,
            self.read_audio,
            self.VADIterator,
            self.collect_chunks,
        ) = utils
        
        self.sampling_rate = sampling_rate
        print(f"VAD initialized with sampling rate: {sampling_rate}")
        
    def contains_speech(self, audio_chunk):
        try:
            # Convert the audio chunk to the correct format and normalize
            frames = np.frombuffer(audio_chunk, dtype=np.float32)
            
            # Print debug information about the audio chunk
            #print(f"Audio chunk stats - Min: {frames.min():.3f}, Max: {frames.max():.3f}, Mean: {frames.mean():.3f}")
            
            # Check if audio is too quiet
            if np.abs(frames).max() < 0.01:
            #    print("Warning: Audio input is very quiet!")
                return False
            
            # Ensure correct shape and type
            frames = frames.astype(np.float32)
            if len(frames.shape) == 2:
                frames = frames.flatten()
                
            # Convert to torch tensor
            audio = torch.tensor(frames)
            
            # Print tensor information
            #print(f"Tensor shape: {audio.shape}, dtype: {audio.dtype}")
            
            # Get speech timestamps
            speech_timestamps = self.get_speech_timestamps(
                audio,
                self.model,
                sampling_rate=self.sampling_rate,
                threshold=0.25,  # Adjust this threshold if needed (0.0-1.0)
                min_speech_duration_ms=100,  # Minimum speech chunk duration in milliseconds
                min_silence_duration_ms=100  # Minimum silence duration between words
            )
            
            #print(f"Speech timestamps detected: {len(speech_timestamps)}")
            return len(speech_timestamps) > 0
            
        except Exception as e:
            print(f"Error in VAD processing: {e}")
            traceback.print_exc()
            return False

class WhisperCommandQueue:
    def __init__(self, tts_queue, silence_threshold=5):
        self.queue = Queue()
        self.is_running = True
        self.silence_threshold = silence_threshold
        self.tts_queue = tts_queue
        self.vad = VoiceActivityDetection()
        self.sample_rate = 16000
        self.chunk_size = 2048
        self.is_paused = False  # New flag for pause state
        self.pause_lock = threading.Lock()  # Lock for thread-safe pause state management
       
        
        # Initialize PyAudio stream
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        # Start the worker thread
        self.worker_thread = threading.Thread(target=self._process_audio_stream)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        print("Listening...")
    
    def pause(self):
        """Pause the command queue processing"""
        with self.pause_lock:
            self.is_paused = True
            print("Command queue paused")
    
    def resume(self):
        """Resume the command queue processing"""
        with self.pause_lock:
            self.is_paused = False
            print("Command queue resumed")
    
    def toggle_pause(self):
        """Toggle the pause state"""
        with self.pause_lock:
            self.is_paused = not self.is_paused
            print(f"Command queue {'paused' if self.is_paused else 'resumed'}")
    
    def get_command(self, timeout=None):
        """Get the next command from the queue"""
        try:
            return self.queue.get(timeout=timeout)
        except QueueEmpty:
            return None
    
    def _process_audio_stream(self):
        recording = False
        silence_duration = 0
        audio_data = np.empty((0, 1), dtype=np.float32)
        
        while self.is_running:
            with self.pause_lock:
                if self.is_paused:
                    time.sleep(0.1)  # Sleep briefly when paused to reduce CPU usage
                    continue
                    
            if hasattr(self.tts_queue, 'is_speaking') and self.tts_queue.is_speaking:
                time.sleep(0.5)
                continue
            
            try:
                # Read from stream
                audio_chunk = np.frombuffer(
                    self.stream.read(self.chunk_size, exception_on_overflow=False),
                    dtype=np.float32
                ).reshape(-1, 1)
                
                # Convert audio chunk to bytes for VAD
                audio_bytes = audio_chunk.astype(np.float32).tobytes()
                
                is_speech = self.vad.contains_speech(audio_bytes)
                
                # State machine for recording
                if not recording and is_speech:
                    recording = True
                    audio_data = audio_chunk
                    silence_duration = 0
                    print("Speech detected, started recording")
                elif recording:
                    audio_data = np.concatenate((audio_data, audio_chunk))
                    
                    if not is_speech:
                        silence_duration += 1
                        if silence_duration > 16:
                            if len(audio_data) > self.chunk_size * 3:  # Minimum length
                                self._process_audio_segment(audio_data)
                            recording = False
                            audio_data = np.empty((0, 1), dtype=np.float32)
                        
            except Exception as e:
                traceback.print_exc()
                print(f"Error in audio processing: {e}")
                time.sleep(0.1)
                continue
    
    def _process_audio_segment(self, audio_data):
        try:
            # Create an audio segment in-memory with appropriate settings
            raw_filename = "raw.wav"
            write(raw_filename, self.sample_rate, audio_data)

            audio_file = open( "raw.wav", "rb")
            
            # Send the audio file to OpenAI's Whisper API for transcription
            transcription = openai_client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                language="ru"
            )
            print(transcription)
    
            # Extract transcribed text from the response
            transcribed_text = transcription.text.strip()
    
            # Print the detected command if valid
            if transcribed_text and len(transcribed_text) > 3:
                print(f"Detected command: {transcribed_text}")
                self.queue.put(VoiceCommand(text=transcribed_text, speed=1.2))
    
        except Exception as e:
            traceback.print_exc()
            print(f"Error processing audio segment: {e}")

    
    def stop(self):
        """Safely stop the command queue"""
        self.is_running = False
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'p') and self.p:
            self.p.terminate()
        if hasattr(self, 'worker_thread') and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)