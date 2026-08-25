#!/usr/bin/env bash
# One-shot repair for AEON OS on the OCI micro VM:
# - reset DB password (was lost when extraction wiped hidden files)
# - rebuild .env DATABASE_URL
# - single patient preloaded gunicorn worker for 1GB RAM
# - run migrations, restart backend
set -e
cd /opt/aeon

NP=$(openssl rand -hex 16)
sudo -u postgres psql -qc "ALTER USER aeon WITH PASSWORD '$NP';"
echo "$NP" > .dbpass && chmod 600 .dbpass

sed -i "/^AEON_DATABASE_URL=/d" .env
echo "AEON_DATABASE_URL=postgresql://aeon:$NP@127.0.0.1:5432/aeon" >> .env

sudo sed -i "s|ExecStart=.*gunicorn.*|ExecStart=/opt/aeon/venv/bin/gunicorn -w 1 -t 240 --preload -b 127.0.0.1:5000 aeon_server:app|" /etc/systemd/system/aeon-backend.service
sudo systemctl daemon-reload

set -a; source .env; set +a
./venv/bin/python -m alembic upgrade head > /tmp/alembic.log 2>&1 && echo "MIGRATIONS OK" || tail -5 /tmp/alembic.log

sudo systemctl restart aeon-backend
echo FIX_APPLIED
