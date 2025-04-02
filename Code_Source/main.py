# 2/4/2025 V 1.1.7 [No UI Feature]

import asyncio
import platform
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
CHUNK_SIZE = 1024







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
Name: Manuel
Hora Actual: {formatted_time}
Dia / Fecha: {formatted_date}
Posicion Geografica del usuario:
Edad del usuario: Unknow
Caracteristicas: Unknow
"""

#####################################################
# SISTEMA DE LOAD HISTORY & SYSTEM INST
#####################################################


def load_history_content():
    try:
        with open("history_tool.txt", "r", encoding="utf-8") as history_file:
            # Read all lines and get only the last non-empty line
            lines = [line.strip() for line in history_file if line.strip()]
            if lines:
                return lines[-1]  # Return only the last line
            return "No previous conversation history available."
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
    "tools": [
        {
            "google_search": {
                "type": "google_search"
            }
        },
        {
            "function_declarations": [
                {
                    "name": "print_yes",
                    "description": "Print yes es la funcion que permite continuar la conversacion. basicamente es una tool que genera todo un contexto de la charla",
                    "parameters": {
                        "type": "object",
                        "required": ["query"],
                        "properties": {
                            "query": {
                                "type": "string", 
                                "description": "En este va todo el resumen de la conversacion"
                            }
                        }
                    }
                }
            ]
        }
    ],
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
            
            # Generar un ID único para esta transmisión
            transmission_id = f"msg_{int(time.time()*1000)}"
            print(f"\nEnviando mensaje con ID: {transmission_id}")
            
            # Interrumpir cualquier reproducción actual vaciando la cola de audio
            try:
                # Vaciar la cola de audio para interrumpir la reproducción actual
                while not self.audio_in_queue.empty():
                    try:
                        self.audio_in_queue.get_nowait()
                        self.audio_in_queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                print("Cola de audio vaciada para dar prioridad al nuevo mensaje")
            except Exception as e:
                print(f"Error al vaciar la cola de audio: {e}")
            
            self.last_send_timestamp = time.time()
            await self.session.send(input=text or ".", end_of_turn=True)

    def _get_frame(self, cap):
        ret, frame = cap.read()
        if not ret:
            return None
        # Convertir BGR a RGB para evitar el tinte azul en el video
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Usar PIL para mejor manejo de imágenes y redimensionamiento
        img = PIL.Image.fromarray(frame_rgb)
        img.thumbnail([1024, 1024])  # Redimensionar manteniendo proporción
        
        # Usar BytesIO para manejar la imagen en memoria
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        
        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        max_retry_attempts = 3
        retry_count = 0
        retry_delay = 1.0
        
        while self.connection_active and retry_count < max_retry_attempts:
            try:
                cap = await asyncio.to_thread(cv2.VideoCapture, 0)
                if not cap.isOpened():
                    print("Error: Camera not opened.")
                    retry_count += 1
                    await asyncio.sleep(retry_delay * retry_count)
                    continue
                
                # Reduce frame interval for more responsive video
                frame_interval = 0.2  # Reduced from 0.5 to 0.2 seconds (5 fps)
                
                # Simplified frame processing - reduce error checking overhead
                while self.connection_active:
                    try:
                        frame = await asyncio.to_thread(self._get_frame, cap)
                        if frame is None:
                            await asyncio.sleep(0.1)
                            continue
                        
                        # Skip full queue check to reduce overhead - just add the new frame
                        try:
                            await self.out_queue.put(frame)
                        except:
                            pass  # Ignore errors when queue is full
                        
                        await asyncio.sleep(frame_interval)
                    
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        print(f"Frame error: {e}")
                        await asyncio.sleep(0.1)
                
                # Exit retry loop if everything went well
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
    
#####################################################
# SISTEMA DE MANEJO DE HISTORIAL
#####################################################

#####################################################
# SISTEMA DE PROCESAMIENTO DE HISTORIAL
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
    
#####################################################
# SISTEMA DE RECONEXIONES Y RECUPERACION
#####################################################

    async def reconnect(self):
        print("Iniciando proceso de reconexión...")
        self.connection_active = False
        max_cleanup_retries = 3
        cleanup_retry_delay = 1.0
        reconnect_backoff_factor = 2
        cleanup_timeout = 5.0  # Timeout para operaciones de limpieza

        async def cleanup_resources():
            cleanup_success = True
            
            # Detener monitor y tareas activas
            if hasattr(self, '_monitor_task') and self._monitor_task is not None:
                try:
                    self._monitor_task.cancel()
                    try:
                        # Esperar a que el monitor termine con un timeout
                        await asyncio.wait_for(asyncio.shield(self._monitor_task), timeout=cleanup_timeout)
                    except asyncio.TimeoutError:
                        print("Timeout al esperar que termine el monitor")
                    except (asyncio.CancelledError, Exception) as e:
                        print(f"Error al esperar que termine el monitor: {e}")
                    self._monitor_task = None
                except Exception as e:
                    print(f"Error al detener monitor: {e}")
                    self._monitor_task = None
                    cleanup_success = False

            # Cerrar stream de audio con reintentos y timeout
            if hasattr(self, 'audio_stream') and self.audio_stream is not None:
                for attempt in range(max_cleanup_retries):
                    try:
                        async def close_stream():
                            try:
                                self.audio_stream.stop_stream()
                                self.audio_stream.close()
                            except Exception as e:
                                raise Exception(f"Error al cerrar stream: {e}")
                        
                        # Ejecutar cierre con timeout
                        try:
                            await asyncio.wait_for(asyncio.to_thread(close_stream), timeout=cleanup_timeout)
                            self.audio_stream = None
                            print("Stream de audio cerrado correctamente")
                            break
                        except asyncio.TimeoutError:
                            print(f"Timeout al cerrar stream de audio en intento {attempt + 1}")
                        except Exception as e:
                            print(f"Error al cerrar stream de audio: {e}")
                            
                        if attempt < max_cleanup_retries - 1:
                            await asyncio.sleep(cleanup_retry_delay * (attempt + 1))
                        else:
                            self.audio_stream = None
                            cleanup_success = False
                    except Exception as e:
                        print(f"Error crítico al cerrar stream de audio: {e}")
                        self.audio_stream = None
                        cleanup_success = False
                        
            # Close session with retries and improved error handling
            if hasattr(self, 'session') and self.session is not None:
                for attempt in range(max_cleanup_retries):
                    try:
                        # Try to close the session with timeout
                        await asyncio.wait_for(self.session.close(), timeout=cleanup_timeout)
                        self.session = None
                        print("Sesión cerrada correctamente")
                        break
                    except asyncio.TimeoutError:
                        print(f"Timeout al cerrar sesión en intento {attempt + 1}")
                    except Exception as e:
                        print(f"Error al cerrar sesión: {e}")
                    
                    if attempt < max_cleanup_retries - 1:
                        # Increase wait time between attempts
                        await asyncio.sleep(cleanup_retry_delay * (attempt + 1))
                    else:
                        self.session = None
                        cleanup_success = False
                        print("No se pudo cerrar la sesión después de todos los intentos")
            # Limpiar colas con manejo de errores mejorado y vaciado seguro
            for queue_name, queue in [('out_queue', self.out_queue), ('audio_in_queue', self.audio_in_queue)]:
                if hasattr(self, queue_name):
                    try:
                        # Vaciar la cola existente de forma segura
                        while True:
                            try:
                                queue.get_nowait()
                                queue.task_done()
                            except asyncio.QueueEmpty:
                                break
                            except ValueError:
                                # Ignorar errores de task_done
                                pass
                            except Exception as e:
                                print(f"Error al vaciar cola {queue_name}: {e}")
                                break
                        
                        # Crear nuevas colas
                        if queue_name == 'out_queue':
                            self.out_queue = asyncio.Queue(maxsize=20)
                        elif queue_name == 'audio_in_queue':
                            self.audio_in_queue = asyncio.Queue(maxsize=100)
                        print(f"Cola {queue_name} limpiada y recreada correctamente")
                    except Exception as e:
                        print(f"Error al recrear cola {queue_name}: {e}")
                        cleanup_success = False

            # Limpiar buffers y reiniciar estados con manejo de errores específico
            try:
                # Limpiar frame buffer de forma segura
                if hasattr(self, 'frame_buffer'):
                    try:
                        self.frame_buffer.clear()
                        print("Frame buffer limpiado correctamente")
                    except Exception as e:
                        print(f"Error al limpiar frame buffer: {e}")
                        cleanup_success = False

                # Reiniciar contadores y timestamps
                try:
                    self.last_send_timestamp = None
                    self.last_frame_send_time = 0
                    self.frames_processed = 0
                    self.data_counter = 0
                    print("Contadores y timestamps reiniciados correctamente")
                except Exception as e:
                    print(f"Error al reiniciar contadores: {e}")
                    cleanup_success = False

                # Reiniciar otros estados
                try:
                    self._audio_buffer = bytearray()
                    self.ping_ms = None
                    self.interaction_count = 0
                    print("Estados adicionales reiniciados correctamente")
                except Exception as e:
                    print(f"Error al reiniciar estados adicionales: {e}")
                    cleanup_success = False

            except Exception as e:
                print(f"Error general al reiniciar estados: {e}")
                cleanup_success = False

            return cleanup_success

        try:
            # Ejecutar limpieza de recursos
            cleanup_result = await cleanup_resources()
            if not cleanup_result:
                print("Advertencia: Algunos recursos no se limpiaron correctamente")

            # Pausa antes de intentar reconexión
            wait_time = self.reconnect_delay * (reconnect_backoff_factor ** min(self.reconnect_attempts, 4))
            print(f"Esperando {wait_time:.1f} segundos antes de intentar reconectar...")
            await asyncio.sleep(wait_time)

            # Intentar reconexión
            print("Intentando reconexión...")
            # Crear nuevas colas para evitar problemas con las anteriores
            self.audio_in_queue = asyncio.Queue(maxsize=100)
            self.out_queue = asyncio.Queue(maxsize=20)
            
            # Restablecer el estado de conexión antes de ejecutar run()
            self.connection_active = True
            
            # Ejecutar run() en un bloque try-except para manejar errores
            await self.run()
            print("Conexión restablecida exitosamente")
            self.reconnect_attempts = 0
            
        except asyncio.CancelledError:
            print("Reconexión cancelada por el usuario")
            self.connection_active = False
            raise
        except Exception as e:
            print(f"Error al restablecer la conexión: {e}")
            self.reconnect_attempts += 1
            self.connection_active = False
            
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                print(f"Se alcanzó el máximo de intentos de reconexión ({self.max_reconnect_attempts})")
                print("El sistema se detendrá. Por favor, reinicie la aplicación manualmente.")
                return
            else:
                print(f"Reintentando reconexión ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
                # Esperar un poco antes de intentar de nuevo para evitar bucles rápidos
                await asyncio.sleep(2.0)
                await self.reconnect()
    
    async def send_realtime(self):
        # Simplified sending logic with fewer checks
        while self.connection_active:
            try:
                if not self.session:
                    await asyncio.sleep(0.5)
                    continue

                try:
                    msg = await self.out_queue.get()
                except:
                    await asyncio.sleep(0.1)
                    continue
                    
                try:
                    # Simplified sending logic - fewer retries and checks
                    if isinstance(msg, dict) and msg.get('mime_type') == 'image/jpeg':
                        self.frame_buffer.append(msg)
                        current_time = time.time()
                        if current_time - self.last_frame_send_time >= 0.2:  # Send frame every 200ms
                            if self.frame_buffer:
                                await self.session.send(input=self.frame_buffer[-1], end_of_turn=False)
                                self.last_frame_send_time = current_time
                    else:
                        if isinstance(msg, dict) and msg.get('mime_type') == 'audio/pcm':
                            if isinstance(msg['data'], bytes):
                                msg = {'mime_type': 'audio/pcm', 'data': base64.b64encode(msg['data']).decode()}
                        await self.session.send(input=msg)
                    
                    self.out_queue.task_done()
                except Exception as e:
                    print(f"Send error: {e}")
                
            except Exception as e:
                print(f"Critical send error: {e}")
                await asyncio.sleep(0.1)
                
                # Solo marcar como completada si pudimos procesar el mensaje
                try:
                    if message_processed or not self.connection_active:
                        self.out_queue.task_done()
                except ValueError as task_done_error:
                    # Ignorar el error "task_done() called too many times"
                    if "called too many times" in str(task_done_error):
                        print("Advertencia: Cola ya marcada como completada")
                    else:
                        print(f"Error al marcar tarea como completada: {task_done_error}")

            except asyncio.CancelledError:
                print("Operación de envío cancelada")
                self.connection_active = False
                break
            except Exception as e:
                print(f"Error crítico en send_realtime: {e}")
                error_count += 1
                if error_count >= max_errors:
                    print(f"Demasiados errores consecutivos ({error_count}), iniciando reconexión...")
                    try:
                        if self.connection_active:
                            self.connection_active = False
                            await self.reconnect()
                        else:
                            print("Conexión inactiva, deteniendo send_realtime")
                            break
                    except asyncio.CancelledError:
                        self.connection_active = False
                        break
                    except Exception as reconnect_error:
                        print(f"Error fatal durante la reconexión: {reconnect_error}")
                        self.connection_active = False
                        break
                else:
                    await asyncio.sleep(0.5)  # Pausa breve antes de continuar

#####################################################
# SISTEMA DE REPRODUCCION DE AUIDO CON PYAUDIO
#####################################################
    async def listen_audio(self):
        # Simplified audio capture with fewer error checks
        max_init_retries = 3
        init_retry_count = 0
        
        # Set up audio capture parameters
        kwargs = {"exception_on_overflow": False}  # Optimize performance by ignoring overflow

        while self.connection_active and init_retry_count < max_init_retries:
            try:
                # Get input device for headphones
                input_device_index, _ = get_headphone_devices()
                self.audio_stream = None

                # Simplified audio stream initialization
                try:
                    self.audio_stream = pya.open(
                        format=FORMAT,
                        channels=CHANNELS,
                        rate=SEND_SAMPLE_RATE,
                        input=True,
                        input_device_index=input_device_index,
                        frames_per_buffer=CHUNK_SIZE,
                    )
                    print("Audio stream initialized successfully")
                except Exception as e:
                    raise RuntimeError(f"Error initializing audio stream: {e}")

                kwargs = {"exception_on_overflow": False}
                consecutive_errors = 0
                max_consecutive_errors = 5
                error_threshold_time = 2.0  # segundos
                last_error_time = None
                stream_error_count = 0  # Resetear contador de errores de stream

                while self.connection_active:
                    try:
                        if not self.audio_stream:
                            raise RuntimeError("Stream de audio no disponible")

                        # Usar timeout para evitar bloqueos en la lectura del audio
                        try:
                            data = await asyncio.wait_for(
                                asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs),
                                timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            print("Timeout al leer audio, reintentando...")
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                raise RuntimeError("Múltiples timeouts al leer audio")
                            continue

                        if not self.connection_active:
                            break

                        # Verificar que la cola no esté llena antes de intentar poner datos
                        if self.out_queue.full():
                            try:
                                # Eliminar el elemento más antiguo para hacer espacio
                                self.out_queue.get_nowait()
                                self.out_queue.task_done()
                            except (asyncio.QueueEmpty, ValueError) as e:
                                # Ignorar errores de cola vacía o task_done llamado demasiadas veces
                                pass

                        # Usar timeout para evitar bloqueos al poner en la cola
                        try:
                            await asyncio.wait_for(
                                self.out_queue.put({"data": data, "mime_type": "audio/pcm"}),
                                timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            # Si no podemos poner en la cola, simplemente continuamos
                            continue

                        consecutive_errors = 0  # Resetear contador de errores tras éxito
                        last_error_time = None
                        stream_error_count = 0  # Resetear contador de errores de stream

                    except Exception as e:
                        current_time = time.time()
                        if last_error_time is None:
                            last_error_time = current_time
                        elif current_time - last_error_time < error_threshold_time:
                            consecutive_errors += 1
                        else:
                            consecutive_errors = 1
                        last_error_time = current_time

                        print(f"Error al capturar audio: {e}")
                        stream_error_count += 1

                        # Verificar si tenemos demasiados errores consecutivos o totales
                        if consecutive_errors >= max_consecutive_errors or stream_error_count >= max_stream_errors:
                            print(f"Demasiados errores ({consecutive_errors} consecutivos, {stream_error_count} totales), reiniciando stream...")
                            break  # Salir del bucle interno para reiniciar el stream

                        if not self.connection_active:
                            break

                        await asyncio.sleep(0.1)  # Breve pausa antes de reintentar

                # Si salimos del bucle por errores pero la conexión sigue activa, reiniciamos el stream
                if self.connection_active and (consecutive_errors >= max_consecutive_errors or stream_error_count >= max_stream_errors):
                    if self.audio_stream is not None:
                        try:
                            self.audio_stream.stop_stream()
                            self.audio_stream.close()
                            self.audio_stream = None
                            print("Stream de audio cerrado para reinicio")
                        except Exception as e:
                            print(f"Error al cerrar stream para reinicio: {e}")
                            self.audio_stream = None
                    # Continuar al siguiente intento sin incrementar init_retry_count
                    await asyncio.sleep(1.0)  # Pausa antes de reiniciar
                    continue

                # Si llegamos aquí sin errores o con la conexión inactiva, salimos del bucle de reintentos
                if not self.connection_active or stream_error_count < max_stream_errors:
                    break

            except asyncio.CancelledError:
                raise
            except Exception as e:
                init_retry_count += 1
                if init_retry_count < max_init_retries:
                    wait_time = init_retry_delay * (2 ** (init_retry_count - 1))  # Backoff exponencial
                    print(f"Error al inicializar stream de audio (intento {init_retry_count}/{max_init_retries}): {e}")
                    print(f"Reintentando en {wait_time} segundos...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"Error fatal al inicializar stream de audio después de {max_init_retries} intentos: {e}")
                    if self.connection_active:
                        print("Iniciando proceso de reconexión debido a errores persistentes de audio")
                        self.connection_active = False
                        asyncio.create_task(self.reconnect())
                    return

            finally:
                if self.audio_stream is not None:
                    try:
                        self.audio_stream.stop_stream()
                        self.audio_stream.close()
                        self.audio_stream = None
                        print("Stream de audio de entrada cerrado correctamente")
                    except Exception as e:
                        print(f"Error al cerrar stream de audio de entrada: {e}")
                        self.audio_stream = None

        if not self.connection_active:
            print("Conexión inactiva, deteniendo listen_audio")


    _history_cache = None
    _last_history_read = 0
    
    async def receive_audio(self):
        max_retry_attempts = 3
        retry_count = 0
        retry_delay = 1.0
        backoff_factor = 2
        error_count = 0
        max_consecutive_errors = 5
        error_threshold_time = 2.0  # segundos
        last_error_time = None
        
        while self.connection_active:
            try:
                if not self.session:
                    print("No hay sesión activa en receive_audio. Esperando reconexión...")
                    await asyncio.sleep(1)
                    continue
                    
                try:
                    turn = self.session.receive()
                except Exception as session_error:
                    print(f"Error al iniciar recepción: {session_error}")
                    if "invalid frame payload data" in str(session_error) or "connection closed" in str(session_error).lower():
                        print("Detectado error de conexión en la sesión, iniciando reconexión...")
                        self.connection_active = False
                        asyncio.create_task(self.reconnect())
                        return
                    raise  # Re-lanzar para que sea manejado por el bloque exterior
                
                full_text = ""
                tool_calls_to_respond = []
                tool_call_detected = False
                first_response_received = False
                retry_count = 0  # Resetear contador de reintentos tras éxito
                error_count = 0  # Resetear contador de errores tras éxito
                last_error_time = None
                
                try:
                    async for response in turn:
                        if not self.connection_active:
                            break
                            
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
                                if not self.connection_active:
                                    break
                                    
                                try:
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
                                except Exception as func_error:
                                    print(f"Error al procesar función: {func_error}")
                                    continue  # Continuar con la siguiente función
                        
                        try:
                            if data := response.data:
                                # Usar timeout para evitar bloqueos al poner en la cola
                                try:
                                    if self.audio_in_queue.full():
                                        # Si la cola está llena, eliminar el elemento más antiguo
                                        try:
                                            self.audio_in_queue.get_nowait()
                                            self.audio_in_queue.task_done()
                                        except (asyncio.QueueEmpty, ValueError):
                                            pass
                                    
                                    await asyncio.wait_for(
                                        self.audio_in_queue.put(data),
                                        timeout=1.0
                                    )
                                except asyncio.TimeoutError:
                                    # Si no podemos poner en la cola, simplemente continuamos
                                    continue
                                continue
                            if text := response.text:
                                full_text += text
                                print(text, end="")
                        except Exception as data_error:
                            print(f"Error al procesar datos de respuesta: {data_error}")
                            continue  # Continuar con la siguiente respuesta
                            
                except Exception as stream_error:
                    if "task_done() called too many times" in str(stream_error):
                        print("Advertencia: Error de task_done() en la cola, continuando...")
                    elif "invalid frame payload data" in str(stream_error) or "connection closed" in str(stream_error).lower():
                        print(f"Error de conexión en el stream: {stream_error}")
                        if self.connection_active:
                            self.connection_active = False
                            asyncio.create_task(self.reconnect())
                            return
                    else:
                        print(f"Error en el stream de respuestas: {stream_error}")
                        current_time = time.time()
                        if last_error_time is None:
                            last_error_time = current_time
                        elif current_time - last_error_time < error_threshold_time:
                            error_count += 1
                        else:
                            error_count = 1
                        last_error_time = current_time
                        
                        if error_count >= max_consecutive_errors:
                            print(f"Demasiados errores consecutivos ({error_count}), iniciando reconexión...")
                            if self.connection_active:
                                self.connection_active = False
                                asyncio.create_task(self.reconnect())
                                return
                
                # Procesar resultados después de completar el stream
                if self.connection_active:
                    try:
                        current_time = datetime.datetime.now().timestamp()
                        if (current_time - AudioLoop._last_history_write > AudioLoop._history_write_interval and
                            AudioLoop._history_write_buffer):
                            await self._flush_history_buffer()
                        
                        if tool_calls_to_respond:
                            asyncio.create_task(self._process_tool_responses(tool_calls_to_respond))
                        
                        print()
                    except Exception as post_error:
                        print(f"Error al procesar resultados finales: {post_error}")
            
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if not self.connection_active:
                    print("Conexión inactiva, deteniendo receive_audio")
                    return
                    
                current_time = time.time()
                if last_error_time is None:
                    last_error_time = current_time
                elif current_time - last_error_time < error_threshold_time:
                    error_count += 1
                else:
                    error_count = 1
                last_error_time = current_time
                
                print(f"Error en receive_audio: {e}")
                
                if "invalid frame payload data" in str(e) or "connection closed" in str(e).lower():
                    print("Detectado error de conexión, iniciando reconexión...")
                    if self.connection_active:
                        self.connection_active = False
                        asyncio.create_task(self.reconnect())
                        return
                
                if error_count >= max_consecutive_errors:
                    print(f"Demasiados errores consecutivos ({error_count}), iniciando reconexión...")
                    if self.connection_active:
                        self.connection_active = False
                        asyncio.create_task(self.reconnect())
                        return
                
                retry_count += 1
                if retry_count >= max_retry_attempts:
                    print(f"Demasiados reintentos ({retry_count}), iniciando reconexión...")
                    if self.connection_active:
                        self.connection_active = False
                        asyncio.create_task(self.reconnect())
                        return
                
                wait_time = retry_delay * (backoff_factor ** (retry_count - 1))
                print(f"Reintentando en {wait_time:.1f} segundos... (Intento {retry_count}/{max_retry_attempts})")
                await asyncio.sleep(wait_time)
        
        print("Conexión inactiva, deteniendo receive_audio")

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
        max_init_retries = 3
        init_retry_count = 0
        init_retry_delay = 1.0
        consecutive_errors = 0
        max_consecutive_errors = 5
        error_threshold_time = 2.0  # segundos
        last_error_time = None
        
        while self.connection_active and init_retry_count < max_init_retries:
            try:
                # Obtener dispositivo de salida
                _, output_device_index = get_headphone_devices()
                stream = None
                
                # Intentar inicializar el stream de audio con manejo de errores mejorado
                try:
                    stream = await asyncio.wait_for(
                        asyncio.to_thread(
                            pya.open,
                            format=FORMAT,
                            channels=CHANNELS,
                            rate=RECEIVE_SAMPLE_RATE,
                            output=True,
                            output_device_index=output_device_index,
                        ),
                        timeout=5.0  # Timeout para evitar bloqueos
                    )
                    print("Stream de audio de salida inicializado correctamente")
                except asyncio.TimeoutError:
                    raise RuntimeError("Timeout al inicializar stream de audio de salida")
                
                consecutive_errors = 0
                
                while self.connection_active:
                    try:
                        # Usar timeout para evitar bloqueos en la lectura de la cola
                        audio_data = await asyncio.wait_for(self.audio_in_queue.get(), timeout=1.0)
                        
                        if not self.connection_active:
                            try:
                                self.audio_in_queue.task_done()
                            except ValueError:
                                # Ignorar errores de task_done llamado demasiadas veces
                                pass
                            break
                        
                        # Usar timeout para evitar bloqueos en la reproducción
                        try:
                            await asyncio.wait_for(
                                asyncio.to_thread(stream.write, audio_data),
                                timeout=2.0
                            )
                            try:
                                self.audio_in_queue.task_done()
                            except ValueError:
                                # Ignorar errores de task_done llamado demasiadas veces
                                pass
                            consecutive_errors = 0  # Resetear contador de errores tras éxito
                            last_error_time = None
                        except asyncio.TimeoutError:
                            print("Timeout al reproducir audio, reintentando...")
                            try:
                                self.audio_in_queue.task_done()
                            except ValueError:
                                pass
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                raise RuntimeError("Múltiples timeouts al reproducir audio")
                            continue
                        
                    except asyncio.TimeoutError:
                        # Timeout normal al esperar audio, no es un error
                        if not self.connection_active:
                            break
                    except Exception as e:
                        current_time = time.time()
                        if last_error_time is None:
                            last_error_time = current_time
                        elif current_time - last_error_time < error_threshold_time:
                            consecutive_errors += 1
                        else:
                            consecutive_errors = 1
                        last_error_time = current_time
                        
                        print(f"Error al reproducir audio: {e}")
                        if consecutive_errors >= max_consecutive_errors:
                            print(f"Demasiados errores consecutivos ({consecutive_errors}), reiniciando stream...")
                            break
                        
                        if not self.connection_active:
                            break
                        
                        await asyncio.sleep(0.1)  # Breve pausa antes de reintentar
                
                # Si salimos del bucle por errores pero la conexión sigue activa, reiniciamos el stream
                if self.connection_active and consecutive_errors >= max_consecutive_errors:
                    if stream is not None:
                        try:
                            stream.stop_stream()
                            stream.close()
                            stream = None
                            print("Stream de audio de salida cerrado para reinicio")
                        except Exception as e:
                            print(f"Error al cerrar stream de salida para reinicio: {e}")
                            stream = None
                    # Continuar al siguiente intento sin incrementar init_retry_count
                    await asyncio.sleep(1.0)  # Pausa antes de reiniciar
                    continue
                
                # Si llegamos aquí sin errores o con la conexión inactiva, salimos del bucle de reintentos
                break
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                init_retry_count += 1
                if init_retry_count < max_init_retries:
                    wait_time = init_retry_delay * (2 ** (init_retry_count - 1))  # Backoff exponencial
                    print(f"Error al inicializar stream de audio de salida (intento {init_retry_count}/{max_init_retries}): {e}")
                    print(f"Reintentando en {wait_time} segundos...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"Error fatal al inicializar stream de audio de salida después de {max_init_retries} intentos: {e}")
                    if self.connection_active:
                        print("Iniciando proceso de reconexión debido a errores persistentes de audio de salida")
                        self.connection_active = False
                        asyncio.create_task(self.reconnect())
                    return
            finally:
                if stream is not None:
                    try:
                        stream.stop_stream()
                        stream.close()
                        print("Stream de audio de salida cerrado correctamente")
                    except Exception as e:
                        print(f"Error al cerrar stream de audio de salida: {e}")
        
        if not self.connection_active:
            print("Conexión inactiva, deteniendo reproducción de audio")

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
