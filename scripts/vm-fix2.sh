#!/usr/bin/env bash
# Set AEON_ROOT so aeon.py stops trying to mkdir /content (Colab default)
set -e
cd /opt/aeon
grep -q "^AEON_ROOT=" .env || echo "AEON_ROOT=/opt/aeon/aeon_state" >> .env
mkdir -p /opt/aeon/aeon_state
sudo systemctl restart aeon-backend
echo AEONROOT_SET
