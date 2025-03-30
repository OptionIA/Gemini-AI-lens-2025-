import asyncio
import base64
import io
import os
import sys
import traceback
import json
import datetime
import time
import cv2
import pyaudio
import PIL.Image
import audioop
import argparse
import random
from google import genai
from google.genai.types import (
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold
)

#####################################################
# BASIC SETTINGS STUFF
#####################################################

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 2048

#####################################################
# SISTEMA DE INFORMACION USUARIO
#####################################################

try:
    with open("api.txt", "r") as f:
        api_keys = [key.strip() for key in f.readlines() if key.strip()]
    GOOGLE_API_KEY = random.choice(api_keys) if api_keys else ""
    if not GOOGLE_API_KEY:
        raise ValueError("No valid API key found in api.txt")
except FileNotFoundError:
    print("Warning: api.txt file not found. Please create it with your API keys.")
    GOOGLE_API_KEY = ""
except ValueError as e:
    print(f"Error: {e}")
    GOOGLE_API_KEY = ""
except Exception as e:
    print(f"Error reading API keys: {e}")
    GOOGLE_API_KEY = ""

MODEL = "models/gemini-2.0-flash-exp"

now_time = datetime.datetime.now()
formatted_time = now_time.strftime("%I:%M %p")
formatted_date = now_time.strftime("%A, %d de %B del %Y")

user_information_check = f"""
Name: xxx
Hora Actual: {formatted_time}
Dia / Fecha: {formatted_date}
Posicion Geografica del usuario: xxx
Edad del usuario: xx
Caracteristicas: xx
"""

#####################################################
# SISTEMA DE LOAD HISTORY & SYSTEM INST
#####################################################


def load_history_content():
    try:
        with open("history_tool.txt", "r", encoding="utf-8") as history_file:
            return history_file.read().strip()
    except FileNotFoundError:
        return "No previous conversation history available."
    except Exception as e:
        print(f"Error reading history file: {e}")
        return "Error reading conversation history."

history_content = load_history_content()

def load_system_instructions():
    try:
        with open("system_instructions.txt", "r", encoding="utf-8") as system_file:
            return system_file.read().strip()
    except FileNotFoundError:
        return ""
    except Exception as e:
        print(f"Error reading system instructions file: {e}")
        return ""

system_inst = load_system_instructions()
SYSTEM_INSTRUCTIONS = f"{system_inst}\n{history_content}\nA continuacion esta la categoria de user_information:\n{user_information_check}"

#####################################################
# CONFIGURACIONES DE GEMINI CLIENT & CONECTION
#####################################################

SAFETY_SETTINGS = [
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]

