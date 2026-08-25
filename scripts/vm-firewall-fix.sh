#!/usr/bin/env bash
# Fix: remove misplaced rules and re-insert before the REJECT rule
set -e
# drop our earlier misordered rules (match by port spec)
while sudo iptables -C INPUT -m state --state NEW -p tcp --dport 80 -j ACCEPT 2>/dev/null; do sudo iptables -D INPUT -m state --state NEW -p tcp --dport 80 -j ACCEPT; done
while sudo iptables -C INPUT -m state --state NEW -p tcp --dport 443 -j ACCEPT 2>/dev/null; do sudo iptables -D INPUT -m state --state NEW -p tcp --dport 443 -j ACCEPT; done
# find the REJECT line number and insert just above it
REJ=$(sudo iptables -L INPUT -n --line-numbers | awk "/REJECT/ {print \$1; exit}")
POS=${REJ:-1}
sudo iptables -I INPUT $POS -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -I INPUT $POS -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save >/dev/null 2>&1
echo "FIXED"
