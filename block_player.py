# block_player.py - Daemon de Reproducción Unificada de Bloques de Parrilla

import config
import os
import time
import random
import threading
import xml.etree.ElementTree as ET
import requests 

# --- Importación de Módulos de Control ---
import jack_control # Requiere las funciones definidas en la tabla
# ----------------------------------------

# --- Variables de Estado Globales ---
JBF_PATH = os.path.join(config.CONFIG_DIR, 'jbf.xml') 
current_block_id = None
playback_thread = None
stop_event = threading.Event() 
current_playback_process = None # Almacena el objeto del proceso asincrónico de mpv/ffmpeg

# --- Lector y Lógica de Bloque (Parseo de jbf.xml) ---

def get_files_from_dir(path):
    """Extrae la lista de archivos de audio de una ruta (absoluta o relativa)."""
    abs_path = path if os.path.isabs(path) else os.path.join(config.BASE_RADIO_DIR, path.lstrip('/'))
    try:
        files = [os.path.join(abs_path, f) for f in os.listdir(abs_path) 
                 if f.endswith(('.mp3', '.ogg', '.wav')) and not f.startswith('.')]
        return files
    except FileNotFoundError:
        print(f"[ERROR PARSE] Directorio no encontrado: {abs_path}")
        return []

def get_block_config(block_id_str):
    """Extrae toda la información de un BLOCKID del jbf.xml."""
    block_id = str(block_id_str)
    try:
        tree = ET.parse(JBF_PATH)
        root = tree.getroot()
        block_element = root.find(f".//BLOCK[@ID='{block_id}']")
        if block_element is None:
            return None
            
        config_data = {
            'ID': block_id,
            'NAME': block_element.get('NAME'),
            'SONGSPERSLOT': int(block_element.get('SONGSPERSLOT', 1)),
            'SHUFFLE': block_element.get('SHUFFLE', '0') == '3', 
            'PROGRAMFILE': block_element.find('PROGRAMFILE').get('PATH') if block_element.find('PROGRAMFILE') is not None else None,
            'SONGSDIRECTORY': block_element.find('SONGSDIRECTORY').get('PATH') if block_element.find('SONGSDIRECTORY') is not None else None,
            'SLOTS_FILES': [],
            'TEXTS_FILES': [],
        }

        # Extracción real de cuñas y textos
        for s_dir in block_element.findall('SLOTSDIRECTORY'):
            config_data['SLOTS_FILES'].extend(get_files_from_dir(s_dir.get('PATH')))
        
        for t_dir in block_element.findall('TEXTSDIRECTORY'):
            config_data['TEXTS_FILES'].extend(get_files_from_dir(t_dir.get('PATH')))

        return config_data

    except (FileNotFoundError, ET.ParseError, AttributeError) as e:
        print(f"[ERROR PARSE] Fallo al leer jbf.xml o extraer datos del bloque {block_id}: {e}")
        return None

# --- Motor de Reproducción (El Thread) ---

