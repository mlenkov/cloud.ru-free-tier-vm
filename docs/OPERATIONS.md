# 📋 Руководство по эксплуатации GitVerse VPS Fortify

## 🎯 Обзор

Это руководство описывает日常ные задачи по эксплуатации системы GitVerse VPS Fortify.

---

## 📅 Рутинные задачи

### Ежедневные проверки

#### 1. Проверка compliance

```bash
# Запустить аудит
python3 cis_manager.py audit

# Проверить compliance
python3 scripts/check_compliance.py --threshold 95
```

**Ожидаемый результат**: Compliance score ≥ 95%

#### 2. Проверка логов

```bash
# Логи аудита
ls -la cis_data/

# Последний аудит
cat cis_data/audit.json | jq '.timestamp'
```

#### 3. Проверка обновлений

```bash
# Наличие обновлений
apt list --upgradable

# Unattended-upgrades статус
systemctl status unattended-upgrades
```

---

### Еженедельные задачи

#### 1. Резервное копирование

```bash
# Создать бэкап
bash scripts/backup.sh

# Проверить бэкапы
ls -la backups/
```

#### 2. Обновление документации

```bash
# Генерировать README
python3 scripts/docs_generator.py

# Проверить изменения
git diff README.md
```

#### 3. Проверка безопасности

```bash
# Проверить fail2ban
fail2ban-client status

# Проверить ssh
grep "PermitRootLogin" /etc/ssh/sshd_config
```

---

### Ежемесячные задачи

#### 1. Аудит безопасности

```bash
# Полный аудит
python3 cis_manager.py audit --format json

# Генерировать отчет
python3 scripts/generate_report.py
```

#### 2. Обновление конфигурации

```bash
# Проверить изменения в config/
git diff config/cis_standard.yaml

# Применить изменения
python3 cis_manager.py fix --force
```

#### 3. Очистка старых данных

```bash
# Удалить старые артефакты
rm -rf cis_data/*_old.json
rm -rf backups/old/

# Очистить логи
journalctl --vacuum-time=30d
```

---

## 🆘 Чрезвычайные ситуации

### Сценарий 1: Compliance падает ниже 95%

**Признаки**:
- CI/CD pipeline падает
- Compliance score < 95%

**Действия**:

```bash
# 1. Запустить аудит
python3 cis_manager.py audit

# 2. Проверить.failed файл
cat cis_data/audit.json | jq '.checks[] | select(.status == "failed")'

# 3. Применить исправления
python3 cis_manager.py fix --force

# 4. Проверить результат
python3 scripts/check_compliance.py --threshold 95
```

---

### Сценарий 2: Система не загружается после исправлений

**Признаки**:
- Сервер недоступен
- SSH не подключается

**Действия**:

```bash
# 1. Восстановить из бэкапа
ls -la backups/
cp backups/latest/* /

# 2. Перезагрузить сервисы
systemctl restart sshd
systemctl restart fail2ban

# 3. Проверить статус
systemctl status sshd
systemctl status fail2ban
```

---

### Сценарий 3: Ошибка Bitwarden

**Признаки**:
- `Failed to login to Bitwarden`
- `BW_SESSION not found`

**Действия**:

```bash
# 1. Проверить переменные
echo $BW_EMAIL
echo $BW_PASSWORD

# 2. Перелогиниться
echo "$BW_PASSWORD" | bw login "$BW_EMAIL" --raw

# 3. Проверить сессию
bw status
```

---

## 📊 Мониторинг и алерты

### Метрики для мониторинга

| Метрика | Цель | Критический |
|---------|------|-------------|
| Compliance Score | ≥95% | <90% |
| Audit Duration | <5 min | >10 min |
| Failed Checks | 0 | >5 |
| Backup Size | <1GB | >5GB |
| Error Rate | 0 | >1/hour |

---

### Алерты в CI/CD

```yaml
# .gitlab-ci.yml
compliance_check:
  script:
    - python3 scripts/check_compliance.py --threshold 95
  allow_failure: false
  on_failure:
    - notify_admins
```

---

## 🔄 Обновление системы

### Обновление cis_manager.py

```bash
# 1. Проверить изменения
git pull origin main

# 2. Протестировать
python3 cis_manager.py audit

# 3. Применить
python3 cis_manager.py fix --force
```

### Обновление зависимостей

```bash
# Установить новые пакеты
bash scripts/setup.sh

# Проверить
python3 cis_manager.py audit
```

---

## 📁 Архивирование данных

### Структура архива

```
archives/
├── 2024-01-01/
│   ├── audit.json
│   ├── report.html
│   └── logs/
│       ├── setup.log
│       └── fix.log
└── 2024-01-15/
    ├── audit.json
    └── report.html
```

### Автоматическое архивирование

```bash
#!/bin/bash
# scripts/archive.sh

DATE=$(date +%Y-%m-%d)
ARCHIVE_DIR="archives/$DATE"

mkdir -p "$ARCHIVE_DIR"

cp cis_data/audit.json "$ARCHIVE_DIR/"
cp README.md "$ARCHIVE_DIR/"

echo "Archived to $ARCHIVE_DIR"
```

---

## 🧪 Тестирование

### Локальное тестирование

```bash
# 1. Создать тестовую машину
vagrant up

# 2. Запустить аудит
python3 cis_manager.py audit

# 3. Проверить результат
python3 scripts/check_compliance.py --threshold 95
```

### CI/CD тестирование

```yaml
test:
  script:
    - bash scripts/test_setup.sh
    - python3 cis_manager.py audit
    - python3 scripts/check_compliance.py --threshold 95
  artifacts:
    paths:
      - cis_data/
    reports:
      junit: cis_data/test-results.xml
```

---

## 📚 Дополнительные ресурсы

- [AGENTS.md](AGENTS.md) - Документация AI Employee
- [Troubleshooting.md](Troubleshooting.md) - Устранение неполадок
- [API.md](API.md) - API документация

---

*Руководство обновляется AI Employee*