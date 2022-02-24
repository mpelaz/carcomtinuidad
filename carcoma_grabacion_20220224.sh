#!/bin/bash
#
# -------------------------------
# 
#    Grabación continuidad 
#
#	 Radio Carcoma Madrid
#
# --------------------------------
#
# Este script tiene que ser invocado a cada hora en punto por el usuario con permiso en el repositorio de música y programas
# y que pertenezca al grupo con permiso de uso del subsistema de audio
#
# Para que funcione necesita: 
# - pulse audio en versión server wide (--server)
# - ffmpeg
# - mediainfo
# - Configuración de pulse para alsa con la tarjeta capturadora correspondiente
# - archivos jSF y jBF generados por la interfaz web de JABATA
#
# mpelaz -- miguel@suena.eu
# version: 20220224  --  mpelaz -- Cambio cálculo longitud de archivo con "mediainfo"
# version: 20220217  --  mpelaz -- Control de bloques de más de dos horas
#
#
# dia de la semana 1 es lunes, 7 domingo
# toma los datos de la continuidad Jabata, con este formato: 
#
#<DAY DAYOFWEEK="3" >
#   <TIMESTRIP BH="00" BM="00" EH="02" EM="00" BLOCKID="159" />
#   <TIMESTRIP BH="02" BM="00" EH="03" EM="00" BLOCKID="179" />
#   <TIMESTRIP BH="18" BM="00" EH="19" EM="00" BLOCKID="6" />
#   <TIMESTRIP BH="19" BM="00" EH="20" EM="00" BLOCKID="167" RECORDINGSTRIP="1" />
#   <TIMESTRIP BH="20" BM="00" EH="21" EM="00" BLOCKID="186" RECORDINGSTRIP="1" />
# </DAY>
# <DAY DAYOFWEEK="4" >
#   <TIMESTRIP BH="04" BM="00" EH="05" EM="00" BLOCKID="167" />
#   <TIMESTRIP BH="14" BM="00" EH="15" EM="00" BLOCKID="200" />
#   <TIMESTRIP BH="16" BM="00" EH="17" EM="00" BLOCKID="106" />
#   <TIMESTRIP BH="17" BM="00" EH="18" EM="00" BLOCKID="187" RECORDINGSTRIP/>
#   <TIMESTRIP BH="22" BM="00" EH="23" EM="00" BLOCKID="16" RECORDINGSTRIP="1" />
# </DAY>



# Configuración
XDG_RUNTIME_DIR="/run/user/1000"				# PID del user que va a correr esto y tiene permisos en los dirs
SILENCIODBS=50							# Límite inferior de dBs para detectar silencios
SEGUNDOSSILENCIO=360						# Segundos de silencio mínimos para descartar la grabación
CARCOMAINSTALL="/home/radio/carcomanegra_woody/radio"		# Ruta absoluta al directorio base de la instalación de continuidad
ARCHIVODIR="archivo"						# Ruta relativa de la carpeta que contiene TODOS los programas grabados
CONF="kjabata_config"			 			# Ruta relativa de la carpeta con la config de la continuidad Jabata
PROGRAMAS="programas"						# Ruta relativa de la carpeta con subcarpetas por programa y enlaces a los programas grabados
FFMPEGLOG_REC="/tmp/ffmpeg.log"					# log para detectar los silencios del ffmpeg
REC_DEVICE="alsa_input.usb-AUDIOTRAK_MAYA44_USB-00.multichannel-input" # Dispositivo PULSEAUDIO de grabación


# Variables globales						# A partir de aquí no se debería tocar nada
SCRIPT_NAME=$(ps -q $$ -o comm=)
#SCRIPT_NAME="graba.sh"
ARCHIVO="$CARCOMAINSTALL/$ARCHIVODIR"
#CONFDIR="/home/carcoma/carcomaREC/" # pruebas mpelaz
CONFDIR="$CARCOMAINSTALL/$CONF"
PID="/tmp/$SCRIPT_NAME"
FFMPEG_PID_FILE="/tmp/ffmpeg_rec.pid"
JSF=$(find $CONFDIR -name "2*jSF" | xargs ls -rt | tail -n1)
JBF=$(find $CONFDIR -name "2*jBF" | xargs ls -rt | tail -n1)


DAYOFWEEK=`date '+%u'`
HORA=`date '+%H'`
MIN=`date '+%M'`
RECORDING=NO
# if [[ $HORA == "24" ]]; then HORA="00"; fi

if [[ `id -u` == 0 ]]; then				# Si se lanza como root, muere SEGURO???
    echo "Este script no debe correr como root"
    exit
fi

