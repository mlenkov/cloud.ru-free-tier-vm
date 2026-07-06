#!/bin/bash
# cloud.ru-free-tier-vm — Server provisioning & CIS audit
# Repo: https://github.com/mlenkov/cloud.ru-free-tier-vm
#
# Usage:
#   BW_ACCESS_TOKEN="xxx" sudo bash deploy.sh
#
# Or from SSH:
#   ssh user@host
#   git clone https://github.com/mlenkov/cloud.ru-free-tier-vm.git
#   cd cloud.ru-free-tier-vm
#   BW_ACCESS_TOKEN="xxx" sudo bash deploy.sh

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

# === Server mode: must run as root ===
if [ "$EUID" -ne 0 ]; then
    exec sudo bash "$0" "$@"
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

# Fix broken dpkg state
dpkg --configure -a 2>/dev/null || true
apt-get update -qq 2>/dev/null || true

# Install deps (force-confdef handles modified conffiles)
apt-get install -y -qq \
  -o Dpkg::Options::="--force-confdef" \
  -o Dpkg::Options::="--force-confold" \
  git python3 python3-pip python3-venv restic rclone curl

cd "$PROJECT_DIR"
pip3 install --break-system-packages -q -r requirements.txt 2>/dev/null || \
PIP_REQUIRE_VIRTUALENV=false pip3 install -q -r requirements.txt

if [ -n "${BW_ACCESS_TOKEN:-}" ]; then
    python3 scripts/secrets.py sync
fi

if [ -f .env ]; then
    set -a; source .env; set +a
fi

python3 cis_manager.py audit --format json
python3 cis_manager.py fix --force
python3 cis_manager.py audit --format json
python3 scripts/check_compliance.py --threshold 95
python3 scripts/backup.py setup 2>/dev/null || true
python3 scripts/backup.py create 2>/dev/null || true
python3 scripts/docs_generator.py

mkdir -p "$DOCS_DIR"
cp docs/SERVER.md "$DOCS_DIR/" 2>/dev/null || true

echo "===== Done ====="
echo "Project: $PROJECT_DIR"
echo "Docs:    $DOCS_DIR/SERVER.md"
