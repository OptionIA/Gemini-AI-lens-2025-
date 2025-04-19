###########################
# IMPORTACIONES MODULARES
############################
import pyaudio
import sys

def list_audio_devices():
    """
    Lists all available audio input and output devices.
    Returns a tuple of (input_devices, output_devices).
    """
    p = pyaudio.PyAudio()
    input_devices = []
    output_devices = []
    
    # Iterate through all audio devices
    for i in range(p.get_device_count()):
        try:
            device_info = p.get_device_info_by_index(i)
            if device_info["maxInputChannels"] > 0:  # Input device
                input_devices.append(device_info)
            if device_info["maxOutputChannels"] > 0:  # Output device
                output_devices.append(device_info)
        except Exception as e:
            print(f"Error getting device info for index {i}: {e}")
    
    p.terminate()
    return input_devices, output_devices

def find_headset_devices():
    """
    Attempts to find headset devices among available audio devices.
    Returns a tuple of (input_device_index, output_device_index).
    Prioritizes devices with "headset", "headphone", "auricular" in their names.
    """
    input_devices, output_devices = list_audio_devices()
    
    # Keywords to look for in device names
    keywords = ["headset", "headphone", "auricular", "microphone", "micrófono"]
    
    # Find input device (microphone)
    input_device = None
    for device in input_devices:
        device_name = device["name"].lower()
        if any(keyword in device_name for keyword in keywords):
            input_device = device
            break
    
    # If no headset input found, use first available input device
    if not input_device and input_devices:
        input_device = input_devices[0]
    
    # Find output device (speakers/headphones)
    output_device = None
    for device in output_devices:
        device_name = device["name"].lower()
        if any(keyword in device_name for keyword in keywords):
            output_device = device
            break
    
    # If no headset output found, use first available output device
    if not output_device and output_devices:
        output_device = output_devices[0]
    
    return (
        input_device["index"] if input_device else None,
        output_device["index"] if output_device else None
    )

def print_audio_devices():
    """
    Prints all available audio devices for debugging purposes.
    """
    p = pyaudio.PyAudio()
    print("\nAvailable Audio Devices:")
    print("-" * 60)
    
    for i in range(p.get_device_count()):
        try:
            device_info = p.get_device_info_by_index(i)
            print(f"\nDevice {i}:")
            print(f"Name: {device_info['name']}")
            print(f"Input channels: {device_info['maxInputChannels']}")
            print(f"Output channels: {device_info['maxOutputChannels']}")
            print(f"Default Sample Rate: {device_info['defaultSampleRate']}")
        except Exception as e:
            print(f"Error getting device info for index {i}: {e}")
    
    p.terminate()
    print("-" * 60)