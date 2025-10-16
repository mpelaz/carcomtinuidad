#!/bin/bash

vncserver :1 -geometry 480x480 -depth 24 -localhost no
export DISPLAY=:1
