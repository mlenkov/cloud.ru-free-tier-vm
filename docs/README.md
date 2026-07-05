# 📖 Документация GitVerse VPS Fortify

## 📋 Оглавление

### 🔧 Основные документы
- [README.md](../README.md) - Общий обзор проекта
- [AGENTS.md](../AGENTS.md) - Документация AI Employee DevOps Agent

### 🏗️ Архитектура и дизайн
- [ARCHITECTURE.md](ARCHITECTURE.md) - Архитектура системы
- [CIS_STANDARDS.md](CIS_STANDARDS.md) - Стандарты CIS Debian 12 Level 1

### 📋 Операционная документация
- [OPERATIONS.md](OPERATIONS.md) - Руководство по эксплуатации
- [Troubleshooting.md](Troubleshooting.md) - Устранение неполадок

### 🔌 API и интеграции
- [API.md](API.md) - API документация

### 📝 Планирование
- [update_plan.md](../update_plan.md) - План улучшений

---

## 🎯 Быстрый старт

### Установка
```bash
# Клонировать репозиторий
git clone <gitverse-repo-url> vps-fortify
cd vps-fortify

# Запустить начальную настройку
bash start.sh

# Проверить compliance
python3 cis_manager.py audit
```

### Основные команды
```bash
# Аудит системы
python3 cis_manager.py audit

# Применить исправления
python3 cis_manager.py fix --force

# Генерировать документацию
python3 scripts/docs_generator.py

# Проверить compliance
python3 scripts/check_compliance.py --threshold 95
```

### Переменные окружения
```bash
export BW_EMAIL="your@email.com"
export BW_PASSWORD="your-password"
export GITVERSE_TOKEN="your-token"
export CIS_TARGET="95"
```

---

## 📚 Структура документации

### Для разработчиков
- [ARCHITECTURE.md](ARCHITECTURE.md) - Архитектура системы
- [API.md](API.md) - API документация

### Для DevOps инженеров
- [AGENTS.md](../AGENTS.md) - AI Employee документация
- [OPERATIONS.md](OPERATIONS.md) - Руководство по эксплуатации
- [Troubleshooting.md](Troubleshooting.md) - Устранение неполадок

### Для аудиторов безопасности
- [CIS_STANDARDS.md](CIS_STANDARDS.md) - Стандарты CIS Debian 12 Level 1

---

## 🔗 Связанные ресурсы

- [CIS Debian 12 Benchmark](https://www.cisecurity.org/cis-benchmarks/)
- [GitVerse Documentation](https://gitverse.ru/docs)
- [Bitwarden API](https://bitwarden.com/help/api/)
- [Debian Security Hardening](https://wiki.debian.org/SecurityHardening)

---

*Документация обновляется автоматически AI Employee*