client = genai.Client(api_key=GOOGLE_API_KEY, http_options={"api_version": "v1alpha"})
CONFIG = {
    "generation_config": {
        "response_modalities": ["AUDIO"],
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
 
    },
    "system_instruction": SYSTEM_INSTRUCTIONS,
    "safety_settings": SAFETY_SETTINGS,

    "tools": [{
        "function_declarations": [
            {
                "name": "print_yes",
                "description": "Print yes es la funcion que permite continuar la conversacion. basicamente es una tool que genera todo un contexto de la charla",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "En este va todo el resumen de la conversacion"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    }]
}

#####################################################
# SISTEMA DE DEVICES
#####################################################

pya = pyaudio.PyAudio()

def get_headphone_devices():
    input_device_index = None
    output_device_index = None
    
    # Palabras clave que suelen aparecer en nombres de auriculares
    headphone_keywords = ['auricular', 'headphone', 'headset', 'earphone', 'audífono', 'cascos']
    
    # Obtener información de todos los dispositivos disponibles
    info = pya.get_host_api_info_by_index(0)
    num_devices = info.get('deviceCount')
    
    # Dispositivos predeterminados como respaldo
    default_input = pya.get_default_input_device_info()['index']
    default_output = pya.get_default_output_device_info()['index']
    
    # Buscar dispositivos de auriculares
    input_candidates = []
    output_candidates = []
    
    print("\nDispositivos de audio disponibles:")
    for i in range(num_devices):
        try:
            device_info = pya.get_device_info_by_index(i)
            device_name = device_info.get('name', '').lower()
            is_input = device_info.get('maxInputChannels') > 0
            is_output = device_info.get('maxOutputChannels') > 0
            
            print(f"  [{i}] {device_info['name']} {'(Entrada)' if is_input else ''} {'(Salida)' if is_output else ''}")
            
            # Verificar si el nombre del dispositivo contiene alguna palabra clave de auriculares
            is_headphone = any(keyword in device_name for keyword in headphone_keywords)
            
            if is_input and is_headphone:
                input_candidates.append((i, device_name))
            if is_output and is_headphone:
                output_candidates.append((i, device_name))
                
        except Exception as e:
            print(f"Error al obtener información del dispositivo {i}: {e}")
    
    # Seleccionar el mejor candidato para entrada
    if input_candidates:
        # Ordenar por preferencia (podría mejorarse con un sistema de puntuación más sofisticado)
        input_candidates.sort(key=lambda x: sum(keyword in x[1] for keyword in headphone_keywords), reverse=True)
        input_device_index = input_candidates[0][0]
        print(f"\nDispositivo de entrada seleccionado: {pya.get_device_info_by_index(input_device_index)['name']}")
    else:
        input_device_index = default_input
        print(f"\nUsando dispositivo de entrada predeterminado: {pya.get_device_info_by_index(default_input)['name']}")
    
    # Seleccionar el mejor candidato para salida
    if output_candidates:
        output_candidates.sort(key=lambda x: sum(keyword in x[1] for keyword in headphone_keywords), reverse=True)
        output_device_index = output_candidates[0][0]
        print(f"Dispositivo de salida seleccionado: {pya.get_device_info_by_index(output_device_index)['name']}")
    else:
        output_device_index = default_output
        print(f"Usando dispositivo de salida predeterminado: {pya.get_device_info_by_index(default_output)['name']}")
    
    return input_device_index, output_device_index
from collections import deque

#####################################################
# SISTEMA DE AUDIO, CAPTURA, Y BUFFER
#####################################################

class AudioLoop:
    def __init__(self):
        self.frame_buffer = deque(maxlen=5)  # Aumentamos el tamaño del buffer para mantener más frames
        self.audio_in_queue = asyncio.Queue(maxsize=100)
        self.out_queue = asyncio.Queue(maxsize=20)
        self.session = None
        self.audio_stream = None
        self.data_counter = 0
        self._audio_buffer = bytearray()
        self.last_send_timestamp = None
        self.ping_ms = None
        self.connection_active = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 1
        self.frames_processed = 0
        self.interaction_count = 0
        self.last_frame_send_time = 0  # Tiempo del último envío de frame

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            
            self.last_send_timestamp = time.time()
            await self.session.send(input=text or ".", end_of_turn=True)

    def _get_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        ret, buffer = cv2.imencode('.png', frame)
        if not ret:
            return None
        return {"mime_type": "image/jpeg", "data": base64.b64encode(buffer).decode()}

    async def get_frames(self):
        cap = await asyncio.to_thread(cv2.VideoCapture, 0)
        if not cap.isOpened():
            print("Error: Camera not opened.")
            return
        
        # Controlar la velocidad de captura para evitar sobrecarga
        frame_interval = 0.1  # Capturar un frame cada 100ms (10 fps)
        
        while True:
            # Capturar frame
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break
                
            # Limpiar la cola si está llena para asegurar que siempre enviamos los frames más recientes
            if self.out_queue.full():
                try:
                    # Eliminar el frame más antiguo para hacer espacio
                    self.out_queue.get_nowait()
                    self.out_queue.task_done()
                except asyncio.QueueEmpty:
                    pass
            
            # Añadir el nuevo frame a la cola
            await self.out_queue.put(frame)
            
            # Esperar un intervalo antes de capturar el siguiente frame
            await asyncio.sleep(frame_interval)
            
        cap.release()

    _history_write_buffer = []
    _last_history_write = 0
    _history_write_interval = 5
    
#####################################################
# SISTEMA DE HISTORIAL & RECONEXIONES
#####################################################

    async def _flush_history_buffer(self):
        if not AudioLoop._history_write_buffer:
            return
            
        try:
            with open("history_tool.txt", "a", encoding="utf-8") as history_file:
                history_file.write("".join(AudioLoop._history_write_buffer))
            if AudioLoop._history_cache is not None:
                AudioLoop._history_cache += "\n" + "".join(AudioLoop._history_write_buffer)
            AudioLoop._history_write_buffer.clear()
            AudioLoop._last_history_write = datetime.datetime.now().timestamp()
        except Exception as e:
            print(f"Error escribiendo buffer de historial: {e}")
    
    async def reconnect(self):
        print("Iniciando proceso de reconexión simplificada...")
        self.connection_active = False
        
        if hasattr(self, 'audio_stream') and self.audio_stream is not None:
            try:
                self.audio_stream.close()
                self.audio_stream = None
            except Exception as e:
                print(f"Error al cerrar stream de audio: {e}")
        
        if hasattr(self, 'session') and self.session is not None:
            try:
                await self.session.close()
                self.session = None
                print("Sesión anterior cerrada correctamente")
            except Exception as e:
                print(f"Error al cerrar la sesión: {e}")
        
        if hasattr(self, 'out_queue'):
            try:
                while not self.out_queue.empty():
                    try:
                        self.out_queue.get_nowait()
                        self.out_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
            except Exception as e:
                print(f"Error al limpiar la cola de salida: {e}")
        
        if hasattr(self, 'audio_in_queue'):
            try:
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                        self.audio_in_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
            except Exception as e:
                print(f"Error al limpiar la cola de audio: {e}")
        
        print("Reiniciando conexión...")
        await self.run()
    
    async def send_realtime(self):
        last_send_time = 0
        min_send_interval = 0
        max_retry_attempts = 3
        retry_count = 0
        retry_delay = 0.5
        frame_send_interval = 0.2  # Enviar un frame cada 200ms como máximo
        
        while True:
            try:
                msg = await self.out_queue.get()
                retry_count = 0
                
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - last_send_time
                if time_since_last < min_send_interval:
                    await asyncio.sleep(min_send_interval - time_since_last)
                
                if isinstance(msg, dict) and msg.get('mime_type') == 'image/jpeg':
                    self.frame_buffer.append(msg)
                    current_time = time.time()
                    # Enviar frames a intervalos regulares, independientemente del envío de texto
                    if current_time - self.last_frame_send_time >= frame_send_interval:
                        # Siempre enviamos el frame más reciente del buffer
                        if self.frame_buffer:
                            latest_frame = self.frame_buffer[-1]
                            await self.session.send(input=latest_frame, end_of_turn=False)
                            self.last_frame_send_time = current_time
#                            print("Frame enviado", end="\r")
                else:
                    self.last_send_timestamp = time.time()
                    if isinstance(msg, dict) and msg.get('mime_type') == 'audio/pcm':
                        if isinstance(msg['data'], bytes):
                            msg = {'mime_type': 'audio/pcm', 'data': base64.b64encode(msg['data']).decode()}
                    await self.session.send(input=msg)
                
                last_send_time = asyncio.get_event_loop().time()
                self.out_queue.task_done()

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Error en send_realtime: {e}")
                try:
                    while not self.out_queue.empty():
                        try:
                            self.out_queue.get_nowait()
                            self.out_queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                    
                    await self.reconnect()
                except asyncio.CancelledError:
                    raise
                except Exception as reconnect_error:
                    print(f"Error durante la reconexión desde send_realtime: {reconnect_error}")
                    raise

#####################################################
# SISTEMA DE REPRODUCCION DE AUIDO CON PYAUDIO
#####################################################

    async def listen_audio(self):
        # Usar la función para obtener dispositivos de auriculares
        input_device_index, _ = get_headphone_devices()
        self.audio_stream = None
        try:
            self.audio_stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=CHUNK_SIZE,
            )
            kwargs = {"exception_on_overflow": False}
            while self.connection_active:
                try:
                    data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
                    if not self.connection_active:
                        break
                    await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})
                except Exception as e:
                    print(f"Error al capturar audio: {e}")
                    if not self.connection_active:
                        break
                    if self.connection_active:
                        await self.reconnect()
                        break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Error al inicializar stream de audio de entrada: {e}")
            if self.connection_active:
                await self.reconnect()
        finally:
            if self.audio_stream is not None:
                try:
                    self.audio_stream.close()
                    self.audio_stream = None
                    print("Stream de audio de entrada cerrado correctamente")
                except Exception as e:
                    print(f"Error al cerrar stream de audio de entrada: {e}")
                    self.audio_stream = None

    _history_cache = None
    _last_history_read = 0
    
    async def receive_audio(self):
        while True:
            turn = self.session.receive()
            full_text = ""
            tool_calls_to_respond = []
            tool_call_detected = False
            first_response_received = False
            
            async for response in turn:
                
                if not first_response_received and self.last_send_timestamp is not None:
                    first_response_received = True
                    current_time = time.time()
                    self.ping_ms = round((current_time - self.last_send_timestamp) * 1000)
                    print(f"\n[Ping: {self.ping_ms}ms]")
                    
                
                if hasattr(response, "tool_call") and response.tool_call is not None:
                    tool_call_detected = True
                    if hasattr(response.tool_call, "function_calls"):
                        function_calls = response.tool_call.function_calls
                    else:
                        function_calls = [response.tool_call]
                    
                    for func_call in function_calls:
                        if hasattr(func_call, "name"):
                            func_name = func_call.name
                        elif hasattr(func_call, "function") and hasattr(func_call.function, "name"):
                            func_name = func_call.function.name
                        else:
                            print("No se pudo determinar el nombre de la función")
                            continue
                        
                        if hasattr(func_call, "args"):
                            args_dict = func_call.args
                        elif hasattr(func_call, "function") and hasattr(func_call.function, "args"):
                            args_dict = func_call.function.args
                        else:
                            args_dict = {}
                            print(f"No se pudieron extraer argumentos para la función {func_name}")
                        
                        result_string = args_dict.get("query", "")
                        if result_string:
                            if func_name == "google_search":
                                print(f"\n[Búsqueda Google] {result_string[:50]}..." if len(result_string) > 50 else f"\n[Búsqueda Google] {result_string}")
                            else:
                                print(f"\n[Function Call] {result_string[:50]}..." if len(result_string) > 50 else f"\n[Function Call] {result_string}")
                            
                            try:
                                if hasattr(response.tool_call, "id"):
                                    tool_call_id = response.tool_call.id
                                elif hasattr(func_call, "id"):
                                    tool_call_id = func_call.id
                                elif hasattr(func_call, "call_id"):
                                    tool_call_id = func_call.call_id
                                else:
                                    tool_call_id = "unknown"
                            except AttributeError:
                                tool_call_id = "unknown"
                                
                            tool_calls_to_respond.append({
                                "id": tool_call_id,
                                "name": func_name,
                                "result": result_string
                            })
                            
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_entry = f"[{timestamp}] {func_name}: {result_string}\n"
                            AudioLoop._history_write_buffer.append(new_entry)
                    
                
                if data := response.data:
                    await self.audio_in_queue.put(data)
                    continue
                if text := response.text:
                    full_text += text
                    print(text, end="")
            
            
            current_time = datetime.datetime.now().timestamp()
            if (current_time - AudioLoop._last_history_write > AudioLoop._history_write_interval and
                AudioLoop._history_write_buffer):
                await self._flush_history_buffer()
            
            if tool_calls_to_respond:
                asyncio.create_task(self._process_tool_responses(tool_calls_to_respond))
            
            print()

