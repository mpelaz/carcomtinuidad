# scheduler.py - El Cerebro del Sistema: Parrilla, Hombre Muerto, Conmutación

import config
import requests
import time
import xml.etree.ElementTree as ET
# ASUMIDO: jack_control.py existe para las operaciones LIVE
import jack_control 


# --- Funciones de Utilidad ---

def update_api_state(key, value):
    """Envía un POST a la API para actualizar un estado."""
    try:
        requests.post(f"{config.API_URL}/set_state/{key}", json={'value': value}).raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[SCHED] ERROR al conectar con API: {e}")

def get_current_api_state():
    """Obtiene el estado completo del sistema."""
    try:
        response = requests.get(f"{config.API_URL}/status")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return {} # Fallback

def switch_audio(target_source, block_id=None):
    """
    Gestiona la conmutación de audio.
    Llama a jack_control para LIVE, o a la API para iniciar un bloque automático.
    """
    
    current_state = get_current_api_state()
    current_source = current_state.get('CURRENT_AUDIO_SOURCE')
    
    # La lógica de conmutación de audio debe ir aquí
    if target_source in ['E1_LIVE', 'E2_LIVE']:
        # Realizar la conmutación en JACK
        jack_control.switch_audio(target_source) # LLAMADA REAL
        update_api_state('CURRENT_AUDIO_SOURCE', target_source)
    
    elif target_source == 'BLOCK_PLAYER' and block_id is not None:
        if current_source == f'BLOCK_{block_id}':
             return # Ya está reproduciendo este bloque
             
        try:
            # El Scheduler ORDENA al API central que inicie el bloque
            requests.post(f"{config.API_URL}/block_player/start", json={'block_id': block_id}).raise_for_status()
        except requests.exceptions.RequestException as e:
             print(f"[SCHED] ERROR: No se pudo ordenar el inicio del Bloque {block_id} a la API: {e}")
             
# --- Bucle Principal del Scheduler ---

def main_scheduler_loop():
    print("[SCHED] Scheduler iniciado.")
    
    # Primera acción: Asegurar que la continuidad esté activa (BLOCK 0)
    switch_audio('BLOCK_PLAYER', block_id='0') 
    
    # Lógica de tiempo real y parrilla
    while True:
        try:
            time.sleep(1) 
            # --- Aquí iría la lógica de lectura de jbf.xml (jsf.xml) y parrilla ---
            
        except KeyboardInterrupt:
            print("\n[SCHED] Daemon detenido por usuario.")
            break
        except Exception as e:
            print(f"[SCHED] Error inesperado en el bucle: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main_scheduler_loop()
