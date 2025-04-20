#################################
# IMPORTACIONES MODULARES
##################################
import asyncio
import pyaudio
import audioop
import time
from .pya_def import find_headset_devices
from .config import LOGGING_ENABLED

############################################
# CONSTANTES DE AUDIO
############################################
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 2048

############################################
# FUNCIONES AUDIO
############################################

async def setup_audio_input(pya, queue):
    """Configura y maneja la entrada de audio usando el dispositivo de entrada preferido."""
    input_device_index, _ = find_headset_devices()
    
    if input_device_index is None:
        if LOGGING_ENABLED:
            print("Warning: No suitable input device found.")
        raise RuntimeError("No suitable audio input device found")

    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=input_device_index,
        frames_per_buffer=CHUNK_SIZE,
    )
    return audio_stream

async def setup_audio_output(pya):
    """Configura y retorna el stream de salida de audio usando el dispositivo de salida preferido."""
    _, output_device_index = find_headset_devices()
    
    if output_device_index is None:
        if LOGGING_ENABLED:
            print("Warning: No suitable output device found.")
        raise RuntimeError("No suitable audio output device found")

    return await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE,
        output=True,
        output_device_index=output_device_index,
    )

async def listen_audio(audio_stream, out_queue):
    """Escucha el audio del micrófono y lo envía a la cola de salida."""
    kwargs = {"exception_on_overflow": False}
    while True:
        data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, **kwargs)
        
        if CHANNELS != 1:
            data = audioop.tomono(data, 2, 1, 1)
        
        await out_queue.put({"data": data, "mime_type": "audio/pcm"})

async def play_audio(stream, audio_in_queue):
    """Reproduce el audio recibido."""
    while True:
        bytestream = await audio_in_queue.get()
        await asyncio.to_thread(stream.write, bytestream)

