# 🐛 Устранение неполадок GitVerse VPS Fortify

## 📋 Обзор

Это руководство содержит решения для типичных проблем при использовании системы GitVerse VPS Fortify.

---

## 🔧 Проблемы с cis_manager.py

### Проблема 1: Требуется root

**Ошибка**:
```
❌ Требуется root (используйте sudo)
```

**Решение**:
```bash
# Запустить с правами root
sudo python3 cis_manager.py audit

# Или переключиться на root
sudo su -
python3 cis_manager.py audit
```

**Проверка**:
```bash
# Проверить текущего пользователя
whoami

# Проверить права
id
```

---

### Проблема 2: input() блокирует автоматизацию

**Ошибка**:
```
Enter to continue...
# Скрипт завис на input()
```

**Решение**:
```bash
# Использовать флаг --force
python3 cis_manager.py audit --force
python3 cis_manager.py fix --force

# Или установить переменную окружения
export NON_INTERACTIVE=1
python3 cis_manager.py fix
```

**Исправление в коде**:
```python
# Добавить проверку
if os.environ.get('NON_INTERACTIVE', '0') == '1':
    return True
```

---

### Проблема 3: sys.exit() нарушает CI/CD

**Ошибка**:
```
# Скрипт аварийно завершается
# CI/CD не получает код ошибки
```

**Решение**:
```python
# Заменить sys.exit() на возврат кода
return 1  # вместо sys.exit(1)

# В main():
sys.exit(main())
```

---

### Проблема 4: Shell=True уязвимость

**Ошибка**:
```
# Команда с shell=True
subprocess.run(cmd, shell=True)
```

**Решение**:
```python
# Использовать shlex.split()
import shlex
subprocess.run(shlex.split(cmd), check=True)
```

---

## 🔑 Проблемы с Bitwarden

### Проблема 1: BW_SESSION not found

**Ошибка**:
```
❌ BW_SESSION not found
```

**Решение**:
```bash
# Логин в Bitwarden
echo "$BW_PASSWORD" | bw login "$BW_EMAIL" --raw

# Получить сессию
export BW_SESSION=$(bw unlock --raw)

# Проверить
bw status
```

---

### Проблема 2: Failed to login to Bitwarden

**Ошибка**:
```
❌ Failed to login to Bitwarden
```

**Решение**:
```bash
# Проверить учетные данные
echo $BW_EMAIL
echo $BW_PASSWORD

# Проверить подключение
bw status

# Перелогиниться
echo "$BW_PASSWORD" | bw login "$BW_EMAIL" --raw
```

---

### Проблема 3: Secret not found

**Ошибка**:
```
❌ Secret not found: gitverse/credentials/token
```

**Решение**:
```bash
# Проверить доступные секреты
bw list items

# Создать секрет
bw create item --name "gitverse-credentials" \
  --username "token" \
  --password "$GITVERSE_TOKEN"

# Проверить
bw get item "gitverse-credentials"
```

---

## 📋 Проблемы с GitVerse CI/CD

### Проблема 1: Pipeline падает

**Признаки**:
- CI/CD статус: Failed
- Ошибки в логах

**Решение**:
```bash
# 1. Проверить логи
gitlab-ci-local --show-log

# 2. Проверить переменные
gitlab-ci-local --show-env

# 3. Протестировать локально
bash scripts/test_pipeline.sh
```

---

### Проблема 2: Переменные окружения не передаются

**Ошибка**:
```
⚠️  GITVERSE_TOKEN not found
```

**Решение**:
```yaml
# .gitlab-ci.yml
variables:
  GITVERSE_TOKEN: "${GITVERSE_TOKEN}"
  BW_SESSION: "${BW_SESSION}"

# Проверить в pipeline
script:
  - echo $GITVERSE_TOKEN  # Должно быть видно
  - echo $BW_SESSION
```

---

### Проблема 3: Artifacts не сохраняются

**Ошибка**:
```
# Файлы не передаются между stages
```

**Решение**:
```yaml
# .gitlab-ci.yml
setup:
  script:
    - python3 cis_manager.py audit
  artifacts:
    paths:
      - cis_data/
    expire_in: 1 week

verify:
  needs:
    - setup
  script:
    - python3 scripts/check_compliance.py
```

---

## 📊 Проблемы с compliance

### Проблема 1: Compliance ниже 95%

**Признаки**:
```
❌ Compliance check failed (85% < 95%)
```

