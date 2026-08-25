#!/usr/bin/env bash
# Rebuild the AEON OS frontend on the micro VM without OOM.
# Stops memory-hungry services during compilation, caps the Node heap,
# then brings everything back up.
set -e
cd /opt/aeon/web

echo "=== stopping services to free RAM ==="
sudo systemctl stop aeon-frontend || true
sudo systemctl stop aeon-backend || true
sleep 2
free -m | head -2

echo "=== building with capped heap ==="
export NODE_OPTIONS="--max-old-space-size=1400"
npm run build

echo "=== restarting services ==="
sudo systemctl start aeon-backend
sudo systemctl start aeon-frontend
echo "BUILD_DEPLOY_DONE"
