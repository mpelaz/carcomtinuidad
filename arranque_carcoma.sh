#!/bin/bash

vncserver :1 -geometry 480x480 -depth 24 -localhost no
export DISPLAY=:1


# Script de arranque de los seis componentes esenciales en el entorno de usuario.

# --- Cargar configuración (Directamente para el shell) ---
# NOTE: Asegúrate de que estos comandos coincidan con config.py
JACK_COMMAND='jackd -d alsa -d hw:0 -r 44100 -p 1024 -n 3'
JACK_MIXER_COMMAND='jack_mixer' 
JACK_WAIT_TIME=5
API_WAIT_TIME=3

# --- 1. Infraestructura de Audio ---
echo "Iniciando Servidor JACK ($JACK_COMMAND)..."
nohup $JACK_COMMAND & 
sleep $JACK_WAIT_TIME

echo "Iniciando JACK-Mixer ($JACK_MIXER_COMMAND)..."
# CORRECCIÓN: Se elimina el peligroso "env DISPLAY="
nohup $JACK_MIXER_COMMAND &
sleep 1

# --- 2. Daemons de Control y Audio ---

echo "Iniciando Reproductor de Bloques Unificado (block_player.py)..."
nohup python3 block_player.py &
sleep 1 

echo "Iniciando API Central de Control (control_api.py)..."
nohup python3 control_api.py &
sleep $API_WAIT_TIME 

echo "Iniciando Daemon de Hardware (hardware_daemon.py)..."
nohup python3 hardware_daemon.py &

echo "Iniciando Scheduler (scheduler.py)..."
nohup python3 scheduler.py &

echo "Sistema de Radio Carcoma iniciado."
