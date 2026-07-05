#!/bin/bash
# Стартовый скрипт для GitVerse DevOps
# Автоматически настраивает сервер под CIS стандарты

set -e

echo "🚀 Starting GitVerse DevOps setup..."
echo "======================================"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script requires root privileges"
    echo "Please run with: sudo bash start.sh"
    exit 1
fi

# Переменные окружения
export BW_SESSION="${BW_SESSION:-}"
export GITVERSE_TOKEN="${GITVERSE_TOKEN:-}"

# Путь к проекту (определяется автоматически)
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "📁 Project directory: $PROJECT_DIR"

# Шаг 1: Обновление системы
echo "📝 Step 1/5: Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Шаг 2: Установка необходимых пакетов
echo "📦 Step 2/5: Installing required packages..."
apt-get install -y \
    python3 \
    python3-pip \
    git \
    curl \
    wget \
    restic \
    rclone

# Шаг 3: Синхронизация секретов из Bitwarden Secrets Manager
if [ -n "$BW_ACCESS_TOKEN" ] && [ -n "$BW_ORG_ID" ]; then
    echo "🔒 Step 3/5: Syncing secrets from Bitwarden Secrets Manager..."
    pip install -r requirements.txt
    python3 scripts/secrets.py sync
    echo "✅ Secrets synced"
else
    echo "⚠️  BW_ACCESS_TOKEN/BW_ORG_ID not provided, loading from .env if exists..."
    if [ -f .env ]; then
        set -a; source .env; set +a
        echo "   ✅ .env loaded"
    else
        echo "   ⚠️  No .env found, continuing with empty secrets"
    fi
fi

# Шаг 4: Применение CIS стандартов
echo "🔧 Step 4/5: Applying CIS standards..."
cd "$PROJECT_DIR"

# Запуск аудита
python3 cis_manager.py audit --format json

# Применение исправлений (автоматически)
python3 cis_manager.py fix --force

# Повторный аудит для проверки
python3 cis_manager.py audit --format json --output audit_after_fix.json

# Шаг 5: Генерация документации
echo "📝 Step 5/5: Generating documentation..."
python3 scripts/docs_generator.py

echo "======================================"
echo "✅ GitVerse DevOps setup complete!"
echo "======================================"

# Итоговая информация
echo ""
echo "📊 Compliance Score:"
grep -o '"compliance_score": [0-9.]*' cis_data/current_audit.json || echo "Unable to determine"
echo ""
echo "📄 README generated at: $PROJECT_DIR/README.md"
echo "💾 Audit reports in: $PROJECT_DIR/cis_data/"
