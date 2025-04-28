import asyncio
import time
import datetime
import sys
import pyaudio
from google import genai
from google.genai import types
from funciones.basic_def import (
    get_key, save_context, get_combined_instructions, get_actual_voice,
    write_voice_text, delayed_reconnect, reset_status_to_reconnect, get_voice_descriptions
)
from funciones.audio_def import (
    FORMAT, CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE,
    setup_audio_input, setup_audio_output, listen_audio, play_audio
)
from funciones.video_def import (
    setup_video_capture, capture_frames, release_capture
)
from funciones.pya_def import print_audio_devices, find_headset_devices
from funciones.config import LOGGING_ENABLED
import json
import os

# Silently get audio devices
input_idx, output_idx = find_headset_devices()

# Variables globales
GOOGLE_API_KEY = get_key()
MODEL = "models/gemini-2.0-flash-live-001"
def get_combined_instructions_by_mode():
    config_path = os.path.join("data", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        current_mode = config.get("current_mode", "conversacional")
    except Exception:
        current_mode = "conversacional"
    # Map modes to their corresponding instruction files
    mode_to_file = {
        "lentes_ai": "lentes_ai.txt",
        "conversacional": "conversacional.txt",
        "agente_psicologo": "agente_psicologo.txt"
    }
    instructions_file = os.path.join("data", mode_to_file.get(current_mode, "conversacional.txt"))
    try:
        with open(instructions_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""
COMBINED_INSTRUCTIONS = get_combined_instructions_by_mode()
ACTUAL_VOICE = get_actual_voice()

# Configuracion de tools usando el sistema nativo de búsqueda de Google
TOOLS = [
    types.Tool(google_search=types.GoogleSearch()),
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="print_yes",
                description="Guarda el contexto de la conversacion, para conversaciones futuras.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="En este va todo el resumen de la conversacion"
                        )
                    },
                    required=["query"]
                )
            ),
            types.FunctionDeclaration(
                name="change_voice",
                description="Cambia la voz de Jarvis a una de las voces disponibles.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "voice_number": types.Schema(
                            type=types.Type.INTEGER,
                            description="Número de voz a usar (1-8):\n1: Puck (joven y enérgica)\n2: Charon (profunda y seria)\n3: Kore (suave y melodiosa)\n4: Fenrir (poderosa)\n5: Aoede (madura y elegante)\n6: Leda (joven y dulce)\n7: Orus (cálida y amigable)\n8: Zephyr (juvenil y dinámica)"
                        )
                    },
                    required=["voice_number"]
                )
            ),
            types.FunctionDeclaration(
                name="force_reconnect",
                description="Fuerza una reconexión inmediata del sistema.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                    required=[]
                )
            )
        ]
    )
]

# Configuracion de seguridad para el modelo de IA
SAFETY_SETTINGS = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
]

# Inicializacion del cliente de Google Generative AI
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={"api_version": "v1alpha"})

# Configuracion para la generacion de contenido
config = types.LiveConnectConfig(
    generation_config=types.GenerationConfig(
        temperature=0.7,
        top_p=0.9,
        top_k=40,
        candidate_count=1,
        stop_sequences=[],
        max_output_tokens=2048
    ),
    response_modalities=["audio"],
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=ACTUAL_VOICE)
        )
    ),
    tools=TOOLS,
    system_instruction=types.Content(
        parts=[types.Part.from_text(text=COMBINED_INSTRUCTIONS)],
        role="user"
    )
)

# Inicializacion de PyAudio
pya = pyaudio.PyAudio()

