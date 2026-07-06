#!/bin/bash
# cloud.ru-free-tier-vm — Server provisioning & CIS audit
# Repo: https://github.com/mlenkov/cloud.ru-free-tier-vm
#
# Usage (interactive):
#   ./deploy.sh
#
# Usage (non-interactive):
#   SSH_USER=root SSH_KEY=~/.ssh/key BW_ACCESS_TOKEN="xxx" ./deploy.sh <hostname>
#
# Usage (directly on server):
#   sudo bash deploy.sh

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

SERVER="${1:-}"

# === Interactive mode (local, no args) ===
if [ -z "$SERVER" ] && [ -z "${_DEPLOY_SERVER_MODE:-}" ]; then
    echo "===== cloud.ru-free-tier-vm — Interactive Setup ====="
    read -rp "Server IP/hostname: " SERVER
    default_user="${SSH_USER:-root}"
    read -rp "SSH user [$default_user]: " input_user
    SSH_USER="${input_user:-$default_user}"
    read -rp "SSH key path (optional): " SSH_KEY
    read -rsp "BW_ACCESS_TOKEN: " BW_ACCESS_TOKEN
    echo

    mkdir -p docs
    cat > docs/connection.md <<EOF
# Server Connection

- **IP**: ${SERVER}
- **User**: ${SSH_USER}
- **SSH Key**: ${SSH_KEY:-}
EOF

    export SSH_USER SSH_KEY BW_ACCESS_TOKEN
    exec bash "$0" "$SERVER"
fi

# === Local mode: scp entire repo + deploy ===
if [ -n "$SERVER" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SSH_USER="${SSH_USER:-root}"
    SSH_DEST="$SSH_USER@$SERVER"
    SSH_OPTS="${SSH_KEY:+-i $SSH_KEY}"

    echo "===== Deploying to ${SSH_DEST} ====="
    ssh-keygen -R "$SERVER" 2>/dev/null || true

    echo "→ Accepting host key..."
    ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 $SSH_OPTS "$SSH_DEST" true 2>/dev/null || true

    echo "→ Testing SSH connection..."
    if ! ssh -o BatchMode=yes -o ConnectTimeout=5 $SSH_OPTS "$SSH_DEST" true; then
        echo "❌ SSH connection failed."
        echo "   Check: user ($SSH_USER), key ($SSH_KEY), server reachability"
        exit 1
    fi

    ssh $SSH_OPTS "$SSH_DEST" "rm -rf cloud.ru-free-tier-vm && mkdir cloud.ru-free-tier-vm"
    tar cz --exclude='.git' --exclude='.opencode' --exclude='__pycache__' \
      --exclude='.env' --exclude='cis_data' --exclude='.github' \
      -C "$SCRIPT_DIR" . | ssh $SSH_OPTS "$SSH_DEST" "tar xz -C cloud.ru-free-tier-vm"
    echo "===== Running provisioning ====="
    ssh -t $SSH_OPTS "$SSH_DEST" \
      "sudo bash -c 'BW_ACCESS_TOKEN=\"${BW_ACCESS_TOKEN:-}\" _DEPLOY_SERVER_MODE=1 bash cloud.ru-free-tier-vm/deploy.sh'"
    exit $?
fi

# === Server mode ===
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
