###########################################
# IMPORTACIONES MODULARES
###########################################

import os
import random
import json
import threading
import time
from google import genai
from google.genai import types

################################################
# FUNCIONES CONFIG
###############################################

def get_current_mode():
    """
    Obtiene el modo actual desde config.json
    """
    config = load_config()
    return config.get('current_mode', 'lentes_ai')

def get_mode_file_path(mode):
    """
    Obtiene la ruta del archivo de instrucciones para un modo específico
    """
    mode_map = {
        'agente_psicologo': 'agente_psicologo.txt',
        'lentes_ai': 'lentes_ai.txt',
        'conversacional': 'conversacional.txt'
    }
    if mode not in mode_map:
        raise ValueError("Modo inválido. Debe ser 'agente_psicologo', 'lentes_ai' o 'conversacional'.")
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'instructions')
    return os.path.join(data_dir, mode_map[mode])

def get_mode_instructions(mode):
    """
    Lee y devuelve las instrucciones para un modo específico
    """
    try:
        with open(get_mode_file_path(mode), 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''

def get_chat_history():
    """
    Lee y devuelve el historial de chat
    """
    history_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    history_path = os.path.join(history_dir, 'history_tool.txt')
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ''

def get_combined_instructions():
    """
    Combina las instrucciones del modo actual con el historial previo
    """
    mode = get_current_mode()
    instructions = get_mode_instructions(mode)
    history = get_chat_history()
    return f"{instructions}\nel historial previo es este:\n{history}"

def load_config():
    """
    Carga la configuración desde config.json. Si no existe, crea uno con valores por defecto.
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, 'config.json')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        default_config = {
            "api_keys": [],
            "current_mode": "lentes_ai",
            "voice": "Puck",
            "capture_mode": "camera",
            "logging_enabled": False,
            "instructions": {
                "lentes_ai": "",
                "conversacional": "",
                "agente_psicologo": ""
            }
        }
        save_config(default_config)
        return default_config

def save_config(config):
    """
    Guarda la configuración en config.json
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, 'config.json')
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_key():
    """
    Obtiene una API key aleatoria del config
    """
    config = load_config()
    keys = config.get('api_keys', [])
    return random.choice(keys) if keys else 'Empty data'

def get_actual_voice():
    """
    Obtiene la voz configurada
    """
    config = load_config()
    return config.get('voice', 'Puck')

def write_voice_text(option):
    """
    Actualiza la voz en la configuración
    """
    voices = {
        1: "Puck",
        2: "Charon",
        3: "Kore",
        4: "Fenrir",
        5: "Aoede",
        6: "Leda",
        7: "Orus",
        8: "Zephyr"
    }
    if option not in voices:
        raise ValueError("El número debe estar entre 1 y 8.")
    
    config = load_config()
    config['voice'] = voices[option]
    save_config(config)

####################################
# HISTORY MANAGEMENT
####################################

def save_context(text):
    """
    Guarda el contexto en history_tool.txt (mantenemos este archivo separado por rendimiento)
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, 'history_tool.txt')
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"{text}\n")

def get_history():
    """
    Lee el historial del archivo history_tool.txt
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, 'history_tool.txt')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return lines[-1].rstrip('\n') if lines else 'Empty data'
    except FileNotFoundError:
        return 'Empty data'

####################################
# STATUS MANAGEMENT
####################################

def reset_status_to_reconnect():
    """
    Marca status para reconexión (mantenemos este archivo separado por rendimiento)
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, 'status.txt')
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('reconnect')

def delayed_reconnect(delay=15):
    """
    Espera el tiempo especificado y luego escribe 'reconnect' en status.txt
    """
    def _delayed_write():
        time.sleep(delay)
        reset_status_to_reconnect()
    
    thread = threading.Thread(target=_delayed_write)
    thread.daemon = True
    thread.start()

def get_voice_descriptions():
    """
    Retorna un diccionario con descripciones de las voces disponibles
    """
    return {
        1: {"name": "Puck", "description": "Voz masculina joven y enérgica"},
        2: {"name": "Charon", "description": "Voz masculina profunda y seria"},
        3: {"name": "Kore", "description": "Voz femenina suave y melodiosa"},
        4: {"name": "Fenrir", "description": "Voz masculina poderosa y resonante"},
        5: {"name": "Aoede", "description": "Voz femenina madura y elegante"},
        6: {"name": "Leda", "description": "Voz femenina joven y dulce"},
        7: {"name": "Orus", "description": "Voz masculina cálida y amigable"},
        8: {"name": "Zephyr", "description": "Voz masculina juvenil y dinámica"}
    }

###############################################
# TOOL CONFIGURATION
###############################################

# La configuración de tools se mantiene como objeto Tool para la API live
get_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="print_yes",
                description="Guarda el contexto de la conversacion, para conversaciones futuras.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    required=["query"],
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="En este va todo el resumen de la conversacion"
                        )
                    }
                )
            ),
            types.FunctionDeclaration(
                name="change_voice",
                description="Cambia la voz de Jarvis a una de las voces disponibles.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    required=["voice_number"],
                    properties={
                        "voice_number": types.Schema(
                            type=types.Type.INTEGER,
                            description="Número de voz a usar (1-8):\n1: Puck (joven y enérgica)\n2: Charon (profunda y seria)\n3: Kore (suave y melodiosa)\n4: Fenrir (poderosa)\n5: Aoede (madura y elegante)\n6: Leda (joven y dulce)\n7: Orus (cálida y amigable)\n8: Zephyr (juvenil y dinámica)"
                        )
                    }
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