#####################################################
# SISTEMA DE PROCESAMIENTO DE RESPUESTAS DE TOOLS
#####################################################

    async def _process_tool_responses(self, tool_calls):
        for tool_call in tool_calls:
            try:
                tool_name = tool_call['name']
                result = tool_call['result']
                if tool_name == "google_search":
                    response_text = f"Búsqueda realizada: {result[:30]}..." if len(result) > 30 else f"Búsqueda realizada: {result}"
                    print(f"\n[Búsqueda completada] {tool_name}")
                else:
                    response_text = f"Procesado: {result[:30]}..." if len(result) > 30 else f"Procesado: {result}"
                    print(f"\n[Guardado en history_tool.txt] {tool_name}")
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history_entry = f"[{timestamp}] {tool_name}: {result}\n"
                
                try:
                    with open("history_tool.txt", "a", encoding="utf-8") as history_file:
                        history_file.write(history_entry)
                    
                    if AudioLoop._history_cache is not None:
                        AudioLoop._history_cache += "\n" + history_entry
                except Exception as e:
                    print(f"Error escribiendo en history_tool.txt: {e}")
                
            except Exception as e:
                print(f"Error al procesar la función: {e}")

    async def play_audio(self):
        # Usar la función para obtener dispositivos de auriculares
        _, output_device_index = get_headphone_devices()
        stream = None
        try:
            stream = await asyncio.to_thread(
                pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
                output_device_index=output_device_index,
            )
            while self.connection_active:
                try:
                    audio_data = await asyncio.wait_for(self.audio_in_queue.get(), timeout=1.0)
                    
                    if not self.connection_active:
                        self.audio_in_queue.task_done()
                        break
                        
                    await asyncio.to_thread(stream.write, audio_data)
                    self.audio_in_queue.task_done()
                    
                except asyncio.TimeoutError:
                    if not self.connection_active:
                        break
                except Exception as e:
                    print(f"Error al reproducir audio: {e}")
                    if not self.connection_active:
                        break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Error al inicializar stream de audio de salida: {e}")
            if self.connection_active:
                await self.reconnect()
        finally:
            if stream is not None:
                try:
                    stream.close()
                    print("Stream de audio de salida cerrado correctamente")
                except Exception as e:
                    print(f"Error al cerrar stream de audio de salida: {e}")

