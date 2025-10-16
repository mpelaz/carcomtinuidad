# hardware_daemon.py - Daemon de Hardware (Control CH340/AT Commands)

import config
import requests
import time
import serial
import threading

# --- Inicialización Serial y Estado ---
ser = None
try:
    # Intenta abrir el puerto serial. Si falla, el daemon solo imprimirá logs.
    ser = serial.Serial(
        config.HARDWARE_SERIAL_PORT, 
        config.HARDWARE_BAUD_RATE, 
        timeout=config.HARDWARE_TIMEOUT
    )
    print(f"[HW] Puerto serial {config.HARDWARE_SERIAL_PORT} abierto.")
except serial.SerialException as e:
    print(f"[HW] ERROR: No se pudo abrir el puerto serial CH340: {e}. El daemon operará en modo LOG.")

# Caché local para evitar spamming de la API
last_input_state = {key: 'HIGH' for key in config.HW_INPUT_MAPPING.keys()}

def send_command(command, expected_response='OK'):
    """Envía un comando AT al módulo serial."""
    if not ser:
        # print(f"[HW_LOG] Cmd OUT: {command.strip()}")
        return True 
    # ... (Resto de la lógica serial intacta)
    try:
        ser.write(command.encode())
        response = ser.readline().decode().strip()
        if expected_response and expected_response not in response:
            print(f"[HW_ERROR] Cmd '{command.strip()}' falló. Resp: '{response}'")
            return False
        return True
    except Exception as e:
        print(f"[HW_ERROR] Fallo en comunicación serial: {e}")
        return False

def get_input_status(input_key):
    """Consulta el estado de una entrada digital (INPUT1?) y devuelve 'LOW' o 'HIGH'."""
    mapping = config.HW_INPUT_MAPPING[input_key]
    command = mapping['CMD_STATUS']
    
    if not ser:
        return 'HIGH' 
    # ... (Resto de la lógica serial intacta)
    try:
        ser.write(command.encode())
        response = ser.readline().decode().strip()
        if 'LOW' in response:
            return 'LOW'
        elif 'HIGH' in response:
            return 'HIGH'
        return 'HIGH'
    except Exception as e:
        # print(f"[HW_ERROR] Fallo al leer input {input_key}: {e}")
        return 'HIGH' 


def notify_api_button_press(button_key):
    """Notifica al control_api.py de una pulsación de botón de acción."""
    
    if 'E1' in button_key:
        studio_id = 'E1'
    elif 'E2' in button_key:
        studio_id = 'E2'
    else:
        studio_id = 'GENERAL' 
    
    color = 'verde' if 'GREEN' in button_key else 'rojo'
    
    try:
        # CORRECCIÓN DE ENDPOINT: Usamos config.API_URL + /press_button_web
        requests.post(f"{config.API_URL}/press_button_web", 
                      json={'studio': studio_id, 'color': color}).raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"[HW_ACTION] ERROR al notificar a la API: {e}")

def update_relay_state(api_state):
    """Actualiza las luces/relés según el estado del sistema (COMANDOS AT)."""
    
    # 1. Luz de Advertencia (Warning)
    warning_mapping = config.HW_RELAY_MAPPING['SCHEDULER_WARNING_LIGHT']
    is_warning = api_state.get('SCHEDULER_WARNING_STATE', False)
    command = warning_mapping['CMD_ON'] if is_warning else warning_mapping['CMD_OFF']
    send_command(command, expected_response='OK')

    # 2. Tally E1
    tally_e1_mapping = config.HW_RELAY_MAPPING['TALLY_E1_LIVE']
    is_e1_live = api_state.get('CURRENT_AUDIO_SOURCE') == 'E1_LIVE'
    command = tally_e1_mapping['CMD_ON'] if is_e1_live else tally_e1_mapping['CMD_OFF']
    send_command(command, expected_response='OK')
    
    # 3. Tally E2
    tally_e2_mapping = config.HW_RELAY_MAPPING['TALLY_E2_LIVE']
    is_e2_live = api_state.get('CURRENT_AUDIO_SOURCE') == 'E2_LIVE'
    command = tally_e2_mapping['CMD_ON'] if is_e2_live else tally_e2_mapping['CMD_OFF']
    send_command(command, expected_response='OK')


def main_hardware_loop():
    print("[HW] Hardware Daemon iniciado. Chequeando estados...")
    
    while True:
        try:
            # 1. Obtener estado del sistema de la API
            try:
                # CORRECCIÓN DE ENDPOINT: Usamos config.API_URL + /status
                api_response = requests.get(f"{config.API_URL}/status")
                api_response.raise_for_status()
                current_state = api_response.json()
            except requests.exceptions.RequestException:
                time.sleep(1) 
                continue
            
            # 2. Actualizar Relés (Tally, Warning)
            update_relay_state(current_state)

            # 3. Leer Entradas (Botones)
            for button_key, mapping in config.HW_INPUT_MAPPING.items():
                
                current_input_status = get_input_status(button_key)
                
                # Detección de pulsación
                if current_input_status == mapping['TRIGGER_STATE'] and last_input_state[button_key] != mapping['TRIGGER_STATE']:
                    notify_api_button_press(button_key)
                    
                last_input_state[button_key] = current_input_status
            
            time.sleep(0.2) 
            
        except KeyboardInterrupt:
            print("\n[HW] Daemon detenido por usuario. Cerrando puerto serial.")
            if ser:
                ser.close()
            break
        except Exception as e:
            print(f"[HW] Error inesperado en el bucle: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main_hardware_loop()
