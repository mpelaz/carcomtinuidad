#!/bin/bash

# dia de la semana 1 es lunes, 7 domingo

XDG_RUNTIME_DIR="/run/user/1001"
SILENCIODBS=50
SEGUNDOSSILENCIO=360
CARCOMAINSTALL="/home/radio/carcomanegra_woody/radio"
CONFDIR="/home/radio/carcomanegra_woody/radio/kjabata_config"
ARCHIVO="/home/radio/carcomanegra_woody/radio/archivo"
PROGRAMAS="/home/radio/carcomanegra_woody/radio/programas"
FFMPEGLOG="/tmp/ffmpeg.log"


JSF=$(find $CONFDIR -name "2*jSF" | xargs ls -rt | tail -n1)
JBF=$(find $CONFDIR -name "2*jBF" | xargs ls -rt | tail -n1)

#pulseaudio --start

DAYOFWEEK=`date '+%u'`
HOUR=`date '+%H'`
RECORDING=NO

if [[ $HOUR == "24" ]]
then
        $HOUR="00"
fi

# echo `date +%Y%m%d%H%M` " Grabacarcoma invocado el día $DAYOFWEEK, hora $HOUR con PID $$."

# while loop para leer linea a linea
while IFS= read -r line; do
        # Solo evaluamos si no está ya grabando
        # Si la linea empieza por el día que queremos, variable a SI
        if [[ $line == *DAYOFWEEK\=\"$DAYOFWEEK* ]] && [[ $RECORDING == NO ]]; then
                printline="SI"
        fi

        # Si estamos en el día, evalúo la programación diaria solo si no está ya grabando
        if [[ $printline == "SI" ]]  && [[ $RECORDING == NO ]]; then

                # Evalúo si es una linea de grabación
                if [[ $line == *RECORDINGSTRIP* ]] && [[ $RECORDING == NO ]]; then

                        # Evalúo si es la hora de empezar a grabar
                        if [[ $line == *BH\=\"$HOUR* ]] && [[ $RECORDING == NO ]]; then

                                # Me quedo con la hora de finalización
                                FIN=$(echo $line | cut -d "\"" -f 6)
                                # y con el BLOCKID
                                BLOCKID=$(echo $line | cut -d "\"" -f 10)
                                # Saco el nombre del programa
                                LIN_NOM=$(grep ID\=\"$BLOCKID $JBF)
                                NOM=$(echo $LIN_NOM | cut -d "\"" -f 4)
                                NOM_FILE=$(echo $NOM | tr ' ' '_')
                                DATE=`date +%Y%m%d`
                                FULLFILE=$ARCHIVO/$DATE-$NOM_FILE

                                # Seteo la variable de grabacion para no hacer nada más hasta que termine
                                RECORDING="SI"

                                # Calculo en segundos lo que tiene que durar la grabación
                                # Convierto los pasos de día sumando 24
                                if [ $FIN < $HOUR ]; then FIN=$(($FIN + 24)); fi
                                DUR_HOURS=$(($FIN - $HOUR))             # horas de grabación
                                REC_SECS=$((($DUR_HOURS * 3600) - 2))   # segundos de grabación, menos 2s para indicativos o ejecución

                                # Si el archivo existe, renombro el nuevo
                                if [ -f $FULLFILE.mp3 ]; then
                                        FULLFILE=$FULLFILE$$
                                fi

                                echo `date +%Y%m%d%H%M` " Grabo $NOM de $HOUR a $FIN durante $REC_SECS sec. en $FULLFILE.mp3"

                                # Si ya corre un ffmpeg me lo cargo
                                # Si me lo cargo, no enlazo para continuidad!!! A mejorar.

                                FFMPEGRUN=$(ps -ef|grep ffmpeg |grep silence | awk '{ print $2 }')
                                if [[ "$FFMPEGRUN" != "" ]]; then
                                        kill $FFMPEGRUN
                                fi

                                # Lanzo el ffmpeg grabador, que chiva silencios <50dB y >5segundos a un log
                                echo > $FFMPEGLOG       # vacío el log de control
                                /usr/bin/ffmpeg \
                                        -nostats \
                                        -hide_banner \
                                        -nostdin \
                                        -f alsa \
                                        -i hw:1,0 \
                                        -sample_rate 44100 \
                                        -af silencedetect=noise=-50dB:d=$SEGUNDOSSILENCIO \
                                        -t $REC_SECS \
                                        $FULLFILE.mp3 \
                                >> $FFMPEGLOG 2>> $FFMPEGLOG &
                                FFMPEGPID=$!
                                # echo "ffmpeg corre con pid " $FFMPEGPID

                                # Bucle de vigilancia de mpeg, lo mata si hay silencios y linka a continuidad si termina bien (>60% del tiempo total)
                                QUESEGUNDOES=`date +%s`
                                while [  $(("`date +%s`" - $QUESEGUNDOES)) -lt $REC_SECS ] && [[ $RECORDING == SI ]]; do

                                        # codigo vigilancia
                                        # echo $(("`date +%s`" - $QUESEGUNDOES)) de $REC_SECS
                                        SILENCE=`grep "^\[silencedetect" $FFMPEGLOG`
                                        if [ "$SILENCE" ]; then
                                                #Hay un silencio en el log, mato el ffmpeg
                                                #kill $FFMPEGPID
                                                #RECORDING=NO
                                                break
                                        fi

                                        sleep 0.9
                                done

                                kill $FFMPEGPID
                                RECORDING=NO

                                # Si ha grabado mas de la cuarta parte de lo que dura el bloque, lo doy por bueno y lo enlazo

                                sleep 1

                                RECORDEDHOURS=$(grep time $FFMPEGLOG | awk '{ print $3 }' | cut -d":" -f1 | cut -d"=" -f2)
                                RECORDEDMINS=$(grep time $FFMPEGLOG | awk '{ print $3 }' | cut -d":" -f2)
                                RECORDEDTIME=$(( ( $RECORDEDHOURS * 60 ) + $RECORDEDMINS ))
                                RECORDQUARTER=$(( $REC_SECS * 60 / 4))                  #La cuarta parte de lo que debería durar la grabación, segundos

                                if [ $RECORDEDTIME -gt $RECORDQUARTER ]; then
                                        mkdir $PROGRAMAS/$NOM
                                        ln -s $FULLFILE.mp3 $PROGRAMAS/$NOM/$NOM_FILE.mp3
                                        echo `date +%Y%m%d%H%M` " Grabado $FULLFILE.mp3"
                                elif [ $RECORDEDTIME -lt $RECORDQUARTER ]; then
                                        rm -f $FULLFILE.mp3
                                        echo `date +%Y%m%d%H%M` " Programa $NOM ha durado menos de $RECORDQUARTER segundos. Borrado"
                                fi


                        fi

                fi

        fi

        if [[ $line == \<\/DAY\> ]]; then
        printline="NO"
        fi

done < "$JSF"

