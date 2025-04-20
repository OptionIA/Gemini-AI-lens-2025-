import os
import time 
from colorama import init, Fore, Back, Style
import sys
import math
import threading
import subprocess

init(autoreset=True)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_golden_rainbow(text, is_input=False):
    # Golden color variations
    golden_colors = [
        (255, 215, 0),  # Golden
        (218, 165, 32), # GoldenRod
        (255, 223, 0),  # Gold
        (238, 232, 170) # PaleGoldenRod
    ]
    
    width = 63  # Width of our interface
    position = 0
    
    for char in text:
        if char != '\n':
            color_index = int((position / width) * len(golden_colors))
            color_index = min(color_index, len(golden_colors) - 1)
            color = golden_colors[color_index]
            print(f"\033[38;2;{color[0]};{color[1]};{color[2]}m{char}", end='')
            position += 1
        else:
            print(char, end='')
            position = 0  # Reset position for new lines
    
    # Don't print newline if this is an input prompt
    if not is_input:
        print(Style.RESET_ALL)

def get_input(prompt):
    print_golden_rainbow(prompt, is_input=True)
    return input()

def print_header():
    header = """
---------------------------------------------------------------
|                                                             |
|      ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗     █████╗ ██╗ |
|      ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝    ██╔══██╗██║ |
|      ██║███████║██████╔╝██║   ██║██║███████╗    ███████║██║ |
| ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║    ██╔══██║██║ |
| ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║    ██║  ██║██║ |
|  ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝    ╚═╝  ╚═╝╚═╝ |
| MADE BY: OptionIA                                           |
|-------------------------------------------------------------|"""
    print_golden_rainbow(header)

def start_jarvis(mode):
    while True:
        clear_screen()
        print_header()
        print_golden_rainbow("| [1] Volver Atras                                            |")
        print_golden_rainbow("| [2] Salir                                                   |")
        print_golden_rainbow("|-------------------------------------------------------------|")
        print_golden_rainbow(f"| [SYS] Iniciando Jarvis ({mode})...")
        time.sleep(0.5)
        print_golden_rainbow("| [SYS] V1.1.7 - 2025/19/4 Snapshot 1")
        time.sleep(0.4)
        print_golden_rainbow("| [SYS] Desarrollado por OptionIA")
        time.sleep(0.7)
        print_golden_rainbow("| [SYS] Iniciando...")
        print_golden_rainbow("|-------------------------------------------------------------|")
        
        # Guardar el modo actual en el archivo
        with open('data/current_mode.txt', 'w', encoding='utf-8') as f:
            f.write(mode.lower())
            
        # Clear status file before starting
        with open('data/status.txt', 'w') as f:
            f.write('')
            
        reconnecting = False
            
        while True:
            try:
                # Start main.py as a subprocess
                process = subprocess.Popen([sys.executable, 'main.py'])
                
                # Loop para verificar el estado del proceso y el archivo status.txt
                while True:
                    try:
                        # Verificar si el proceso terminó
                        if process.poll() is not None and not reconnecting:
                            return  # Salir al menú si el proceso terminó normalmente
                            
                        # Verificar status.txt
                        with open('data/status.txt', 'r') as f:
                            status = f.read().strip()
                        
                        if status == 'reconnect':
                            reconnecting = True
                            # Clear the status file
                            with open('data/status.txt', 'w') as f:
                                f.write('')
                            # Kill the process if it's still running
                            if process.poll() is None:
                                process.kill()
                                process.wait()
                            # Mostrar secuencia completa de inicio
                            clear_screen()
                            print_header()
                            print_golden_rainbow("| [1] Volver Atras                                            |")
                            print_golden_rainbow("| [2] Salir                                                   |")
                            print_golden_rainbow("|-------------------------------------------------------------|")
                            print_golden_rainbow(f"| [SYS] Iniciando Jarvis ({mode})...")
                            time.sleep(0.5)
                            print_golden_rainbow("| [SYS] V1.1.7 - 2025/19/4 Snapshot 1")
                            time.sleep(0.6)
                            print_golden_rainbow("| [SYS] Desarrollado por OptionIA")
                            time.sleep(0.3)
                            print_golden_rainbow("| [SYS] Iniciando...")
                            print_golden_rainbow("|-------------------------------------------------------------|")
                            break  # Salir del loop interno para reiniciar
                            
                        time.sleep(0.1)  # Pequeña pausa para no consumir CPU
                        
                    except KeyboardInterrupt:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                        return
                    except:
                        pass
                
                if reconnecting:
                    reconnecting = False
                    continue  # Reiniciar el proceso
                    
                break  # Si no es reconexión, salir al menú
                    
            except KeyboardInterrupt:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                return
            except:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                return
        
        return  # Volver al menú principal

def main_menu():
    while True:
        clear_screen()
        print_header()
        print_golden_rainbow("| [1] Iniciar Jarvis Default    [3] Iniciar Jarvis Normal     |")
        print_golden_rainbow("| [2] Iniciar Jarvis Psicologo  [4] Configuracion Jarvis      |")
        print_golden_rainbow("|-------------------------------------------------------------|")
        option = get_input("|_>>>: ")
        
        if option in ['1', '2', '3']:
            jarvis_mode = {
                '1': 'Default',
                '2': 'Psicologo',
                '3': 'Normal'
            }[option]
            start_jarvis(jarvis_mode)
        elif option == '4':
            config_menu()
        else:
            print_golden_rainbow("| [SYS] Opción inválida. Intente nuevamente...")
            time.sleep(2)

