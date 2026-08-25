#!/usr/bin/env bash
# AEON OS — app deployment on Oracle micro VM (runs detached via nohup)
set -x
exec > >(tee /tmp/aeon-deploy.log) 2>&1

cd /opt/aeon

echo "=== [1/8] extract code ==="
find /opt/aeon -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
tar -xzf /tmp/aeon-deploy.tar.gz -C /opt/aeon
test -f aeon_server.py && test -f web/package.json && echo "code OK"

echo "=== [2/8] postgres ==="
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='aeon'" | grep -q 1; then
  DBPASS=$(openssl rand -hex 16)
  echo "$DBPASS" > /opt/aeon/.dbpass
  sudo -u postgres psql -c "CREATE USER aeon WITH PASSWORD '$DBPASS';"
  sudo -u postgres psql -c "CREATE DATABASE aeon OWNER aeon;"
fi
sudo systemctl enable --now postgresql

echo "=== [3/8] secrets + .env ==="
JWT=$(openssl rand -hex 32)
[ -f /opt/aeon/.jwtsecret ] || openssl rand -hex 32 > /opt/aeon/.jwtsecret
JWT=$(cat /opt/aeon/.jwtsecret)
ADMINPASS=$(openssl rand -base64 15 | tr -d '/+=' | head -c 16)
cat > /opt/aeon/.env <<ENV
AEON_ENV=production
AEON_DATABASE_URL=postgresql://aeon:$(cat /opt/aeon/.dbpass)@127.0.0.1:5432/aeon
AEON_JWT_SECRET=$JWT
AUTH_SECRET=$JWT
NEXTAUTH_SECRET=$JWT
AUTH_TRUST_HOST=true
NEXTAUTH_URL=http://141.147.3.145
AEON_PYTHON_URL=http://127.0.0.1:5000
AEON_CORS_ALLOWED_ORIGINS=http://141.147.3.145
AEON_LLM_PROVIDER=stub
AEON_ADMIN_EMAIL=admin@aeon.local
AEON_ADMIN_PASSWORD=$ADMINPASS
AEON_ADMIN_NAME=Admin
PORT=3000
ENV
chmod 600 /opt/aeon/.env
cp /opt/aeon/.env /opt/aeon/web/.env.production.local 2>/dev/null || true

echo "=== [4/8] python venv ==="
cd /opt/aeon
python3 -m venv venv
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt gunicorn
echo "pip done"

echo "=== [5/8] migrations ==="
set -a; source /opt/aeon/.env; set +a
./venv/bin/python -m alembic upgrade head && echo "migrations OK"

echo "=== [6/8] web deps ==="
cd /opt/aeon/web
npm ci --no-audit --no-fund 2>&1 | tail -2

echo "=== [7/8] next build (slow on 1GB, using swap) ==="
NODE_OPTIONS="--max-old-space-size=1400" npm run build 2>&1 | tail -6

echo "=== [8/8] systemd services ==="
sudo tee /etc/systemd/system/aeon-backend.service >/dev/null <<UNIT
[Unit]
Description=AEON OS Flask backend
After=network.target postgresql.service
[Service]
User=ubuntu
WorkingDirectory=/opt/aeon
EnvironmentFile=/opt/aeon/.env
ExecStart=/opt/aeon/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 aeon_server:app
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
sudo tee /etc/systemd/system/aeon-web.service >/dev/null <<UNIT
[Unit]
Description=AEON OS Next.js frontend
After=network.target aeon-backend.service
[Service]
User=ubuntu
WorkingDirectory=/opt/aeon/web
EnvironmentFile=/opt/aeon/.env
ExecStart=/usr/bin/npm start
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now aeon-backend aeon-web

echo "=== caddy reverse proxy ==="
if ! command -v caddy >/dev/null; then
  curl -fsSL -o /tmp/caddy.tgz https://github.com/caddyserver/caddy/releases/download/v2.8.4/caddy_2.8.4_linux_amd64.tar.gz
  tar -xzf /tmp/caddy.tgz -C /tmp caddy
  sudo mv /tmp/caddy /usr/local/bin/caddy && sudo chmod +x /usr/local/bin/caddy
  sudo tee /etc/systemd/system/caddy.service >/dev/null <<UNIT2
[Unit]
Description=Caddy web server
After=network.target
[Service]
User=root
ExecStart=/usr/local/bin/caddy run --config /etc/caddy/Caddyfile
Restart=always
[Install]
WantedBy=multi-user.target
UNIT2
  sudo systemctl daemon-reload
fi
sudo mkdir -p /etc/caddy
sudo tee /etc/caddy/Caddyfile >/dev/null <<'CADDY'
{
	auto_https off
}
:80 {
	encode gzip
	handle /health {
		reverse_proxy 127.0.0.1:5000
	}
	handle {
		reverse_proxy 127.0.0.1:3000
	}
}
CADDY
sudo systemctl enable --now caddy 2>/dev/null || sudo systemctl restart caddy || echo "caddy start failed"

echo "DEPLOY_DONE"