#####################################################
# SISTEMA DE INICIO Y REINICIO
#####################################################


    async def run(self):
        self.reconnect_attempts = 0
        self.connection_active = True
        
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                print(f"Conectando a Gemini... {self.reconnect_attempts+1}/{self.max_reconnect_attempts}")
                
                try:
                    global history_content
                    history_content = load_history_content()
                    updated_system_instructions = f"{system_inst}\n{history_content}\nA continuacion esta la categoria de user_information:\n{user_information_check}"


                    updated_config = CONFIG.copy()
                    updated_config["system_instruction"] = updated_system_instructions
                except FileNotFoundError:
                    updated_config = CONFIG
                except Exception as e:
                    print(f"Error al cargar historial para reconexión: {e}")
                    updated_config = CONFIG
                
                async with (
                    client.aio.live.connect(model=MODEL, config=updated_config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session = session
                    self.connection_active = True
                    self.reconnect_attempts = 0
                    self.reconnect_delay = 1
                    
                    print("Conexión establecida correctamente")

                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=5)

                    async def task_wrapper(coro, task_name):
                        try:
                            await coro
                        except asyncio.CancelledError:
                            return
                        except Exception as e:
                            print(f"Error en tarea {task_name}: {e}")
                            if self.connection_active:
                                self.connection_active = False
                                await self.reconnect()
                                return

                    send_text_task = tg.create_task(task_wrapper(self.send_text(), "send_text"))
                    tg.create_task(task_wrapper(self.send_realtime(), "send_realtime"))
                    tg.create_task(task_wrapper(self.listen_audio(), "listen_audio"))
                    tg.create_task(task_wrapper(self.get_frames(), "get_frames"))
                    tg.create_task(task_wrapper(self.receive_audio(), "receive_audio"))
                    tg.create_task(task_wrapper(self.play_audio(), "play_audio"))
                    tg.create_task(task_wrapper(self._monitor_connection(), "monitor_connection"))
                    await send_text_task
                    self.connection_active = False
                    raise asyncio.CancelledError("User requested exit")

            except asyncio.CancelledError:
                print("\nSaliendo por petición del usuario...")
                break
            except Exception as e:
                self.connection_active = False
                print(f"\nError de conexión: {e}")
                
                wait_time = min(self.reconnect_delay * (2 ** min(self.reconnect_attempts, 6)), 60)
                self.reconnect_attempts += 1
                
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"Se alcanzó el límite máximo de intentos de reconexión ({self.max_reconnect_attempts})")
                    break
                    
                print(f"Reintentando en {wait_time:.1f} segundos... (Intento {self.reconnect_attempts}/{self.max_reconnect_attempts})")
                await asyncio.sleep(wait_time)
            
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                try:
                    self.audio_stream.close()
                    self.audio_stream = None
                except Exception as e:
                    print(f"Error al cerrar stream de audio durante reconexión: {e}")
            
            # Cerrar la sesión actual si existe
            if hasattr(self, 'session') and self.session is not None:
                try:
                    await self.session.close()
                    self.session = None
                    print("Sesión anterior cerrada correctamente")
                except Exception as e:
                    print(f"Error al cerrar la sesión durante reconexión: {e}")
            
            if hasattr(self, 'out_queue'):
                try:
                    while not self.out_queue.empty():
                        try:
                            self.out_queue.get_nowait()
                            self.out_queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                except Exception as e:
                    print(f"Error al limpiar la cola de salida: {e}")
            
            if hasattr(self, 'audio_in_queue'):
                try:
                    while not self.audio_in_queue.empty():
                        try:
                            self.audio_in_queue.get_nowait()
                            self.audio_in_queue.task_done()
                        except asyncio.QueueEmpty:
                            break
                except Exception as e:
                    print(f"Error al limpiar la cola de audio: {e}")
            wait_time = min(self.reconnect_delay * (2 ** min(self.reconnect_attempts, 6)), 60)
            print(f"Esperando {wait_time:.1f} segundos antes de intentar reconectar...")
            await asyncio.sleep(wait_time)
        
        print("Sistema de reconexión finalizado")

