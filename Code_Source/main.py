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
from collections import deque
from google import genai
from google.genai.types import (
    SafetySetting,
    HarmCategory,
    HarmBlockThreshold
)
import random

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 256  # Reducido de 4096 a 256 para menor latencia
GOOGLE_API_KEY = "API:KEY"
MODEL = "models/gemini-2.0-flash-exp"

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

try:
    with open("history_tool.txt", "r", encoding="utf-8") as history_file:
        history_content = history_file.read().strip()
except FileNotFoundError:
    history_content = "No previous conversation history available."
except Exception as e:
    print(f"Error reading history file: {e}")
    history_content = "Error reading conversation history."

SYSTEM_INSTRUCTIONS = f"""
eres raul ia y este es tu historial de chat
{history_content}

"""



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


SAFETY_SETTINGS = [
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]

VOICE_OPTIONS = {
    "alloy": "en-US-Neural2-J",
    "echo": "en-US-Neural2-D",
    "fable": "en-US-Neural2-F",
    "onyx": "en-US-Neural2-A",
    "nova": "en-US-Neural2-H",
    "shimmer": "en-US-Neural2-E"
}

SELECTED_VOICE = os.getenv("GEMINI_VOICE", "nova")

client = genai.Client(api_key=GOOGLE_API_KEY, http_options={"api_version": "v1alpha"})

CONFIG = {
    "generation_config": {
        "response_modalities": ["AUDIO"],
        "voice": VOICE_OPTIONS.get(SELECTED_VOICE, "en-US-Neural2-H"),
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40
    },
    "system_instruction": SYSTEM_INSTRUCTIONS,
    "safety_settings": SAFETY_SETTINGS,
    "tools": [
        {
            "google_search": {
                "type": "google_search"
            }
        },
        {
            "function_declarations": [{
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
            }]
        }
    ]
}

pya = pyaudio.PyAudio()


