#!/usr/bin/env sh
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="\${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || { echo "Python 3 não encontrado." >&2; exit 1; }
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else "NixLMs requer Python 3.10+")'
UNIT_DIR="\${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_FILE="$UNIT_DIR/nixlms.service"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=NixLMs local autonomous runtime
After=default.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$PYTHON -m nixlms_web.server
Restart=on-failure
RestartSec=10
Environment=NIXLMS_AUTONOMY_ENABLED=1

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now nixlms.service
printf '%s\n' "Inicialização configurada para o usuário atual." "Status: systemctl --user status nixlms.service" "Interface: http://127.0.0.1:8765" "Para remover: scripts/remove-autostart.sh"
