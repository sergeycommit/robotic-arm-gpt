import cv2
import time
from vidgear.gears import CamGear
from PIL import Image

class WebcamCapture:
    def __init__(self, camera_index=1):
        self.camera_index = camera_index
        self.cap = cv2.VideoCapture(camera_index)
        
        # Best supported video resolution based on testing
        self.width = 1024
        self.height = 768
        
        # Apply base settings
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # Disable autofocus
        self.cap.set(cv2.CAP_PROP_FOCUS, 100)    # Set initial focus
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)  # Disable auto exposure
        self.cap.set(cv2.CAP_PROP_EXPOSURE, -6)  # Set initial exposure
        self.cap.set(cv2.CAP_PROP_BRIGHTNESS, 128)
        self.cap.set(cv2.CAP_PROP_CONTRAST, 128)
        self.cap.set(cv2.CAP_PROP_SHARPNESS, 128)
        
        # Initialize video stream
        self.setup_stream()
        
    def setup_stream(self):
        """Setup camera for video streaming"""
        if hasattr(self, 'stream'):
            self.stream.stop()
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        
        options = {
            "CAP_PROP_FRAME_WIDTH": self.width,
            "CAP_PROP_FRAME_HEIGHT": self.height,
            "CAP_PROP_BUFFERSIZE": 1
        }
        self.stream = CamGear(source=self.camera_index, logging=True, **options).start()
        
        # Warm-up
        print("Warming up camera...")
        for _ in range(5):
            self.stream.read()
    
    def get_video_frame(self):
        """Capture a frame"""
        if not hasattr(self, 'stream'):
            self.setup_stream()
            
        start_time = time.time()
        frame = self.stream.read()
        capture_time = time.time() - start_time
        
        if frame is None:
            raise IOError("Failed to capture frame")
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_frame)
        
        print(f"Frame capture time: {capture_time:.4f} seconds")
        print(f"Frame size: {pil_image.size}")
        return pil_image
    
    def adjust_focus(self, focus_value):
        """Adjust the focus of the camera (0-255)"""
        self.cap.set(cv2.CAP_PROP_FOCUS, focus_value)
        
    def adjust_exposure(self, exposure_value):
        """Adjust the exposure of the camera (-13 to 0)"""
        self.cap.set(cv2.CAP_PROP_EXPOSURE, exposure_value)
        
    def adjust_sharpness(self, sharpness_value):
        """Adjust the sharpness of the camera (0-255)"""
        self.cap.set(cv2.CAP_PROP_SHARPNESS, sharpness_value)
    
    def get_current_settings(self):
        """Get current camera settings"""
        settings = {
            "focus": self.cap.get(cv2.CAP_PROP_FOCUS),
            "exposure": self.cap.get(cv2.CAP_PROP_EXPOSURE),
            "brightness": self.cap.get(cv2.CAP_PROP_BRIGHTNESS),
            "contrast": self.cap.get(cv2.CAP_PROP_CONTRAST),
            "sharpness": self.cap.get(cv2.CAP_PROP_SHARPNESS),
            "current_width": self.cap.get(cv2.CAP_PROP_FRAME_WIDTH),
            "current_height": self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        }
        return settings
    
    def close(self):
        """Clean up resources"""
        if hasattr(self, 'stream'):
            self.stream.stop()
        self.cap.release()
