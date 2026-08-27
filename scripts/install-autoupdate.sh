#!/usr/bin/env sh
# AEON OS — install the auto-update systemd timer on the VM.
# Installs /etc/systemd/system/aeon-autoupdate.{service,timer} and enables the
# timer. Idempotent: safe to re-run (e.g. after APP_DIR changes).
#   Check schedule: systemctl list-timers aeon-autoupdate.timer
#   Logs:           journalctl -u aeon-autoupdate.service -f
set -eu

APP_DIR="${AEON_APP_DIR:-/opt/aeon}"
SCRIPT="$APP_DIR/scripts/aeon-autoupdate.sh"

[ "$(id -u)" = 0 ] || { echo "Run with sudo (needs to write systemd units)."; exit 1; }
test -f "$SCRIPT" || { echo "ERROR: $SCRIPT not found — is the repo checked out at $APP_DIR?"; exit 1; }

sudo tee /etc/systemd/system/aeon-autoupdate.service >/dev/null <<EOF
[Unit]
Description=AEON OS auto-update (pull main, rebuild stack if changed)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/sh $SCRIPT
EOF

sudo tee /etc/systemd/system/aeon-autoupdate.timer >/dev/null <<EOF
[Unit]
Description=Periodic AEON OS auto-update

[Timer]
OnBootSec=5min
OnUnitActiveSec=30min
RandomizedDelaySec=4min
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now aeon-autoupdate.timer

echo ""
echo "aeon-autoupdate.timer installed."
echo "  Schedule:  systemctl list-timers aeon-autoupdate.timer"
echo "  Live logs: journalctl -u aeon-autoupdate.service -f"
echo "  Update now: sudo systemctl start aeon-autoupdate.service"
