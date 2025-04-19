#################################
# IMPORTACIONES MODULARES
##################################
import asyncio
import pyaudio
import audioop
import time

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
    """Configura y maneja la entrada de audio."""
    mic_info = pya.get_default_input_device_info()
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )
    return audio_stream

async def setup_audio_output(pya):
    """Configura y retorna el stream de salida de audio."""
    return await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=RECEIVE_SAMPLE_RATE,
        output=True,
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

