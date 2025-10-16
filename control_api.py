import os
import time
from datetime import datetime
import json
# Importar Flask y extensiones
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

# --- CONFIGURACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)

# Configuración de CORS: Permite que cualquier origen (el navegador) acceda a la API
# Esto es esencial para que la web funcione en 192.168.200.5:5000 y acceda a la API
CORS(app) 

# --- VARIABLES DE ESTADO (MOCK/SIMULACIÓN) ---
# En un sistema real, estas funciones obtendrían los datos de un sistema de mensajería (ZeroMQ, Redis)
# o un archivo de estado escrito por el Block Player y el Scheduler.

def get_current_source():
    """Simula la obtención de la fuente de audio actual (ej: BLOCK_0, E1_LIVE)."""
    # En un sistema real, leerías de una variable compartida o una base de datos/archivo.
    try:
        with open('/tmp/audio_source.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "BLOCK_0"

def get_current_time():
    """Obtiene la hora actual del sistema."""
    return datetime.now().strftime('%H:%M:%S')

def get_current_warning():
    """Simula el estado de aviso (Warning) del Scheduler."""
    # Retorna un booleano, True si hay un aviso.
    return False 

def get_program_name_from_file():
    """Lee el nombre real del programa desde el archivo de estado creado por el Block Player."""
    try:
        # El Block Player/Scheduler debe escribir el nombre del programa aquí.
        with open('/tmp/current_program_name.txt', 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Continuidad Automatizada"
    except Exception as e:
        print(f"ERROR reading program name file: {e}")
        return "Error de Lectura"

# --- RUTAS WEB (HTML) ---

@app.route('/')
def index():
    """Sirve la interfaz web HTML."""
    return render_template('index.html')


# --- RUTAS API (JSON) ---

@app.route('/api/status_panel', methods=['GET'])
def get_status_panel():
    """Devuelve el estado actual del sistema (hora, fuente, programa)."""
    
    # === CORRECCIÓN CRÍTICA: DEFINICIÓN DE current_status ===
    # Agrupamos los datos obtenidos de las funciones para definir la variable
    current_status = {
        "source": get_current_source(),
        "time": get_current_time(),
        "warning": get_current_warning(),
        "program_name": get_program_name_from_file(),
    }
    # =======================================================

    response = {
        "source": current_status.get('source', 'N/A'),
        "time": current_status.get('time', '00:00:00'),
        "warning": current_status.get('warning', False),
        "program_name": current_status.get('program_name', 'Continuidad Automatizada')
    }
    
    return jsonify(response)


@app.route('/api/press_button_web', methods=['POST'])
def press_button_web():
    """Recibe la orden de pulsación de botón de la interfaz web."""
    try:
        data = request.json
        studio = data.get('studio')
        color = data.get('color')
        
        # LOGGING SEGURO: Esto aparecerá en tu terminal si la API recibe la petición
        print(f"WEB PRESS RECEIVED: Studio={studio}, Action={color}")
        
        # Aquí DEBE ir tu lógica para comunicar esta acción al Block Player/Scheduler.
        # Por ejemplo, publicando en una cola o escribiendo en un archivo de comando.
        
        # Simulación de respuesta exitosa
        return jsonify({"status": "received", "studio": studio, "color": color}), 200
        
    except Exception as e:
        # Captura errores en el procesamiento JSON o en la lógica interna
        print(f"ERROR processing button press: {e}") 
        return jsonify({"status": "error", "message": str(e)}), 500


# --- ARRANQUE DEL SERVIDOR ---

if __name__ == '__main__':
    # Creación de archivos de estado simulados si no existen (solo para prueba inicial)
    if not os.path.exists('/tmp/audio_source.txt'):
        with open('/tmp/audio_source.txt', 'w') as f:
            f.write("BLOCK_0")
    if not os.path.exists('/tmp/current_program_name.txt'):
        with open('/tmp/current_program_name.txt', 'w') as f:
            f.write("Radio Carcoma Automática")
            
    # Ejecuta el servidor Flask en modo desarrollo
    app.run(host='0.0.0.0', port=5000, debug=True)
