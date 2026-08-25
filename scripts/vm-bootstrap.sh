#!/usr/bin/env bash
# AEON OS — server-side bootstrap for Oracle Cloud micro VM (Ubuntu 22.04 x86_64)
# Designed to run detached: nohup bash vm-bootstrap.sh > /tmp/aeon-bootstrap.log 2>&1 &
set -x

exec > >(tee /tmp/aeon-bootstrap.log) 2>&1

echo "=== [1/5] swap ==="
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  echo "/swapfile none swap sw 0 0" | sudo tee -a /etc/fstab >/dev/null
fi
free -h | grep -i swap || true

echo "=== [2/5] apt packages ==="
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  postgresql postgresql-contrib python3-venv python3-pip git curl jq >/dev/null

echo "=== [3/5] postgres up ==="
sudo systemctl enable --now postgresql
sudo -u postgres psql -tAc "SELECT version();" | cut -c1-40 || true

echo "=== [4/5] node 20 ==="
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - >/dev/null
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs >/dev/null
fi
node -v && npm -v

echo "=== [5/5] caddy (reverse proxy) ==="
if ! command -v caddy >/dev/null; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    debian-keyring debian-archive-keyring apt-transport-https >/dev/null
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/deb/gpg.key' | sudo gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null || true
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/deb/debian.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -qq >/dev/null
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq caddy >/dev/null
fi
caddy version || true

echo "BOOTSTRAP_DONE"