class AudioLoop:
    def __init__(self):
        self.audio_in_queue = asyncio.Queue(maxsize=100)
        self.out_queue = asyncio.Queue(maxsize=20)
        self.session = None
        self.audio_stream = None
        self.video_capture = None
        self.data_counter = 0
        self._audio_buffer = bytearray()
        self.last_send_timestamp = None
        self.ping_ms = None
        self.connection_active = True
        self.interaction_count = 0
        self.last_instructions_refresh = time.time()
        self.refresh_instructions_interval = 10

    async def send_text(self):
        while True:
            try:
                text = await asyncio.to_thread(
                    input,
                    "message > ",
                )
                if text.lower() == "q":
                    # Write reconnect to status.txt and break
                    with open("data/status.txt", "w") as f:
                        f.write("reconnect")
                    break
                
                self.last_send_timestamp = time.time()
                await self.session.send(input=text or ".", end_of_turn=True)
            except:
                break

    _history_write_buffer = []
    _last_history_write = 0
    _history_write_interval = 5
    
    async def _flush_history_buffer(self):
        if not AudioLoop._history_write_buffer:
            return
            
        try:
            save_context("".join(AudioLoop._history_write_buffer))
            AudioLoop._history_write_buffer.clear()
            AudioLoop._last_history_write = datetime.datetime.now().timestamp()
        except Exception as e:
            if LOGGING_ENABLED:
                print(f"Error escribiendo buffer de historial: {e}")
    
    async def send_realtime(self):
        last_send_time = 0
        min_send_interval = 0.00005
        
        while True:
            try:
                msg = await self.out_queue.get()
                
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - last_send_time
                if time_since_last < min_send_interval:
                    await asyncio.sleep(min_send_interval - time_since_last)
                
                self.last_send_timestamp = time.time()
                await self.session.send(input=msg)
                last_send_time = asyncio.get_event_loop().time()
                self.out_queue.task_done()
            except:
                await asyncio.sleep(0.1)

    async def listen_audio(self):
        """Inicializa y gestiona la entrada de audio usando las funciones modularizadas."""
        self.audio_stream = await setup_audio_input(pya, self.out_queue)
        await listen_audio(self.audio_stream, self.out_queue)

    async def play_audio(self):
        """Inicializa y gestiona la salida de audio usando las funciones modularizadas."""
        stream = await setup_audio_output(pya)
        await play_audio(stream, self.audio_in_queue)

    async def get_frames(self):
        """Inicializa y gestiona la captura de video usando las funciones modularizadas."""
        try:
            self.video_capture = await setup_video_capture()
            await capture_frames(self.video_capture, self.out_queue)
        except Exception as e:
            if LOGGING_ENABLED:
                print(f"\n[ERROR] Error en captura de video: {str(e)}")
        finally:
            release_capture(self.video_capture)

    async def _handle_function_call(self, func_call):
        """Maneja las llamadas a funciones del modelo"""
        args_dict = func_call.args
        
        if func_call.name == "print_yes":
            result_string = args_dict.get("query")
            if result_string:
                save_context(result_string)
                return {"result": "ok"}
                
        elif func_call.name == "change_voice":
            voice_number = args_dict.get("voice_number")
            if voice_number and 1 <= voice_number <= 8:
                write_voice_text(voice_number)
                voice_info = get_voice_descriptions()[voice_number]
                await self.session.send(input=f"Cambiaré mi voz a {voice_info['name']} ({voice_info['description']}). La nueva voz estará activa en 15 segundos.")
                delayed_reconnect(15)
                return {"result": "ok"}
                
        elif func_call.name == "force_reconnect":
            await self.session.send(input="Iniciando reconexión inmediata...")
            reset_status_to_reconnect()
            return {"result": "ok"}
        
        return {"error": "Invalid function call"}

    async def receive_audio(self):
        while True:
            try:
                turn = self.session.receive()
                full_text = ""
                tool_call_detected = False
                first_response_received = False
                
                async for response in turn:
                    if not first_response_received and self.last_send_timestamp is not None:
                        first_response_received = True
                        current_time = time.time()
                        self.ping_ms = round((current_time - self.last_send_timestamp) * 1000)
                        if LOGGING_ENABLED:
                            print(f"\n[Ping: {self.ping_ms}ms]")

                    # Manejo de function calls
                    if hasattr(response, "tool_call") and response.tool_call is not None:
                        tool_call_detected = True
                        for func_call in response.tool_call.function_calls:
                            result = await self._handle_function_call(func_call)
                            
                            # Crear respuesta de la función
                            tool_response = types.LiveClientToolResponse(
                                function_responses=[
                                    types.FunctionResponse(
                                        name=func_call.name,
                                        response=result,
                                        id=getattr(func_call, "id", "default_id")
                                    )
                                ]
                            )
                            
                            # Enviar la respuesta
                            await self.session.send(input=tool_response)

                    # Procesar audio y texto
                    if data := response.data:
                        await self.audio_in_queue.put(data)
                        continue
                    if text := response.text:
                        full_text += text
                        print(text, end="")
                print()
            except:
                break

    async def run(self):
        self.connection_active = True
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=config) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session
                self.connection_active = True

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                async def task_wrapper(coro, task_name):
                    try:
                        await coro
                    except asyncio.CancelledError:
                        if LOGGING_ENABLED:
                            print(f"\n[SYS] Tarea {task_name} cancelada")
                        with open("data/status.txt", "w") as f:
                            f.write("reconnect")
                        raise
                    except Exception as e:
                        if LOGGING_ENABLED:
                            print(f"\n[ERROR] Error en tarea {task_name}: {str(e)}")
                        self.connection_active = False
                        with open("data/status.txt", "w") as f:
                            f.write("reconnect")
                        raise asyncio.CancelledError()

                # Create tasks in a more structured way
                task_definitions = [
                    ("send_text", self.send_text()),
                    ("send_realtime", self.send_realtime()),
                    ("listen_audio", self.listen_audio()),
                    ("get_frames", self.get_frames()),
                    ("receive_audio", self.receive_audio()),
                    ("play_audio", self.play_audio())
                ]

                try:
                    tasks = []
                    for task_name, coro in task_definitions:
                        task = tg.create_task(task_wrapper(coro, task_name), name=task_name)
                        if task_name == "send_text":
                            send_text_task = task
                        tasks.append(task)

                    # Wait for send_text task while keeping others running
                    await send_text_task

                except* Exception as exc:
                    if LOGGING_ENABLED:
                        print(f"\n[ERROR] Error en las tareas: {exc}")
                    raise
                finally:
                    # Cancel all remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    
                    # Wait for all tasks to complete their cleanup
                    await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            if LOGGING_ENABLED:
                print(f"\n[ERROR] Error en AudioLoop.run: {str(e)}")
        finally:
            self.connection_active = False
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                try:
                    self.audio_stream.close()
                except Exception as e:
                    if LOGGING_ENABLED:
                        print(f"\n[ERROR] Error cerrando audio_stream: {str(e)}")
            if hasattr(self, 'video_capture') and self.video_capture is not None:
                release_capture(self.video_capture)
            sys.exit(0)

if __name__ == "__main__":
    try:
        main = AudioLoop()
        asyncio.run(main.run())
    except KeyboardInterrupt:
        sys.exit(0)
    finally:
        pya.terminate()
