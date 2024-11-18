import io
import base64
import urllib.parse
from PIL import Image


def image_to_uri(image):
    # Convert the numpy array to an Image object
    image = Image.fromarray(image)

    #image = image.resize((512, 512))
    
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    img_uri = f"{img_str}"
    return img_uri


def encode_credentials(username, password):
    encoded_username = urllib.parse.quote(username)
    encoded_password = urllib.parse.quote(password)
    return encoded_username, encoded_password
