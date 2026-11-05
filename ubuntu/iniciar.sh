#!/usr/bin/env bash
# Abre el servidor KtOS local de WRC 9. Uso: bash iniciar.sh
cd "$(dirname "$0")" || exit 1

for cmd in python3 openssl; do
    if ! command -v "$cmd" >/dev/null; then
        echo "Falta $cmd. Instalalo con: sudo apt install $cmd"
        exit 1
    fi
done

if command -v ufw >/dev/null; then
    sudo ufw allow 60000:60031/udp comment 'WRC9 LAN' >/dev/null
fi

exec sudo python3 wrc9-ktos.py
