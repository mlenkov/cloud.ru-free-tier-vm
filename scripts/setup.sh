#!/bin/bash
# Скрипт установки (setup.sh)
# Применяет CIS стандарты к серверу

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "🔧 Applying CIS standards..."
echo "📁 Project directory: $PROJECT_DIR"

# Запуск аудита
python3 "$PROJECT_DIR/cis_manager.py" audit

# Исправление проблем (без интерактива)
python3 "$PROJECT_DIR/cis_manager.py" fix --force

# Валидация
python3 "$PROJECT_DIR/cis_manager.py" audit --format json --output "$PROJECT_DIR/cis_data/audit_after_fix.json"

echo "✅ CIS standards applied"