**Решение**:
```bash
# 1. Запустить аудит
python3 cis_manager.py audit

# 2. Посмотреть проваленные проверки
cat cis_data/audit.json | jq '.checks[] | select(.status == "failed")'

# 3. Применить исправления
python3 cis_manager.py fix --force

# 4. Проверить результат
python3 scripts/check_compliance.py --threshold 95
```

---

### Проблема 2: Невозможно исправить некоторые проверки

**Признаки**:
```
⚠️  Cannot fix: Check requires manual intervention
```

**Решение**:
```bash
# 1. Посмотреть описание проверки
cat cis_data/audit.json | jq '.checks[] | select(.status == "failed") | .description'

# 2. Применить исправление вручную
# Следовать рекомендациям в cis_data/manual_fixes.md

# 3. Проверить
python3 cis_manager.py audit
```

---

### Проблема 3: Неверная версия CIS

**Признаки**:
```
⚠️  CIS version mismatch: expected Debian 12, got Debian 11
```

**Решение**:
```bash
# 1. Проверить версию ОС
cat /etc/os-release

# 2. Обновить config
cat > config/cis_standard.yaml <<EOF
cis_version: "Debian 12 Level 1"
EOF

# 3. Запустить аудит
python3 cis_manager.py audit
```

---

## 📁 Проблемы с файловой системой

### Проблема 1: Недостаточно места

**Признаки**:
```
❌ No space left on device
```

**Решение**:
```bash
# 1. Проверить место
df -h

# 2. Очистить кэш
apt clean
rm -rf /var/cache/apt/archives/*

# 3. Удалить старые логи
journalctl --vacuum-time=7d

# 4. Очистить артефакты
rm -rf cis_data/*_old.json
```

---

### Проблема 2: Ошибка доступа к файлам

**Признаки**:
```
❌ Permission denied: /etc/ssh/sshd_config
```

**Решение**:
```bash
# Запустить с правами root
sudo python3 cis_manager.py audit

# Или изменить права
chmod 644 /etc/ssh/sshd_config
```

---

## 🔌 Проблемы с сетью

### Проблема 1: Bitwarden недоступен

**Признаки**:
```
❌ Failed to connect to Bitwarden API
```

**Решение**:
```bash
# 1. Проверить подключение
ping api.bitwarden.com

# 2. Проверить firewall
ufw status

# 3. Открыть порт
ufw allow 443
```

---

### Проблема 2: GitVerse недоступен

**Признаки**:
```
❌ Failed to connect to GitVerse API
```

**Решение**:
```bash
# 1. Проверить подключение
ping gitverse.ru

# 2. Проверить токен
echo $GITVERSE_TOKEN

# 3. Проверить API
curl -H "PRIVATE-TOKEN: $GITVERSE_TOKEN" https://gitverse.ru/api/v4/projects
```

---

## 🧪 Локальное тестирование

### Проблема: Невозможно протестировать без root

**Решение**:
```bash
# Использовать Docker для тестирования
docker run -it --privileged debian:bookworm bash

# Установить зависимости
apt update && apt install -y python3 jq

# Запустить тест
python3 cis_manager.py audit
```

---

## 📚 Частые ошибки

### Ошибка 1: Неверная версия Python

**Ошибка**:
```
❌ Python 3.11+ required, found 3.9
```

**Решение**:
```bash
# Проверить версию
python3 --version

# Установить новую версию
apt install python3.11
```

---

### Ошибка 2: Отсутствует jq

**Ошибка**:
```
❌ jq not found
```

**Решение**:
```bash
# Установить jq
apt install jq
```

---

### Ошибка 3: Отсутствует git

**Ошибка**:
```
❌ git not found
```

**Решение**:
```bash
# Установить git
apt install git
```

---

## 🔍 Диагностика

### Скрипт диагностики

```bash
#!/bin/bash
# scripts/diagnose.sh

echo "=== System Diagnosis ==="

# Python version
echo "Python: $(python3 --version)"

# Git version
echo "Git: $(git --version)"

# Disk space
echo "Disk: $(df -h / | tail -1 | awk '{print $4}') free"

# Memory
echo "Memory: $(free -h | grep Mem | awk '{print $2}') total"

# Check dependencies
echo "Checking dependencies..."
which python3 jq git

# Check permissions
echo "Permissions: $(whoami)"

echo "=== End Diagnosis ==="
```

---

## 📞 Поддержка

Если проблема не решена:

1. Проверить логи в `cis_data/`
2. Прочитать документацию в `docs/`
3. Создать issue в GitVerse
4. Обратиться к DevOps команде

---

*Устранение неполадок обновляется AI Employee*