#!/usr/bin/env bash
# Open web ports in the OS-level firewall (OCI Ubuntu ships restrictive iptables)
set -e
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
# persist across reboots
if command -v netfilter-persistent >/dev/null; then
  sudo netfilter-persistent save
else
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables-persistent >/dev/null || true
  sudo netfilter-persistent save 2>/dev/null || true
fi
echo "FIREWALL_OK"