echo `date +%Y%m%d%H%M` " $$ Hora $HORA en día $DAYOFWEEK comienzo ejecución"
# while loop para leer linea a linea la programación
while IFS= read -r line; do 

	if [[ $line == *DAYOFWEEK\=\"$DAYOFWEEK* ]] ; then  # Si la linea empieza por el día que queremos, variable a SI
		printline="SI"
	fi

    if [[ $line == *\</DAY* ]] || [[ $line == *\<JABATOSCHEDULEFILE* ]] ; then  # Si se acaba la programación del día, seteamos a NO
		printline="NO"
	fi
    
    if [[ $printline == "SI" ]] && [[ $line == *TIMESTRIP* ]] ; then    # Si estamos en el día de hoy y la fila es de bloque, evalúo las horas de cada bloque
        HORA_INI=$(echo $line | cut -d"\"" -f 2)
        HORA_FIN=$(echo $line | cut -d"\"" -f 6)

        if [ $HORA_FIN -lt $HORA_INI ]; then          # Evalúo si el bloque tiene cambio de día    
            if [ $HORA -lt $HORA_INI ]; then          # Si el bloque tiene salto del día y la hora actual es del día siguiente, le sumo 24
            HORA=$(($HORA + 24))
            fi
            HORA_FIN=$(($HORA_FIN + 24))                # Sumo 24 a la hora de finalización para el cálculo posterior de duración de bloque
        fi 
    
        # Evalúo bloque actual, si la hora actual es igual o posterior a la de inicio y anterior a la de finalización
        if [ $HORA -ge $HORA_INI ] && [ $HORA -lt $HORA_FIN ] ; then	

            if [[ $line == *RECORDINGSTRIP* ]]; then    # Estamos en un bloque de grabación. 

                # Si estamos aquí dentro, esto tiene que estar grabando. 
                FFMPEGRUN=$(ps -ef|grep ffmpeg |grep silence | awk '{ print $2 }')
				if [[ "$FFMPEGRUN" != "" ]]; then       # Algún proceso de grabación corriendo??
                    
                    echo  `date +%Y%m%d%H%M` " $$ proceso ffmpeg existente con pid $FFMPEGRUN. Saliendo." 
					exit
                    
                else 

                    # Iniciamos la grabación
                    BLOCKID=$(echo $line | cut -d "\"" -f 10)   # Saco el BLOCKID para sacar el nombre del programa del jBF
                    LIN_NOM=$(grep ID\=\"$BLOCKID $JBF)	        # Saco el nombre del programa
                    NOM=$(echo $LIN_NOM | cut -d "\"" -f 4)
                    NOM_FILE=$(echo $NOM | tr ' ' '_')	        # Relleno espacios con underscores
                    DATE=`date +%Y%m%d`
                    FULLFILE=$ARCHIVO/$DATE-$NOM_FILE	        # Ruta completa al .mp3
                    RECORDING="SI"				                # Seteo la variable de grabacion para no hacer nada más hasta que termine
                    echo $$ > $PID				                # Seteo el PID fuera para otras ejecuciones
                    
                    # Calculo en segundos lo que tiene que durar la grabación
                    MIN=`date '+%M'`                            # Minuto actual
                    SEG=`date '+%S'`                            # Segundo actual
                    PROG_DURA_S=$((($HORA_FIN - $HORA_INI) * 3600))                 # Duración del bloque en segundos
                    DIFF_S=$(((($HORA - $HORA_INI) * 3600) + ($MIN * 60) + $SEG ))  # Segundos pasados desde inicio de bloque
                    REC_SECS=$((($PROG_DURA_S - $DIFF_S) - 2 ))              # Segundos restantes de bloque -2s para operaciones
                    
                    if [ -f $FULLFILE.mp3 ]; then 		# Si el archivo existe, renombro el nuevo con el PID
                        FULLFILE=$FULLFILE$$
                    fi

                    # Lanzo el ffmpeg grabador, que chiva silencios < XX dB y > YY segundos a un log
                    echo $$ > $PID
                    echo > $FFMPEGLOG_REC	# vacío el log de control
                    sleep 1
                    
                    # Lanzo ffmpeg <<--- *** OJO!! opciones para tarjeta USB de 4x4 canales, cambiar si se pone una distinta.
                    /usr/bin/ffmpeg \
                        -nostdin \
                        -nostats \
                        -hide_banner \
                        -f pulse \
                        -sample_rate 44100 \
                        -re \
                        -channels 2 \
                        -i $REC_DEVICE \
                        -af "aresample=async=1, silencedetect=noise=-50dB:d=$SEGUNDOSSILENCIO" \
                        -use_wallclock_as_timestamps true \
                        -metadata title="$NOM $DATE https://www.radiocarcoma.com" \
                        -metadata album="Radio Carcoma Madrid https://www.radiocarcoma.com -- Tel.(+34) 911 426 912" \
                        -metadata copyright="(c) Radio Carcoma Madrid" \
                        -metadata genre="Radio" \
                        -t $REC_SECS \
                        $FULLFILE.mp3 2> "$FFMPEGLOG_REC" 1> "$FFMPEGLOG_REC" &
                    FFMPEGPID=$!
                    # echo "ffmpeg corre con pid " $FFMPEGPID
                    echo $FFMPEGPID > $FFMPEG_PID_FILE

                    echo `date +%Y%m%d%H%M` " $$ Grabo $NOM con pid $FFMPEGPID de $HORA a $HORA_FIN durante $REC_SECS sec. en $FULLFILE.mp3"

                    # Bucle de vigilancia de mpeg, lo mata si hay silencios 
                    QUESEGUNDOES=`date +%s`

                    # Mientras lleve grabando menos de lo que dura el bloque y el proceso esté corriendo...
                    while [  $(("`date +%s`" - $QUESEGUNDOES)) -lt $REC_SECS ] && [[ $RECORDING == SI ]] && kill -0 $FFMPEGPID 2> /dev/null ; do 
                        
                        # echo $(("`date +%s`" - $QUESEGUNDOES)) de $REC_SECS
                        SILENCE=`grep "^\[silencedetect" $FFMPEGLOG_REC`
                        if [ "$SILENCE" ]; then
                            #Hay un silencio en el log, salgo para matar el ffmpeg 
                            RECORDING=NO
                            break
                        fi

                        sleep 0.9
                    done				# Fin while tiempo grabación

                    RECORDING=NO        # Hemos terminado de grabar
                    FFMPEGRUN=$(ps -ef|grep ffmpeg |grep silence | awk '{ print $2 }')
                    if [[ "$FFMPEGRUN" != "" ]]; then               # Paro el ffmpeg grabador que hubiera andando
                        kill $FFMPEGRUN
                        #kill $FFMPEGRUN
                        rm -f $FFMPEG_PID_FILE
                        #sleep 2
                    fi

                    #sleep 3					# Espera a que ffmpeg escriba el log con la duración de lo grabado
                    
                    # Si ha grabado mas de la TERCERA parte de lo que dura el bloque, lo doy por bueno y lo enlazo.
		    # OJO -> Esta TERCERA parte tiene que ser siempre MAYOR que el tiempo de silencio que definamos. Si no es así,
		    # podríamos dar por buenas grabaciones en silencio muy largas que se repetirían como bloque de continuidad.


		    RECORDEDTIME_MS=$(mediainfo --Output='General;%Duration%' $FULLFILE.mp3)
		    RECORDEDTIME=$((RECORDEDTIME_MS / 1000 / 60))	# Duración del archivo grabado en MINUTOS
                    RECORDQUARTER=$(($PROG_DURA_S /3 /60))		# La tercera parte de lo que dura el bloque (/3), en minutos (/60)

                    if [ $RECORDEDTIME -ge $RECORDQUARTER ]; then   # Si el archivo grabado es igual o menor a la cuarta parte de lo que debería durar (min)
                        mkdir "$CARCOMAINSTALL/$PROGRAMAS/$NOM"
                        rm -f "$CARCOMAINSTALL/$PROGRAMAS/$NOM/$NOM_FILE.mp3"
                        ln -s "../../$ARCHIVODIR/$DATE-$NOM_FILE.mp3" "$CARCOMAINSTALL/$PROGRAMAS/$NOM/$NOM_FILE.mp3"		# Creo el enlace para la continuidad
                        echo `date +%Y%m%d%H%M`	" Grabado $FULLFILE.mp3"
                    elif [ $RECORDEDTIME -lt $RECORDQUARTER ]; then             # Si es menor, borro el grabado y dejo el enlace anterior
                        rm -f "$FULLFILE.mp3"
                        echo `date +%Y%m%d%H%M` " Programa $NOM ha durado menos de $RECORDQUARTER minutos. Borrado"
                    fi                    

				fi  # Fin hay o no procesos ffmpeg corriendo, dentro de bloque de grabación

            else                                        # Estamos en un bloque de repetición

                # Si estamos aquí dentro, no debería haber ningún proceso grabador. Si lo hay, me lo cargo. 
                echo `date +%Y%m%d%H%M` " $$ Hora $HORA en día $DAYOFWEEK sin grabación"
                RECORDING=NO
                FFMPEGRUN=$(ps -ef|grep ffmpeg |grep silence | awk '{ print $2 }')
				if [[ "$FFMPEGRUN" != "" ]]; then 
					kill $FFMPEGRUN
                    #kill $FFMPEGRUN
                    rm -f $FFMPEG_PID_FILE
                    sleep 2
				fi

            fi                  # Fin acciones bloque actual

            printline="NO"      # Si he caído aquí, el bloque era actual y ya he finalizado las acciones, no evalúo más lineas del archivo.

        fi                      # Evaluación estar en bloque actual
    
    fi                          # Fin linea de programación de bloque

done < "$JSF"                     # while lee archivo
echo `date +%Y%m%d%H%M` " $$ Hora $HORA en día $DAYOFWEEK fin ejecución"
