# config.py - Configuración central de Radio Carcoma

# --- 1. CONFIGURACIÓN DEL SISTEMA Y RUTAS ---
BASE_RADIO_DIR = '/radio' 
LOGS_DIR = 'logs'
ARCHIVE_SUBDIR = 'archivo'
BORRADOS_SUBDIR = 'borrados'
CONFIG_DIR = '.' # Directorio donde se encuentra jbf.xml
TEMP_RECORDING_FILE = '/tmp/temp_recording.mp3'

# --- 2. CONFIGURACIÓN DE LA COMUNICACIÓN (API/RED) ---
API_HOST = '0.0.0.0'
API_PORT = 5000
API_URL = f"http://{API_HOST}:{API_PORT}/api"

# --- 3. CONFIGURACIÓN DE AUDIO (Necesario para jackd) ---
JACK_COMMAND = 'jackd -d alsa -d hw:0 -r 44100 -p 1024 -n 3'
JACK_MIXER_COMMAND = 'jack_mixer'

# --- 4. CONFIGURACIÓN DE HARDWARE (Módulo CH340) ---
HARDWARE_SERIAL_PORT = '/dev/ttyUSB0'
HARDWARE_BAUD_RATE = 9600
HARDWARE_TIMEOUT = 0.5

# Mapping de Relés (Salidas: Luces de Aviso, Tally)
# Las luces deben reflejar el estado del sistema. El comando debe incluir \r\n
HW_RELAY_MAPPING = {
    # Relé que se activa cuando el Scheduler está en modo WARNING
    'SCHEDULER_WARNING_LIGHT': {'RELAY_ID': 1, 'CMD_ON': 'AT+RELAY1=1\r\n', 'CMD_OFF': 'AT+RELAY1=0\r\n'},
    # Tally Light para Estudio 1 (LIVE)
    'TALLY_E1_LIVE': {'RELAY_ID': 2, 'CMD_ON': 'AT+RELAY2=1\r\n', 'CMD_OFF': 'AT+RELAY2=0\r\n'},
    # Tally Light para Estudio 2 (LIVE)
    'TALLY_E2_LIVE': {'RELAY_ID': 3, 'CMD_ON': 'AT+RELAY3=1\r\n', 'CMD_OFF': 'AT+RELAY3=0\r\n'},
}

# Mapping de Entradas (Botones: Cortar/Pedir Paso/Salto)
HW_INPUT_MAPPING = {
    # Botón Rojo Estudio 1 (Pulsar para ir a LIVE / Cortar si ya está LIVE)
    'BUTTON_RED_E1': {'INPUT_ID': 1, 'CMD_STATUS': 'AT+INPUT1?\r\n', 'TRIGGER_STATE': 'LOW'}, # LOW significa pulsado
    # Botón Rojo Estudio 2
    'BUTTON_RED_E2': {'INPUT_ID': 2, 'CMD_STATUS': 'AT+INPUT2?\r\n', 'TRIGGER_STATE': 'LOW'},
    # Botón Verde (Salto de Bloque / Hombre Muerto)
    'BUTTON_GREEN': {'INPUT_ID': 3, 'CMD_STATUS': 'AT+INPUT3?\r\n', 'TRIGGER_STATE': 'LOW'},
}

# --- 5. CONFIGURACIÓN DE TIEMPOS ---
JACK_WAIT_TIME = 5 
API_WAIT_TIME = 3

# --- CONFIGURACIÓN DE JACK MIXER STRIPS Y VOLUMENES ---
# Mapeo de strips en jack-mixer: Asegúrate de que estos IDs coincidan con tu mixer
E1_STRIP = 1
E2_STRIP = 2
BLOCK_PLAYER_STRIP = 3 # Nuevo strip para la reproducción unificada (Continuidad/Bloques)

# Valores de volumen
VOLUME_ON = 0.0       # Volumen activo
VOLUME_OFF = -100.0   # Volumen apagado

# FFMPEG
FFMPEG_BITRATE = '192k'
