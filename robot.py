import os
import time
import platform
import ctypes
from ctypes import *

# Determine the current working directory
current_dir = os.getcwd()

# Determine the platform and set the appropriate library name
platform_system = platform.system()
if platform_system == "Windows":
    lib_name = "librisdk.dll"
elif platform_system == "Linux":
    lib_name = "librisdk.so"
else:
    raise OSError("Unsupported operating system")

# Construct the full path to the library
lib_path = os.path.join(current_dir, lib_name)

# Load the library
try:
    lib = ctypes.CDLL(lib_path)
    print(f"Successfully loaded library from: {lib_path}")
except OSError as e:
    print(f"Error loading the library: {e}")
    print(f"Attempted to load from: {lib_path}")
    raise


# In[ ]:



# Define necessary constants
MIN_PULSE = 375
MAX_PULSE = 2500
SERVO_COUNT = 7
MIN_ANGLE = 0
MAX_ANGLE = 180

# Initialize the SDK
def init_sdk():
    errTextC = create_string_buffer(1000)
    errCode = lib.RI_SDK_InitSDK(2, errTextC)
    if errCode != 0:
        raise Exception(f"Failed to initialize SDK: {errTextC.value.decode()}")

# Create and initialize components
def init_components():
    errTextC = create_string_buffer(1000)
    
    # Create PWM
    pwm = c_int()
    errCode = lib.RI_SDK_CreateModelComponent("connector".encode(), "pwm".encode(), "pca9685".encode(), byref(pwm), errTextC)
    if errCode != 0:
        raise Exception(f"Failed to create PWM: {errTextC.value.decode()}")
    
    # Create I2C
    i2c = c_int()
    errCode = lib.RI_SDK_CreateModelComponent("connector".encode(), "i2c_adapter".encode(), "ch341".encode(), byref(i2c), errTextC)
    if errCode != 0:
        raise Exception(f"Failed to create I2C: {errTextC.value.decode()}")
    
    # Link PWM to I2C
    errCode = lib.RI_SDK_LinkPWMToController(pwm, i2c, c_uint8(0x40), errTextC)
    if errCode != 0:
        raise Exception(f"Failed to link PWM to I2C: {errTextC.value.decode()}")
    
    # Create and link servos
    servos = []
    for i in range(SERVO_COUNT):
        servo = c_int()
        errCode = lib.RI_SDK_CreateModelComponent("executor".encode(), "servodrive".encode(), "mg90s".encode(), byref(servo), errTextC)
        if errCode != 0:
            raise Exception(f"Failed to create servo {i}: {errTextC.value.decode()}")
        
        errCode = lib.RI_SDK_LinkServodriveToController(servo, pwm, i, errTextC)
        if errCode != 0:
            raise Exception(f"Failed to link servo {i}: {errTextC.value.decode()}")
        
        servos.append(servo)
    
    return servos

positions = {}

# Move a servo to a specific position
def move_servo(servo, position):
    errTextC = create_string_buffer(1000)
    safe_position = max(MIN_PULSE, min(MAX_PULSE, position))
    errCode = lib.RI_SDK_exec_ServoDrive_TurnByPulse(servo, safe_position, errTextC)
    if errCode != 0:
        raise Exception(f"Failed to move servo: {errTextC.value.decode()}")
    positions[servo.value] = position

def move_servo_slow(servo, position):
    if position > positions[servo.value]:
        for i in range(positions[servo.value], position, 1):
            move_servo(servo, i)
            time.sleep(0.01)
        move_servo(servo, position)
    elif position < positions[servo.value]:
        for i in range(positions[servo.value], position, -1):
            move_servo(servo, i)
            time.sleep(0.01)
        move_servo(servo, position)

# Move a servo to a specific position with speed control
def move_servo_speed(servo, pulse, speed):
    errTextC = create_string_buffer(1000)
    angle = pulse_to_angle(pulse)
    safe_angle = max(MIN_ANGLE, min(MAX_ANGLE, angle))
    errCode = lib.RI_SDK_exec_ServoDrive_Turn(servo, int(safe_angle), speed, c_bool(False), errTextC)
    if errCode != 0:
        raise Exception(f"Failed to move servo: {errTextC.value.decode()}")

