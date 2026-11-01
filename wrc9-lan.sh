#!/usr/bin/env bash
# Activa o desactiva el modo LAN oculto de WRC 9 (Steam + Proton).
# Uso: ./wrc9-lan.sh on | off | status
set -euo pipefail

LINES=('WRC.UseLanNetwork = true;' 'Engine.UseKtOS = false;')
APPID=1267540
REL="steamapps/compatdata/$APPID/pfx/drive_c/users/steamuser/Documents/My Games/WRC9/UserSettings.cfg"

CFG=""
for root in \
    "$HOME/snap/steam/common/.local/share/Steam" \
    "$HOME/.local/share/Steam" \
    "$HOME/.steam/steam" \
    "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
    if [ -f "$root/$REL" ]; then CFG="$root/$REL"; break; fi
done

if [ -z "$CFG" ]; then
    echo "No encontre UserSettings.cfg. Abri WRC 9 una vez y cerralo, y volve a intentar." >&2
    exit 1
fi

case "${1:-status}" in
    on|off)
        if pgrep -f 'WRC9\.exe' >/dev/null; then
            echo "WRC 9 esta abierto. Cerralo primero." >&2
            exit 1
        fi
        [ -f "$CFG.bak" ] || cp -- "$CFG" "$CFG.bak"
        sed -i -e '/^WRC\.UseLanNetwork/d' -e '/^Engine\.UseKtOS/d' "$CFG"
        if [ "$1" = on ]; then
            [ -z "$(tail -c1 "$CFG")" ] || echo >> "$CFG"
            printf '%s\n' "${LINES[@]}" >> "$CFG"
        fi
        ;;
    status) ;;
    *) echo "Uso: $0 on | off | status" >&2; exit 2 ;;
esac

if grep -q '^WRC\.UseLanNetwork = true' "$CFG"; then
    echo "Modo LAN: ACTIVADO"
else
    echo "Modo LAN: desactivado"
fi
echo "Archivo: $CFG"