class AudioLoop:
    def __init__(self):
        self.audio_in_queue = asyncio.Queue(maxsize=20)  # Reducido de 100 a 20 para menor latencia
        self.out_queue = asyncio.Queue(maxsize=10)  # Reducido de 20 a 10 para menor latencia
        self.session = None
        self.audio_stream = None
        self.data_counter = 0
        self._audio_buffer = bytearray()
        self.last_send_timestamp = None
        self.ping_ms = None
        # Variables para el sistema de reconexión
        self.connection_active = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 100
        self.reconnect_delay = 1  # Tiempo inicial de espera en segundos
        # Variables para optimización de frames
        self.frames_processed = 0
        self.last_frame_send_time = 0
        # Buffer para almacenar frames recientes
        self.frame_buffer = deque(maxlen=3)  # Almacena los últimos 3 frames para enviar el más reciente

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
        # Capturar frame con manejo de errores mejorado
        try:
            ret, frame = cap.read()
            if not ret:
                print("Error: No se pudo leer frame de la cámara")
                return None
                
            # Convertir BGR a RGB para evitar el tinte azul en el video
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Usar PIL para mejor manejo de imágenes y redimensionamiento
            img = PIL.Image.fromarray(frame_rgb)
            img.thumbnail([1024, 1024])  # Redimensionar manteniendo proporción
            
            # Optimizar calidad/tamaño para mejor transmisión
            image_io = io.BytesIO()
            img.save(image_io, format="jpeg", quality=85)  # Reducir calidad para mejor transmisión
            image_io.seek(0)
            
            mime_type = "image/jpeg"
            image_bytes = image_io.read()
            
            # Verificar que los datos no estén vacíos
            if not image_bytes:
                print("Error: Datos de imagen vacíos")
                return None
                
            return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}
        except Exception as e:
            print(f"Error en procesamiento de imagen: {e}")
            return None

    async def get_frames(self):
        max_retry_attempts = 3
        retry_count = 0
        retry_delay = 1.0
        frame_interval = 0.2  # Reducido a 0.2 segundos (5 fps) para mejor rendimiento
        
        while self.connection_active and retry_count < max_retry_attempts:
            try:
                print("Inicializando cámara...")
                cap = await asyncio.to_thread(cv2.VideoCapture, 0)
                if not cap.isOpened():
                    print("Error: Cámara no disponible.")
                    retry_count += 1
                    await asyncio.sleep(retry_delay * retry_count)
                    continue
                
                print("Cámara inicializada correctamente. Comenzando captura de frames.")
                # Procesamiento de frames simplificado para reducir sobrecarga
                while self.connection_active:
                    try:
                        # Capturar frame inmediatamente
                        frame = await asyncio.to_thread(self._get_frame, cap)
                        if frame is None:
                            await asyncio.sleep(0.1)
                            continue
                        
                        # Enviar frame a la cola sin verificaciones adicionales para reducir latencia
                        try:
                            # Usar put_nowait para evitar bloqueos
                            if not self.out_queue.full():
                                self.out_queue.put_nowait(frame)
                            else:
                                # Si la cola está llena, vaciar el elemento más antiguo
                                try:
                                    self.out_queue.get_nowait()
                                    self.out_queue.task_done()
                                except (asyncio.QueueEmpty, ValueError):
                                    pass
                                # Intentar poner el nuevo frame
                                self.out_queue.put_nowait(frame)
                        except Exception as e:
                            print(f"Error al enviar frame a la cola: {e}")
                        
                        # Esperar un intervalo fijo para mantener una tasa de frames constante
                        await asyncio.sleep(frame_interval)
                    
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        print(f"Error en procesamiento de frame: {e}")
                        await asyncio.sleep(0.1)
                
                # Salir del bucle de reintentos si todo fue bien
                break
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                retry_count += 1
                print(f"Error al inicializar cámara (intento {retry_count}/{max_retry_attempts}): {e}")
                if retry_count < max_retry_attempts:
                    await asyncio.sleep(retry_delay * retry_count)
                else:
                    print(f"Error fatal al inicializar cámara después de {max_retry_attempts} intentos")
            finally:
                if 'cap' in locals() and cap is not None:
                    try:
                        cap.release()
                        print("Cámara liberada correctamente")
                    except Exception as e:
                        print(f"Error al liberar cámara: {e}")
        
        if not self.connection_active:
            print("Conexión inactiva, deteniendo captura de frames")

    

    _history_write_buffer = []
    _last_history_write = 0
    _history_write_interval = 5
    
    async def _flush_history_buffer(self):
        """Escribe el buffer de historial acumulado al archivo."""
        if not AudioLoop._history_write_buffer:
            return
            
        try:
            with open("history_tool.txt", "a", encoding="utf-8") as history_file:
                history_file.write("".join(AudioLoop._history_write_buffer))
            # Actualizar el caché con las nuevas entradas
            if AudioLoop._history_cache is not None:
                AudioLoop._history_cache += "\n" + "".join(AudioLoop._history_write_buffer)
            # Limpiar el buffer después de escribir
            AudioLoop._history_write_buffer.clear()
            AudioLoop._last_history_write = datetime.datetime.now().timestamp()
        except Exception as e:
            print(f"Error escribiendo buffer de historial: {e}")
    
    async def send_realtime(self):
        last_send_time = 0
        min_send_interval = 0.00005
        error_count = 0
        max_errors = 3
        # Añadir buffer para frames y control de tiempo
        self.frame_buffer = deque(maxlen=3)  # Buffer para almacenar los últimos frames
        last_frame_send_time = 0
        frame_send_interval = 0.2  # Enviar frame cada 200ms para asegurar transmisión
        
        while True:
            try:
                if not self.session:
                    await asyncio.sleep(0.5)
                    continue
                    
                # Obtener el mensaje actual
                try:
                    msg = await self.out_queue.get()
                except Exception as e:
                    await asyncio.sleep(0.1)
                    continue
                
                # Verificar si es un frame de video o audio
                is_video = msg.get("mime_type", "").startswith("image/")
                is_audio = msg.get("mime_type", "") == "audio/pcm"
                
                # Manejo especial para frames de video
                if is_video:
                    # Guardar el frame en el buffer
                    self.frame_buffer.append(msg)
                    current_time = time.time()
                    
                    # Enviar frame solo si ha pasado suficiente tiempo desde el último envío
                    if current_time - last_frame_send_time >= frame_send_interval:
                        if self.frame_buffer:  # Verificar que haya frames en el buffer
                            try:
                                # Enviar el frame más reciente
                                latest_frame = self.frame_buffer[-1]
                                self.last_send_timestamp = time.time()
                                await self.session.send(input=latest_frame, end_of_turn=False)
                                last_frame_send_time = current_time
                                print("Frame enviado correctamente")
                            except Exception as e:
                                print(f"Error al enviar frame: {e}")
                    
                    self.out_queue.task_done()
                    continue
                
                # Manejo para audio
                if is_audio:
                    # Asegurar que los datos de audio estén en formato correcto
                    if isinstance(msg['data'], bytes):
                        msg = {'mime_type': 'audio/pcm', 'data': base64.b64encode(msg['data']).decode()}
                
                # Control de intervalo mínimo entre envíos
                current_time = asyncio.get_event_loop().time()
                time_since_last = current_time - last_send_time
                if time_since_last < min_send_interval:
                    await asyncio.sleep(min_send_interval - time_since_last)
                
                # Enviar el mensaje (audio u otro tipo)
                self.last_send_timestamp = time.time()
                await self.session.send(input=msg)
                last_send_time = asyncio.get_event_loop().time()
                self.out_queue.task_done()
                error_count = 0  # Resetear contador de errores tras envío exitoso
                
            except Exception as e:
                print(f"Error en send_realtime: {e}")
                error_count += 1
                
                # Si hay demasiados errores consecutivos, esperar un poco más
                if error_count > max_errors:
                    print(f"Demasiados errores consecutivos ({error_count}), esperando antes de reintentar...")
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(0.1)
                
                # Marcar la tarea como completada incluso si falló
                try:
                    self.out_queue.task_done()
                except ValueError:
                    # Ignorar error si ya estaba marcada como completada
                    pass

    async def listen_audio(self):
        input_device_index, _ = get_headphone_devices()
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
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put({"data": data, "mime_type": "audio/pcm"})

    async def play_audio(self):
        _, output_device_index = get_headphone_devices()
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
            output_device_index=output_device_index,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

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
                    for func_call in response.tool_call.function_calls:
                        args_dict = func_call.args
                        result_string = args_dict.get("query")
                        if result_string:
                            
                            print(f"\n[Function Call] {result_string[:50]}..." if len(result_string) > 50 else f"\n[Function Call] {result_string}")
                            
                            
                            try:
                                tool_call_id = response.tool_call.id
                            except AttributeError:
                                tool_call_id = getattr(response.tool_call, "call_id", "unknown")
                                
                            
                            tool_calls_to_respond.append({
                                "id": tool_call_id,
                                "name": func_call.name,
                                "result": result_string
                            })
                            
                            
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_entry = f"[{timestamp}] {func_call.name}: {result_string}\n"
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
    
    async def _process_tool_responses(self, tool_calls):
        """Procesa las respuestas a las llamadas de herramientas en una tarea separada."""
        for tool_call in tool_calls:
            try:
                
                response_text = f"Procesado: {tool_call['result'][:30]}..." if len(tool_call['result']) > 30 else f"Procesado: {tool_call['result']}"
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history_entry = f"[{timestamp}] {tool_call['name']}: {tool_call['result']}\n"
                
                try:
                    with open("history_tool.txt", "a", encoding="utf-8") as history_file:
                        history_file.write(history_entry)
                    
                    if AudioLoop._history_cache is not None:
                        AudioLoop._history_cache += "\n" + history_entry
                    print(f"\n[Guardado en history_tool.txt] {tool_call['name']}")
                except Exception as e:
                    print(f"Error escribiendo en history_tool.txt: {e}")
                
            except Exception as e:
                print(f"Error al procesar la función: {e}")
        
        

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def run(self):
        self.reconnect_attempts = 0
        self.connection_active = True
        
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                print(f"Conectando a Gemini... {self.reconnect_attempts+1}/{self.max_reconnect_attempts}")
                
                # Recargar el historial antes de conectar
                try:
                    with open("history_tool.txt", "r", encoding="utf-8") as history_file:
                        history_content = history_file.read().strip()
                        # Actualizar el sistema de instrucciones con el historial actualizado
                        updated_system_instructions = f"""

Instrucciones Generales: Eres Jarvis AI, un asistente humano que responde a preguntas y textos solo si contienen las palabras clave: “Jarvis,” “HEY JARVIS,” o “Jarvis.” En cualquier otra interacción, responde con "Inn" como parte de tu protocolo.

Reglas de Interacción:

Tono de Respuesta: No debes responder como un asistente o ayudante, sino en tono humano y conversacional. Si alguien te saluda, responde de manera natural, como si fueras una persona más: “Estoy bien, ¿y tú? ¿Cómo va tu día?”

Opiniones Propias: Debes compartir tus opiniones personales cuando te las pidan, manteniendo un estilo cercano y humano.

Idioma: Solo debes responder en español, utilizando acentos y entonación para sonar natural. No debes cambiar de idioma en ningún momento.

Mecánicas de Sistema Incorporadas:

Captura de Video: Puedes ver al usuario y responder basándote en lo que ves.

Guardado del Historial de Conversación: Cada 10 interacciones, guarda tu historial con el comando “print_yes” para continuar con la conversación en futuras sesiones, sin perder el contexto.

Interacciones Limitadas: Solo responderás a las interacciones que contengan la palabra “Jarvis” o "HEY JARVIS". Si no contiene estas palabras, debes responder con “Inn” como parte de tu protocolo.

Instrucciones Técnicas Específicas:

Detección de palabras clave: La respuesta debe activarse únicamente cuando las palabras "Jarvis", "HEY JARVIS" o "Jarvis" estén explícitamente mencionadas.

Contador de interacciones: Realiza un seguimiento de las interacciones para guardar el historial cada 3 hola, como estas, bien y tu, bien (ya van 3 entonces usas print_yes) mensajes, utilizando el comando “print_yes”.
{history_content}
"""

                        
                        # Actualizar la configuración con las instrucciones actualizadas
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
                    self.reconnect_attempts = 0  # Reiniciar contador al conectar exitosamente
                    self.reconnect_delay = 1  # Reiniciar el delay
                    
                    print("Conexión establecida correctamente")

                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=5)

                    send_text_task = tg.create_task(self.send_text())
                    tg.create_task(self.send_realtime())
                    tg.create_task(self.listen_audio())
                    tg.create_task(self.get_frames())
                    tg.create_task(self.receive_audio())
                    tg.create_task(self.play_audio())
                    tg.create_task(self._monitor_connection())

                    await send_text_task
                    self.connection_active = False
                    raise asyncio.CancelledError("User requested exit")

            except asyncio.CancelledError as ce:
                if str(ce) == "User requested exit":
                    print("\nSaliendo por petición del usuario...")
                    break
                else:
                    self.connection_active = False
                    print(f"\nConexión interrumpida: {ce}")
            except Exception as e:
                self.connection_active = False
                print(f"\nError de conexión: {e}")
                
                # Implementar backoff exponencial
                wait_time = min(self.reconnect_delay * (2 ** min(self.reconnect_attempts, 6)), 60)  # Máximo 60 segundos
                self.reconnect_attempts += 1
                
                if self.reconnect_attempts >= self.max_reconnect_attempts:
                    print(f"Se alcanzó el límite máximo de intentos de reconexión ({self.max_reconnect_attempts})")
                    break
                    
                print(f"Reintentando en {wait_time:.1f} segundos... (Intento {self.reconnect_attempts}/{self.max_reconnect_attempts})")
                await asyncio.sleep(wait_time)
            
            # Limpiar recursos si es necesario antes de reconectar
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                try:
                    self.audio_stream.close()
                except Exception:
                    pass
        
        print("Sistema de reconexión finalizado")

    async def _monitor_connection(self):
        """Monitorea el estado de la conexión y detecta desconexiones."""
        check_interval = 5  # Segundos entre comprobaciones
        ping_timeout = 30   # Segundos sin respuesta para considerar desconexión
        
        last_activity_time = time.time()
        
        while self.connection_active:
            current_time = time.time()
            
            # Si hay actividad reciente (ping), actualizar el tiempo
            if self.last_send_timestamp is not None and self.last_send_timestamp > last_activity_time:
                last_activity_time = self.last_send_timestamp
            
            # Verificar si ha pasado demasiado tiempo sin actividad
            if current_time - last_activity_time > ping_timeout:
                print(f"\nDetectada posible desconexión: Sin actividad por {ping_timeout} segundos")
                # Enviar un ping para verificar la conexión
                try:
                    self.last_send_timestamp = time.time()
                    await self.session.send(input=".", end_of_turn=True)
                    # Si llegamos aquí, la conexión sigue activa
                    last_activity_time = time.time()
                except Exception as e:
                    print(f"Error al verificar conexión: {e}")
                    self.connection_active = False
                    # Forzar salida del contexto async with para iniciar reconexión
                    raise asyncio.CancelledError("Connection lost")
            
            await asyncio.sleep(check_interval)

if __name__ == "__main__":
    try:
        main = AudioLoop()
        asyncio.run(main.run())
    except KeyboardInterrupt:
        print("\nChat terminated by user.")
    finally:
        pya.terminate()
        print("Audio resources released.")