#####################################################
# SISTEMA DE MONITORIZACION DE CONEXION
#####################################################
    async def _monitor_connection(self):
        check_interval = 5
        ping_timeout = 30
        
        last_activity_time = time.time()
        
        while self.connection_active:
            current_time = time.time()
            
            if self.last_send_timestamp is not None and self.last_send_timestamp > last_activity_time:
                last_activity_time = self.last_send_timestamp
            
            if current_time - last_activity_time > ping_timeout:
                print(f"\nDetectada posible desconexión: Sin actividad por {ping_timeout} segundos")
                if hasattr(self, 'session') and self.session is not None:
                    try:
                        self.last_send_timestamp = time.time()
                        await self.session.send(input=".", end_of_turn=True)
                        last_activity_time = time.time()
                        print("Conexión verificada correctamente")
                    except Exception as e:
                        print(f"Error al verificar conexión: {e}")
                        self.connection_active = False
                        try:
                            await self.reconnect()
                            return
                        except Exception as reconnect_error:
                            print(f"Error durante la reconexión desde monitor: {reconnect_error}")
                            return
                else:
                    print("No hay sesión activa para verificar conexión")
                    self.connection_active = False
                    await self.reconnect()
                    return
            
            try:
                await asyncio.wait_for(asyncio.sleep(check_interval), timeout=check_interval)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                return
            if not self.connection_active:
                break
#####################################################
# INICIALIZACION DE MODULO
#####################################################

if __name__ == "__main__":
    try:
        main = AudioLoop()
        asyncio.run(main.run())
    except KeyboardInterrupt:
        print("\nChat terminado por el usuario.")
    finally:
        pya.terminate()
        print("Recursos de audio liberados.")