def config_menu():
    from funciones.basic_def import load_config, save_config, write_voice_text
    while True:
        clear_screen()
        print_header()
        print_golden_rainbow("| [1] Configurar API Key          [3] Borrar Contexto         |")
        print_golden_rainbow("| [2] Configurar User Instruction [4] Cambiar Modo            |")
        print_golden_rainbow("| [5] Creditos & Donaciones       [6] Configurar Voz          |")
        print_golden_rainbow("| [7] Volver                                                  |")
        print_golden_rainbow("|-------------------------------------------------------------|")
        option = get_input("|_>>>: ")
        
        config = load_config()
        
        if option == '1':
            print_golden_rainbow("| [SYS] Inserte sus api keys separadas por comas (1,2,3,4...) |")
            api_keys = get_input("|_>>>: ")
            config['api_keys'] = [key.strip() for key in api_keys.split(',')]
            save_config(config)
            print_golden_rainbow("| [SYS] Guardadas correctamente, presione enter para volver   |")
            get_input("|_>>>: ")

        elif option == '3':
            # Borrar contenido del historial
            try:
                with open('data/history_tool.txt', 'w', encoding='utf-8') as f:
                    f.write('')
                print_golden_rainbow("| [SYS] Historial borrado correctamente                       |")
            except:
                print_golden_rainbow("| [SYS] Error al borrar el historial                         |")
            print_golden_rainbow("| [SYS] Presione enter para continuar                        |")
            get_input("|_>>>: ")

        elif option == '4':
            # Cambiar modo de ejecución
            clear_screen()
            print_header()
            print_golden_rainbow("| [1] Modo Cámara                                            |")
            print_golden_rainbow("| [2] Modo Pantalla                                          |")
            print_golden_rainbow("|-------------------------------------------------------------|")
            modo = get_input("|_>>>: ")
            
            if modo in ['1', '2']:
                nuevo_modo = "camera" if modo == '1' else "screen"
                config['capture_mode'] = nuevo_modo
                save_config(config)
                print_golden_rainbow(f"| [SYS] Modo de captura cambiado a: {nuevo_modo.title()}        |")
            else:
                print_golden_rainbow("| [SYS] Opción inválida                                      |")
            print_golden_rainbow("| [SYS] Presione enter para continuar                        |")
            get_input("|_>>>: ")
                
        elif option == '5':
            # Mostrar créditos y donaciones
            clear_screen()
            print_header()
            print_golden_rainbow("| [SYS] Desarrollado por OptionIA                             |")
            print_golden_rainbow("| [SYS] Version: V1.1.7 - 2025/19/4 Snapshot 1               |")
            print_golden_rainbow("|-------------------------------------------------------------|")
            print_golden_rainbow("| [SYS] Donaciones:                                          |")
            print_golden_rainbow("| [SYS] - ETH: 0x0000000000000000000000000000000000000000   |")
            print_golden_rainbow("| [SYS] - BTC: bc1q000000000000000000000000000000000000     |")
            print_golden_rainbow("| [SYS] - PayPal: Unknow                                    |")
            print_golden_rainbow("|-------------------------------------------------------------|")
            print_golden_rainbow("| [SYS] Contacto: github.com/optionIA                        |")
            print_golden_rainbow("| [SYS] Presione enter para volver                           |")
            get_input("|_>>>: ")

        elif option == '6':
            # Configurar voz
            clear_screen()
            print_header()
            print_golden_rainbow("| [SYS] Voces disponibles:                                    |")
            print_golden_rainbow("| [1] Puck                     [5] Aoede                      |")
            print_golden_rainbow("| [2] Charon                   [6] Leda                       |")
            print_golden_rainbow("| [3] Kore                     [7] Orus                       |")
            print_golden_rainbow("| [4] Fenrir                   [8] Zephyr                     |")
            print_golden_rainbow("|-------------------------------------------------------------|")
            voice_option = get_input("|_>>>: ")
            
            try:
                if voice_option in ['1', '2', '3', '4', '5', '6', '7', '8']:
                    write_voice_text(int(voice_option))
                    voices = {
                        '1': 'Puck',
                        '2': 'Charon',
                        '3': 'Kore',
                        '4': 'Fenrir',
                        '5': 'Aoede',
                        '6': 'Leda',
                        '7': 'Orus',
                        '8': 'Zephyr'
                    }
                    print_golden_rainbow(f"| [SYS] Voz cambiada a: {voices[voice_option]}                          |")
                else:
                    print_golden_rainbow("| [SYS] Opción inválida                                      |")
            except:
                print_golden_rainbow("| [SYS] Error al cambiar la voz                              |")
            print_golden_rainbow("| [SYS] Presione enter para continuar                        |")
            get_input("|_>>>: ")
            
        elif option == '7':
            return

if __name__ == "__main__":
    main_menu()