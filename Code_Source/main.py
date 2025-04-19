import asyncio
import base64
import io
import cv2
import pyaudio
import PIL.Image
import time
import datetime
from google import genai
from google.genai import types  # Añadimos la importación de types
from funciones.basic_def import get_key, save_context, get_combined_instructions
from funciones.audio_def import (
    FORMAT, CHANNELS, SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE, CHUNK_SIZE,
    setup_audio_input, setup_audio_output, listen_audio, play_audio
)

# Variables globales
GOOGLE_API_KEY = get_key()
MODEL = "models/gemini-2.0-flash-live-001"
COMBINED_INSTRUCTIONS = get_combined_instructions()

# Configuracion de tools
TOOLS = [{
    "function_declarations": [{
        "name": "print_yes",
        "description": "Guarda el contexto de la conversacion, para conversaciones futuras.",
        "parameters": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "En este va todo el resumen de la conversacion"
                }
            }
        },
        "responses": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "Resultado de la operación"
                }
            }
        }
    }]
}]

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
CONFIG = {
    "generation_config": {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "candidate_count": 1,
        "stop_sequences": [],
        "max_output_tokens": 2048,
        "stream": True
    },
    "contents": [],
    "tools": TOOLS,
    "safety_settings": SAFETY_SETTINGS,
    "system_instruction": COMBINED_INSTRUCTIONS
}

# Inicializacion de PyAudio
pya = pyaudio.PyAudio()

class AudioLoop:
    def __init__(self):
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
        self.last_instructions_refresh = time.time()
        self.refresh_instructions_interval = 10

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
        img = PIL.Image.fromarray(frame)
        img.thumbnail([1024, 1024])
        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)
        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode()}

    async def get_frames(self):
        cap = await asyncio.to_thread(cv2.VideoCapture, 0)
        
        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break
            
            await self.out_queue.put(frame)

        cap.release()

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
            except Exception as e:
                print(f"Error en send_realtime: {e}")
                await asyncio.sleep(0.1)

    async def listen_audio(self):
        """Inicializa y gestiona la entrada de audio usando las funciones modularizadas."""
        self.audio_stream = await setup_audio_input(pya, self.out_queue)
        await listen_audio(self.audio_stream, self.out_queue)

    async def play_audio(self):
        """Inicializa y gestiona la salida de audio usando las funciones modularizadas."""
        stream = await setup_audio_output(pya)
        await play_audio(stream, self.audio_in_queue)

    async def receive_audio(self):
        while True:
            turn = self.session.receive()
            full_text = ""
            tool_call_detected = False
            first_response_received = False
            
            async for response in turn:
                if not first_response_received and self.last_send_timestamp is not None:
                    first_response_received = True
                    current_time = time.time()
                    self.ping_ms = round((current_time - self.last_send_timestamp) * 1000)
                    print(f"\n[Ping: {self.ping_ms}ms]")

                # Manejo de function calls mejorado
                if hasattr(response, "tool_call") and response.tool_call is not None:
                    tool_call_detected = True
                    for func_call in response.tool_call.function_calls:
                        args_dict = func_call.args
                        result_string = args_dict.get("query")
                        if result_string:
                            print(f"\n[Function Call] {result_string[:50]}..." if len(result_string) > 50 else f"\n[Function Call] {result_string}")
                            
                            # Crear respuesta de la función
                            tool_response = types.LiveClientToolResponse(
                                function_responses=[
                                    types.FunctionResponse(
                                        name=func_call.name,
                                        response={"result": "ok"},
                                        id=getattr(func_call, "id", "default_id")
                                    )
                                ]
                            )
                            
                            # Enviar la respuesta
                            await self.session.send(input=tool_response)
                            
                            # Registrar para el historial
                            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_entry = f"[{timestamp}] {func_call.name}: {result_string}\n"
                            try:
                                save_context(new_entry)
                                print(f"\n[Guardado en historial] {func_call.name}")
                            except Exception as e:
                                print(f"Error guardando en historial: {e}")
                            
                            # Continuar la conversación
                            await self.session.send(input="Función ejecutada correctamente. ¿Hay algo más en lo que pueda ayudarte?")

                # Procesar audio y texto
                if data := response.data:
                    await self.audio_in_queue.put(data)
                    continue
                if text := response.text:
                    full_text += text
                    print(text, end="")
            
            print()
    
    async def _process_tool_responses(self, tool_calls):
        for tool_call in tool_calls:
            try:
                response_text = f"Procesado: {tool_call['result'][:30]}..." if len(tool_call['result']) > 30 else f"Procesado: {tool_call['result']}"
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history_entry = f"[{timestamp}] {tool_call['name']}: {tool_call['result']}\n"
                
                try:
                    save_context("history_tool.txt", [history_entry])
                    print(f"\n[Guardado en history_tool.txt] {tool_call['name']}")
                except Exception as e:
                    print(f"Error escribiendo en history_tool.txt: {e}")
                
            except Exception as e:
                print(f"Error al procesar la función: {e}")

    async def run(self):
        self.reconnect_attempts = 0
        self.connection_active = True
        
        while self.reconnect_attempts < self.max_reconnect_attempts:
            try:
                print(f"Conectando a Gemini... {self.reconnect_attempts+1}/{self.max_reconnect_attempts}")
                
                # Actualizar las instrucciones antes de cada conexión
                global COMBINED_INSTRUCTIONS
                COMBINED_INSTRUCTIONS = get_combined_instructions()
                updated_config = CONFIG.copy()
                updated_config["system_instruction"] = COMBINED_INSTRUCTIONS
                
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
                            raise
                        except Exception as e:
                            print(f"Error en tarea {task_name}: {e}")
                            if self.connection_active:
                                self.connection_active = False
                                raise asyncio.CancelledError(f"Error en {task_name}, reconexión necesaria")

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
                except Exception:
                    pass
        
        print("Sistema de reconexión finalizado")

    async def _monitor_connection(self):
        """Monitorea el estado de la conexión y detecta desconexiones."""
        check_interval = 5  # intervalo de verificación en segundos
        ping_timeout = 30   # tiempo de espera máximo sin actividad
        
        last_activity_time = time.time()
        
        while self.connection_active:
            current_time = time.time()
            
            # Actualizar el tiempo de última actividad
            if self.last_send_timestamp is not None and self.last_send_timestamp > last_activity_time:
                last_activity_time = self.last_send_timestamp
            
            # Verificar desconexión
            if current_time - last_activity_time > ping_timeout:
                print(f"\nDetectada posible desconexión: Sin actividad por {ping_timeout} segundos")
                try:
                    self.last_send_timestamp = time.time()
                    await self.session.send(input=".", end_of_turn=True)
                    last_activity_time = time.time()
                except Exception as e:
                    print(f"Error al verificar conexión: {e}")
                    self.connection_active = False
                    raise asyncio.CancelledError("Connection lost")
            
            await asyncio.sleep(check_interval)

if __name__ == "__main__":
    try:
        main = AudioLoop()
        asyncio.run(main.run())
    except KeyboardInterrupt:
        print("\nChat terminado por el usuario.")
    finally:
        pya.terminate()
        print("Recursos de audio liberados.")
