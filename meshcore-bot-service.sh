#!/bin/bash
# setup the python env
source ~/Meshcore-Bot-venv/bin/activate
# make sure we are in the correct directory
cd /home/pi/Alligitor/meshcore-bot

#generate a file name for screen
logFilename="screen-"$(date +"%Y-%m-%d_%H-%M-%S")-meshcore-bot.log
echo $logFilename

/usr/bin/screen -S MeshcoreBot -d -L -Logfile /tmp/$logFilename -m /home/pi/Meshcore-Bot-venv/bin/python3 meshcore_bot.py

