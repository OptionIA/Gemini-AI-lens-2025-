###########################################
# IMPORTACIONES MODULARES
###########################################

import os
import random
from google import genai
from google.genai import types

################################################
# FUNCIONES GET TEXT
###############################################
def get_text_from_file(filename):
    """
    Reads the content of a text file located in the 'data' directory and returns its content.
    If the filename is 'history_tool', returns only the last line. For dont saturate the memory.
    If the file is empty, returns 'Empety data'. for dont saturate the model with errors.
    The 'data' directory is located at the same level as this script.
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, filename)
    with open(file_path, 'r', encoding='utf-8') as f:
        if filename == 'history_tool':
            lines = f.readlines()
            return lines[-1].rstrip('\n') if lines else 'Empety data'
        content = f.read()
        return content if content.strip() else 'Empety data'

def get_key():
    """
    Reads all API keys from 'api.txt' in the 'data' directory, selects one at random, and returns it.
    Each line in 'api.txt' should contain one API key.
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, 'api.txt')
    with open(file_path, 'r', encoding='utf-8') as f:
        keys = [line.strip() for line in f if line.strip()]
    if not keys:
        return 'Empety data'
    return random.choice(keys)

def save_context(text):
    """
    Appends the given text as a new line to the 'history_tool.txt' file in the 'data' directory.
    """
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    file_path = os.path.join(data_dir, 'history_tool.txt')
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(f"{text}\n")

def get_combined_instructions():
    """
    Combines the system instructions from system_inst.txt with the history from history_tool.txt
    to create a complete context for the model.
    Returns the combined instructions as a single string.
    """
    system_instructions = get_text_from_file('system_inst.txt')
    history = get_text_from_file('history_tool.txt')
    
    combined = f"{system_instructions}\n\nPrevious context:\n{history}"
    return combined

###############################################
# VARIABLES IMPORTABLES
###############################################

# La configuración de tools debe mantenerse como objeto Tool para la API live
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
            )
        ]
    )
]
