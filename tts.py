import os
import threading
import tempfile
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from queue import Queue, Empty as QueueEmpty
from threading import Lock
from dataclasses import dataclass
from typing import Optional

@dataclass
class TTSRequest:
    text: str
    speed: float = 1.0
    voice: str = 'alloy'  # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer

class OpenAITTSQueue:
    def __init__(self, client = None):
        """Initialize the TTS queue system using OpenAI's API"""
        self.queue = Queue()
        self.is_running = True
        self.speaking_lock = Lock()
        self.is_speaking = False
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize OpenAI client
        self.client = client
        
        # Start worker thread
        self._initialize_worker()

    def _initialize_worker(self):
        """Initialize the worker thread that processes the queue"""
        self.worker_thread = threading.Thread(target=self._process_queue)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def _process_queue(self):
        """Process items in the queue"""
        while self.is_running:
            try:
                request = self.queue.get(timeout=1.0)
                self.set_speaking(True)
                print("Speaking...")
                self._process_tts_request(request)
                self.queue.task_done()
                self.set_speaking(False)
                print("Finished speaking.")
            except QueueEmpty:
                continue
            except Exception as e:
                print(f"Error processing TTS request: {str(e)}")
                self.set_speaking(False)

    def _process_tts_request(self, request: TTSRequest):
        """Process a single TTS request"""
        try:
            # Create temporary file path for the audio
            temp_file = Path(self.temp_dir) / f"speech_{threading.get_ident()}.mp3"
            
            # Generate speech using OpenAI API
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=request.voice,
                input=request.text
            )
            
            # Save to temporary file
            response.stream_to_file(temp_file)
            
            # Read and play the audio
            data, samplerate = sf.read(temp_file)
            
            # Apply speed adjustment if needed
            if request.speed != 1.0:
                # Adjust sample rate to change speed
                adjusted_samplerate = int(samplerate * request.speed)
                sd.play(data, adjusted_samplerate)
                sd.wait()
            else:
                sd.play(data, samplerate)
                sd.wait()
            
            # Clean up temporary file
            os.remove(temp_file)
            
        except Exception as e:
            print(f"Error in TTS processing: {str(e)}")
            print(request)
            raise

    def add_text(self, text: str, speed: float = 1.0, voice: str = 'alloy'):
        """Add text to the TTS queue"""
        request = TTSRequest(text=text, speed=speed, voice=voice)
        self.queue.put(request)

    def get_queue_size(self) -> int:
        """Get the current size of the queue"""
        return self.queue.qsize()

    def clear_queue(self):
        """Clear all pending items from the queue"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except QueueEmpty:
                break

    def stop(self):
        """Stop the TTS system and clean up"""
        self.is_running = False
        sd.stop()
        self.clear_queue()
        if self.worker_thread.is_alive():
            self.worker_thread.join()
        
        # Clean up temp directory
        try:
            os.rmdir(self.temp_dir)
        except:
            pass

    def set_speaking(self, state: bool):
        """Set the speaking state"""
        with self.speaking_lock:
            self.is_speaking = state

    def is_busy(self) -> bool:
        """Check if the TTS system is currently busy (speaking or has items in queue)"""
        with self.speaking_lock:
            return self.is_speaking or not self.queue.empty()

    def wait_until_done(self, check_interval: float = 0.1):
        """
        Wait until all speech is finished and the queue is empty.
        
        Args:
            check_interval (float): How often to check the status in seconds
        """
        while self.is_busy():
            time.sleep(check_interval)
