#!/bin/bash
# cloud.ru-free-tier-vm — Server provisioning & CIS audit
# Repo: https://github.com/mlenkov/cloud.ru-free-tier-vm
#
# Usage:
#   sudo BW_ACCESS_TOKEN="xxx" bash deploy.sh
#
# Or from SSH:
#   ssh user@host
#   sudo apt update && sudo apt install -y git
#   git clone https://github.com/mlenkov/cloud.ru-free-tier-vm.git
#   cd cloud.ru-free-tier-vm
#   sudo BW_ACCESS_TOKEN="xxx" bash deploy.sh

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# === Server mode: must run as root ===
# Pass BW_ACCESS_TOKEN explicitly through sudo (env var BEFORE sudo is lost)
if [ "$EUID" -ne 0 ]; then
    exec sudo BW_ACCESS_TOKEN="${BW_ACCESS_TOKEN:-}" bash "$0" "$@"
fi

ORIGINAL_USER="${SUDO_USER:-$(who am i | awk "{print \$1}")}"
if [ -z "$ORIGINAL_USER" ] || [ "$ORIGINAL_USER" = "root" ]; then
    ORIGINAL_HOME="$HOME"
else
    ORIGINAL_HOME=$(eval echo "~$ORIGINAL_USER")
fi

PROJECT_DIR="$ORIGINAL_HOME/cloud.ru-free-tier-vm"
DOCS_DIR="$ORIGINAL_HOME/docs"

echo "===== cloud.ru-free-tier-vm — Server Provisioning ====="

# Clean dpkg locks from any previous interrupted install
rm -f /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend \
      /var/cache/apt/archives/lock /var/lib/apt/lists/lock
dpkg --configure -a 2>/dev/null || true

# Install all deps upfront (avoids dpkg lock issues in cis_manager)
apt-get update -qq 2>/dev/null || true
apt-get install -y -qq \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold" \
  git python3 python3-pip python3-venv restic rclone curl \
  aide fail2ban chrony needrestart unattended-upgrades

# AIDE DB initialization (background, 5-15 min on 2 vCPU)
if [ ! -f /var/lib/aide/aide.db ]; then
    echo "→ Initializing AIDE DB (background)..."
    aideinit --background 2>/dev/null || true
fi

cd "$PROJECT_DIR"
pip3 install --break-system-packages -q -r requirements.txt 2>/dev/null || \
PIP_REQUIRE_VIRTUALENV=false pip3 install -q -r requirements.txt

if [ -z "${BW_ACCESS_TOKEN:-}" ]; then
    echo "⚠️  BW_ACCESS_TOKEN не задан. Секреты не синхронизируются."
    echo "   Введите токен сейчас или нажмите Enter чтобы пропустить:"
    read -rsp "   BW_ACCESS_TOKEN: " BW_ACCESS_TOKEN
    echo
    export BW_ACCESS_TOKEN
fi

if [ -n "${BW_ACCESS_TOKEN:-}" ]; then
    python3 scripts/secrets.py sync
fi

if [ -f .env ]; then
    set -a; source .env 2>/dev/null; set +a
fi

python3 cis_manager.py audit --format json
python3 cis_manager.py fix --force

# Ensure fail2ban is running before final audit
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
backend = systemd
maxretry = 3
EOF
systemctl enable --now fail2ban 2>&1 || true
sleep 2
if ! systemctl is-active --quiet fail2ban; then
    echo "⚠️  fail2ban не стартует, ошибка:"
    sudo journalctl -u fail2ban -n 5 --no-pager 2>/dev/null || true
fi

python3 cis_manager.py audit --format json

# Don't exit on compliance fail — let backup + docs run
python3 scripts/check_compliance.py --threshold 95 || true

python3 scripts/backup.py setup 2>/dev/null || true
python3 scripts/backup.py create 2>/dev/null || true
python3 scripts/docs_generator.py

mkdir -p "$DOCS_DIR"
cp docs/SERVER.md "$DOCS_DIR/" 2>/dev/null || true

chown -R "$ORIGINAL_USER:$ORIGINAL_USER" "$PROJECT_DIR"

echo "===== Done ====="
echo "Project: $PROJECT_DIR"
echo "Docs:    $DOCS_DIR/SERVER.md"
