# 🏗️ Архитектура GitVerse VPS Fortify

## 📋 Обзор архитектуры

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GitVerse CI/CD                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐ │
│  │   Setup      │  │   Verify     │  │   Docs       │  │  Merge  │ │
│  │   Stage      │  │   Stage      │  │   Stage      │  │  Check  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬────┘ │
│         │                  │                  │               │       │
│         └──────────────────┴──────────────────┘               │       │
│                            │                                  │       │
│                            ▼                                  ▼       │
│              ┌───────────────────────────┐           ┌─────────────┐  │
│              │   AI Employee (Agent)     │           │  GitVerse   │  │
│              │   ┌───────────────────┐   │           │   Webhook   │  │
│              │   │  cis_manager.py   │   │           │  Handler    │  │
│              │   │  docs_generator.py│   │           └──────┬──────┘  │
│              │   │  check_compliance.py│  │                  │       │
│              │   └───────────────────┘   │                  │       │
│              └───────────┬───────────────┘                  │       │
└──────────────────────────┼───────────────────────────────────┼───────┘
                           │                                   │
        ┌──────────────────┼──────────────────┐                │
        │                  │                  │                │
        ▼                  ▼                  ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐
│   CIS        │  │   Bitwarden  │  │   GitVerse   │  │   GitLab    │
│   Manager    │  │   Secrets    │  │   API        │  │   Runner    │
│   (Python)   │  │   Vault      │  │              │  │  (Optional) │
└──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘
```

---

## 🧩 Компоненты системы

### 1. AI Employee (Agent)

**Файлы**: `cis_manager.py`, `scripts/`

**Ответственность**:
- CIS compliance auditing
- Security remediation
- Documentation generation
- Compliance verification

**Основные команды**:
```bash
python3 cis_manager.py audit        # Аудит
python3 cis_manager.py fix --force  # Исправление
python3 scripts/docs_generator.py   # Документация
python3 scripts/check_compliance.py # Валидация
```

**Архитектура**:
```
cis_manager.py
├── CISManager class
│   ├── _init_checks()          # Регистрация проверок
│   ├── audit()                 # Запуск аудита
│   ├── fix()                   # Исправление
│   └── _run_cmd()              # Выполнение команд
├── CheckResult dataclass
└── AuditReport dataclass
```

### 2. GitVerse CI/CD Pipeline

**Файл**: `.gitlab-ci.yml`

**Этапы**:
1. **Setup** - Применение CIS стандартов
2. **Verify** - Проверка compliance
3. **Docs** - Генерация документации
4. **Merge Check** - Проверка перед мержем

**Конфигурация**:
```yaml
variables:
  BW_SESSION: "${BW_SESSION}"
  GITVERSE_TOKEN: "${GITVERSE_TOKEN}"
  CIS_TARGET: "95"

stages:
  - setup
  - verify
  - docs
  - merge_check
```

### 3. Bitwarden Secrets Manager

**Роль**: Безопасное хранение секретов

**Секреты**:
- `bitwarden/credentials/url` - API URL
- `bitwarden/credentials/master_password` - Master password
- `gitverse/credentials/token` - GitVerse token

**Интеграция**:
```bash
# Login
echo "$BW_PASSWORD" | bw login "$BW_EMAIL" --raw

# Get secret
bw get item "server-credentials"
```

### 4. Configuration Files

**Файлы**: `config/cis_standard.yaml`, `config/templates/`

**Структура**:
```yaml
cis_version: "Debian 12 Level 1"
compliance_target: 95

checks:
  network:
    - cis_id: "3.1"
      description: "IP forwarding disabled"
      required: true
  ssh:
    - cis_id: "5.2"
      description: "Root login disabled"
      required: true
```

---

## 🔄 Поток данных

### Стадия Setup

```
1. GitVerse CI triggers pipeline
   ↓
2. start.sh executes
   - Update system
   - Install dependencies
   - Configure Bitwarden
   ↓
3. cis_manager.py audit
   - Run all CIS checks
   - Generate audit.json
   ↓
4. cis_manager.py fix --force
   - Apply fixes
   - Create backups
   ↓
5. Store artifacts
   - cis_data/
   - audit.json
```

### Стадия Verify

```
1. Load artifacts
   ↓
2. Run audit
   - python3 cis_manager.py audit --format json
   ↓
3. Validate compliance
   - python3 scripts/check_compliance.py --threshold 95
   ↓
4. Generate report
   - Save to artifacts
```

### Стадия Docs

```
1. Load audit data
   ↓
2. Generate README.md
   - python3 scripts/docs_generator.py
   ↓
3. Commit and push
   - git add README.md
   - git commit -m "docs: update"
   - git push
```

---

## 🎯 Принципы архитектуры

### 1. Modularity
- CIS Manager - отдельный модуль
- Scripts - независимые утилиты
- Config - внешние настройки

### 2. Idempotency
- Повторный запуск без изменений
- Проверка текущего состояния
- Backup перед изменениями

### 3. GitOps
- All config in git
- Self-documenting
- Audit trail

### 4. Minimal Dependencies
- Python stdlib only
- No Docker required
- Lightweight scripts

### 5. Security First
- Secrets in Bitwarden
- No hardcoded passwords
- Run as root only when needed

---

## 📊 Масштабируемость

### Для нескольких серверов

```
gitverse-vps-fortify/
├── servers/
│   ├── server1/
│   │   ├── config.yaml
│   │   └── inventory.ini
│   └── server2/
│       ├── config.yaml
│       └── inventory.ini
├── cis_manager.py
└── scripts/
    ├── deploy_to_server.sh
    └── multi_server_audit.py
```

### CI/CD для нескольких серверов

```yaml
stages:
  - deploy
  - verify

deploy:
  script:
    - bash scripts/deploy_to_server.sh server1
    - bash scripts/deploy_to_server.sh server2
  parallel: 2

verify:
  script:
    - python3 scripts/multi_server_audit.py
```

---

## 🔒 Безопасность

### Уровни безопасности

1. **Код**
   - No hardcoded secrets
   - Input validation
   - Error handling

2. **Конфигурация**
   - Secrets in Bitwarden
   - Environment variables
   - Gitignore sensitive files

3. **Сеть**
   - SSH only
   - Firewall rules
   - Fail2ban

4. **Аудит**
   - All changes logged
   - Audit trail
   - Backup before changes

---

## 🐛 Troubleshooting

### Проблемы с CI/CD
- Check pipeline logs
- Verify environment variables
- Test locally first

### Проблемы с compliance
- Run audit manually
- Check logs in cis_data/
- Review fix commands

### Проблемы с Bitwarden
- Verify credentials
- Check network connectivity
- Test with bw CLI

---

## 📚 Связанные документы

- [AGENTS.md](AGENTS.md) - Документация AI Employee
- [CIS_STANDARDS.md](CIS_STANDARDS.md) - CIS Debian 12 Level 1
- [OPERATIONS.md](OPERATIONS.md) - Руководство по эксплуатации
- [Troubleshooting.md](Troubleshooting.md) - Устранение неполадок

---

*Архитектура обновляется AI Employee*