# Convert pulse to angle
def pulse_to_angle(pulse):
    return (pulse - MIN_PULSE) / ((MAX_PULSE - MIN_PULSE) / 180) - 90


# Main function
def main():
    init_sdk()
    servos = init_components()
    
    # Set all servos to initial position
    for servo in servos:
        move_servo(servo, 1500)
        positions[servo.value] = 1500
    
    # Example: Move servo 3 to position 1500
    move_servo(servos[3], 1500)
    
    # Clean up (you might want to add proper cleanup code here)


# In[ ]:


def move_two_servos_sync(servos, r0, r1, r2):
    """
    Move servo 1 and 2 simultaneously, completing movement at the same time.
    
    Args:
        servos: List of servo objects
        r1: Target position for servo 1 (float)
        r2: Target position for servo 2 (float)
    """
    # Get current positions
    start1 = positions[servos[1].value]
    start2 = positions[servos[2].value]
    
    # Calculate distances to move
    dist1 = abs(r1 - start1)
    dist2 = abs(r2 - start2)

    if r1 <= start1:
        move_servo_slow(servos[0], r0)
        
    # Find which movement is larger to determine number of steps
    max_dist = max(dist1, dist2)
    
    if max_dist != 0:    
        # Calculate step sizes for each servo to ensure synchronized completion
        step1 = (r1 - start1) / max_dist
        step2 = (r2 - start2) / max_dist
        
        # Move servos step by step
        for i in range(int(max_dist)):
            new_pos1 = start1 + step1 * i
            new_pos2 = start2 + step2 * i
            
            # Move both servos
            move_servo(servos[1], int(new_pos1))
            move_servo(servos[2], int(new_pos2))
            
            # Use same delay as move_servo_slow
            time.sleep(0.01)
        
        # Final movement to ensure target positions are exactly reached
        move_servo(servos[1], int(r1))
        move_servo(servos[2], int(r2))
    if r1 > start1:
        move_servo_slow(servos[0], r0)

    

def execute_move_command(r):
    move_two_servos_sync(servos, r[0], r[1], r[2])
    move_servo_slow(servos[6], r[6])


grid_positions = {
    'red': {
        'up': [1200, 1825, 1600],
        'down': [1200, 1625, 1850]
    },
    'green': {
        'up': [1450, 1825, 1600],
        'down': [1450, 1625, 1850]
    },
    'blue': {  
        'up': [1700, 1825, 1600],
        'down': [1700, 1625, 1850]
    },
    'yellow': {  # middle row, left
        'up': [1200, 1900, 1750],
        'down': [1200, 1750, 2000]
    },
    'cyan': {  # middle row, center
        'up': [1450, 1900, 1750],
        'down': [1450, 1750, 2000]
    },
    'magenta': {  # middle row, right
        'up': [1700, 1900, 1750],
        'down': [1700, 1750, 2000]
    },
    'black': {  # back row, left
        'up': [1300, 2000, 1900],
        'down': [1300, 1850, 2125]
    },
    'white': {  # back row, center
        'up': [1450, 2000, 1900],
        'down': [1450, 1850, 2125]
    },
    'orange': {  # back row, right
        'up': [1700, 2000, 1900],
        'down': [1650, 1850, 2125]
    }
}

def execute_string_command(target_arm_position, target_arm_height, gripper):
    if target_arm_height == "raised":
        r = grid_positions[target_arm_position]['up']
    elif target_arm_height == "lowered":
        r = grid_positions[target_arm_position]['down']
    else:
        raise Exception(f"Wrong target_arm_height: {target_arm_height}")
    gripper_pos = 1650
    if gripper == "close" or gripper == "hold":
        gripper_pos = 1950
    move_two_servos_sync(servos, r[0], r[1], r[2])
    move_servo_slow(servos[6], gripper_pos)
