#!/usr/bin/env sh
set -eu
UNIT_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/nixlms.service"
systemctl --user disable --now nixlms.service 2>/dev/null || true
rm -f "$UNIT_FILE"
systemctl --user daemon-reload
printf '%s\n' "Inicialização automática da NixLMs removida para o usuário atual."
