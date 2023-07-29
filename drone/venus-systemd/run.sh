#!/usr/bin/env bash

if [ ${EUID} -ne 0 ]; then
    echo "This script should run as root?"
    exit 1
fi

if [ test -f "/VENUS_PROD" ]; then
    # Production mode
    echo "Running venus production mode..."

    sudo -i -u pi bash << EOF
cd /venus/main
./home/pi/.pyenv/shims/python3.10 src/main.py
EOF
else
    # Development (test) mode
    echo "Running venus development/test mode..."

    mount /dev/sda1 /venus-dev
    chmod -R 755 /venus-dev
    chmod -R -rwxrw-rw /venus-dev
    sudo -i -u pi bash << EOF
cd /venus-dev/main
./home/pi/.pyenv/shims/python3.10 src/main.py
EOF
fi