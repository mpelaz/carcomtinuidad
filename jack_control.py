# jack_control.py - Módulo de Control de Audio JACK/MPV/FFMPEG (FINAL)

import subprocess
import os
import threading
import config # Importa la configuración

# ASUNCIONES DE CONFIGURACIÓN FALTANTE:
# Debes tener estas variables definidas en config.py para que switch_audio funcione
# config.E1_STRIP = 1
# config.E2_STRIP = 2
# config.BLOCK_PLAYER_STRIP = 3 # Nuevo nombre para CONTINUIDAD
# config.VOLUME_ON = 0.0
# config.VOLUME_OFF = -100.0
# config.FFMPEG_BITRATE = '192k'

# --- Utilidades de Mixer ---

def jack_mixer_set_volume(strip_num, volume_db):
    """Ajusta el volumen de un strip en jack_mixer."""
    try:
        # Usamos jack_mixer_client, asumiendo que usa guion bajo si el binario es jack_mixer
        subprocess.run(['jack-mixer-client', '--set-fader', str(strip_num), str(volume_db)], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"[JACK_CONTROL] Error al ajustar fader: {e}")
        pass

# --- Funciones de Reproducción de Audio (para block_player.py) ---

def _get_mpv_command(file_path, async_mode=False):
    """Genera el comando base de MPV para audio a través de JACK."""
    command = [
        'mpv',
        '--no-terminal',
        '--audio-driver=jack',
        '--audio-client-name=Block_Player_Output', # Cliente para la reproducción de bloques
        '--volume=100',
        '--idle=no' # No esperar
    ]
    if not async_mode:
        command.append('--no-input-default-bindings') # Evita que el usuario interrumpa la cuña
    
    command.append(file_path)
    return command

def play_file_sync(file_path):
    """
    Reproduce un archivo de audio (Cuña/Texto) de forma sincronizada.
    Bloquea la ejecución hasta que el archivo termina.
    """
    command = _get_mpv_command(file_path, async_mode=False)
    try:
        # Ejecución SÍNCRONA
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Error al reproducir archivo sincrónico {file_path}: {e}")
        return False

def start_playback_async(file_path):
    """
    Inicia la reproducción de un programa/música en segundo plano (Asíncrono).
    Devuelve el objeto del proceso.
    """
    command = _get_mpv_command(file_path, async_mode=True)
    try:
        # Ejecución ASÍNCRONA
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return process
    except Exception as e:
        print(f"Error al iniciar reproducción asíncrona {file_path}: {e}")
        return None

def stop_playback_async(process_obj):
    """
    Detiene un proceso de reproducción asíncrono.
    """
    if process_obj and process_obj.poll() is None:
        try:
            process_obj.terminate() # Intenta terminar limpiamente
            process_obj.wait(timeout=1) # Espera breve
            if process_obj.poll() is None:
                 process_obj.kill() # Mata si no termina
        except Exception as e:
             print(f"Error al intentar detener el proceso: {e}")

# --- Funciones de Grabación (Existentes) ---

def start_ffmpeg_recording(recording_name, temp_file):
    """Inicia la grabación del puerto Aux 1 (Clean) del jack-mixer."""
    # Nota: Se asume que config.FFMPEG_BITRATE existe
    command = [
        'ffmpeg',
        '-f', 'jack',
        '-i', 'jack-mixer:aux_1_out', 
        '-acodec', 'libmp3lame',
        '-b:a', config.FFMPEG_BITRATE,
        '-metadata', f'title={recording_name}',
        temp_file
    ]

    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process # Devolver el objeto, no solo el PID, es más robusto

def stop_process(process_obj):
    """Mata un proceso de grabación usando el objeto (más seguro que solo el PID)."""
    if process_obj and process_obj.poll() is None:
         try:
             process_obj.terminate() 
             process_obj.wait(timeout=1)
             if process_obj.poll() is None:
                 process_obj.kill()
             return True
         except Exception:
             return False
    return False

# --- Función de Conmutación de Audio (Corregida) ---

def switch_audio(source):
    """Conmuta la fuente de audio ajustando los faders en jack_mixer."""

    # 1. Apagar todas las fuentes manejadas por el Scheduler
    jack_mixer_set_volume(config.E1_STRIP, config.VOLUME_OFF)
    jack_mixer_set_volume(config.E2_STRIP, config.VOLUME_OFF)
    jack_mixer_set_volume(config.BLOCK_PLAYER_STRIP, config.VOLUME_OFF) # Usar el nuevo nombre

    # 2. Encender la fuente solicitada
    if source == "E1_LIVE":
        jack_mixer_set_volume(config.E1_STRIP, config.VOLUME_ON)
    elif source == "E2_LIVE":
        jack_mixer_set_volume(config.E2_STRIP, config.VOLUME_ON)
    elif source == "BLOCK_PLAYER":
        jack_mixer_set_volume(config.BLOCK_PLAYER_STRIP, config.VOLUME_ON)
    
    # Nota: La función 'play_chime' no es necesaria para la lógica central, se ha eliminado.