def run_playback_engine(block_config):
    """Ejecuta la reproducción del bloque con intercalación de cuñas."""
    global current_playback_process
    
    print(f"\n[ENGINE] INICIANDO: Bloque ID {block_config['ID']} - {block_config['NAME']}")
    jack_control.switch_audio('BLOCK_PLAYER') # Conmutar JACK a la entrada del reproductor (Strip 5)
    
    # 1. Determinar Archivos
    main_files = []
    is_looping_mode = False
    
    if block_config['PROGRAMFILE']:
        main_files = [block_config['PROGRAMFILE']]
    elif block_config['SONGSDIRECTORY']:
        main_files = get_files_from_dir(block_config['SONGSDIRECTORY'])
        is_looping_mode = True
        if block_config['SHUFFLE']:
            random.shuffle(main_files)
    
    if not main_files:
        print(f"[ENGINE] ERROR: Bloque {block_config['ID']} sin archivos de audio. Deteniendo hilo.")
        return

    # 2. Lógica de Intercalación
    songs_per_slot = block_config['SONGSPERSLOT']
    songs_played_since_slot = 0
    
    while not stop_event.is_set():
        audio_queue = list(main_files)

        for i, file_path in enumerate(audio_queue):
            if stop_event.is_set():
                break

            # A. Intercalación (Slot / Cuña / Texto)
            if (songs_played_since_slot >= songs_per_slot) or (i == 0):
                if block_config['SLOTS_FILES']:
                    slot_path = random.choice(block_config['SLOTS_FILES'])
                    jack_control.play_file_sync(slot_path) # LLAMADA REAL SINCRÓNICA
                if block_config['TEXTS_FILES']:
                    text_path = random.choice(block_config['TEXTS_FILES'])
                    jack_control.play_file_sync(text_path) # LLAMADA REAL SINCRÓNICA
                    
                songs_played_since_slot = 0
            
            # B. Reproducir Audio Principal (Asincrónico/Loop)
            if not stop_event.is_set():
                current_playback_process = jack_control.start_playback_async(file_path, is_looping_mode)
                
                # Esperar a que el proceso de reproducción termine de forma natural
                # Esto es clave: la función 'wait' del objeto proceso debe ser manejada
                # dentro de jack_control o aquí para garantizar la sincronicidad.
                
                # Ejemplo de espera (asumiendo que jack_control tiene una función de espera)
                # jack_control.wait_for_process_to_finish(current_playback_process)
                
                songs_played_since_slot += 1
        
        # C. Lógica de Fin de Lista
        if not is_looping_mode:
            break
        else:
            # Reiniciar la cola (Continua la reproducción en bucle)
            if block_config['SHUFFLE']:
                random.shuffle(main_files)
    
    # Detener cualquier proceso de playback activo al finalizar
    if current_playback_process:
        jack_control.stop_playback_async(current_playback_process)
        current_playback_process = None
        
    if not stop_event.is_set():
        requests.post(f"{config.API_URL}/set_state/BLOCK_PLAYER_STATE", json={'value': 'IDLE'})
    print(f"[ENGINE] Bloque ID {block_config['ID']} detenido limpiamente.")


# --- Funciones de Control del Daemon (Llamadas por la API) ---

def stop_current_playback():
    """Señala al hilo de reproducción que debe terminar y espera su finalización."""
    global playback_thread, current_block_id, current_playback_process

    if playback_thread and playback_thread.is_alive():
        print(f"[CONTROL] Orden de detención para Bloque ID {current_block_id}...")
        stop_event.set()
        
        if current_playback_process:
            jack_control.stop_playback_async(current_playback_process)
            current_playback_process = None
        
        playback_thread.join(timeout=5) 
        playback_thread = None
        current_block_id = None
        requests.post(f"{config.API_URL}/set_state/BLOCK_PLAYER_STATE", json={'value': 'IDLE'})


def start_block(block_id):
    """Detiene la reproducción actual e inicia el bloque solicitado."""
    global playback_thread, current_block_id

    stop_current_playback()
    config_data = get_block_config(block_id)
    if not config_data:
        # Fallback a Continuidad (Bloque 0)
        print(f"[CONTROL] Bloque {block_id} no válido. Volviendo a Continuidad (0).")
        return start_block('0') 

    current_block_id = block_id
    stop_event.clear()
    
    playback_thread = threading.Thread(target=run_playback_engine, args=(config_data,))
    playback_thread.daemon = True
    playback_thread.start()
    
    requests.post(f"{config.API_URL}/set_state/BLOCK_PLAYER_STATE", json={'value': f'PLAYING:{block_id}'})
    requests.post(f"{config.API_URL}/set_state/CURRENT_AUDIO_SOURCE", json={'value': f'BLOCK_{block_id}'})


def main_daemon_loop():
    """El bucle principal del daemon."""
    print("[CONTROL] block_player.py Daemon iniciado. Listo para recibir comandos.")
    
    while True:
        try:
            time.sleep(1) 
        except KeyboardInterrupt:
            stop_current_playback()
            print("\n[CONTROL] Daemon detenido por usuario.")
            break

if __name__ == '__main__':
    main_daemon_loop()
