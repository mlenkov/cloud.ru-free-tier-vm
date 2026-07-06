# Руководство по эксплуатации

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    Локальная машина                      │
│  ./deploy.sh <ip>  ─── tar + scp ──────────────────┐    │
└─────────────────────────────────────────────────────┘    │
                                                          ▼
┌─────────────────────────────────────────────────────────┐
│                    Сервер (Debian 12)                     │
│  ┌──────────┐  ┌────────────┐  ┌───────────┐           │
│  │ deploy   │  │ CIS        │  │ Backup    │           │
│  │ .sh      │  │ Manager    │  │ (restic)  │           │
│  │ (bash)   │──▶ (Python)   │──▶ 3-2-1     │           │
│  └──────────┘  └─────┬──────┘  └───────────┘           │
│                      │                                  │
│                      ▼                                  │
│  ┌─────────────────────────────────────┐                │
│  │ 59 CIS checks → audit → fix → docs │                │
│  └─────────────────────────────────────┘                │
│                                                         │
│  Secrets: Bitwarden Secrets Manager (BSM)               │
│  Storage: S3 (cloud.ru) + Yandex Disk (rclone)          │
└─────────────────────────────────────────────────────────┘
```

**Компоненты:**

| Компонент | Файл | Роль |
|-----------|------|------|
| Entry point | `deploy.sh` | tar+scp на сервер, запуск pipeline |
| CIS аудит | `cis_manager.py` | 59 проверок, audit + fix |
| Секреты | `scripts/secrets.py` | sync из BSM в `.env` (root:root 600) |
| Backup | `scripts/backup.py` | restic: local + S3 + Yandex Disk |
| Документация | `scripts/docs_generator.py` | server.md → `docs/SERVER.md` |
| CI/CD | `.github/workflows/deploy.yml` | GitHub Actions pipeline |
| Config | `config/backup.yaml` | настройки backup (без хардкодов) |

---

## CIS Debian 12 Level 1 — 59 проверок

Весь реестр проверок живёт в `cis_manager.py:_build_check_registry()`.

**Категории:**

| Категория | Проверок | Что проверяет |
|-----------|----------|---------------|
| Network | 10 | IP forwarding, ICMP redirects, rp_filter, martians |
| SSH | 14 | Root login, MaxAuthTries, ciphers, MACs, PermitTunnel |
| Authentication | 5 | PASS_MAX_DAYS, PASS_MIN_DAYS, UMASK |
| File Permissions | 8 | /etc/passwd, shadow, group, fstab, sudoers |
| Fail2ban | 4 | установлен, активен, maxretry, bantime |
| Updates | 4 | unattended-upgrades, needrestart, auto-reboot |
| Core Dumps | 4 | fs.suid_dumpable, limits.conf |
| Banners | 4 | issue, issue.net, sshd Banner |
| Audit | 6 | aide, auditd, rsyslog |

**Команды:**
```bash
python3 cis_manager.py audit          # проверка
python3 cis_manager.py fix --force    # исправление
```

---

## Операции

### Ежедневно
```bash
# Статус compliance
python3 cis_manager.py audit

# Статус backup
python3 scripts/backup.py status
```

### Еженедельно
```bash
# Полный backup
python3 scripts/backup.py create

# Обновление документации
python3 scripts/docs_generator.py

# Проверка безопасности
fail2ban-client status
grep "PermitRootLogin" /etc/ssh/sshd_config
```

### Backup / Restore

```bash
# Создать backup
python3 scripts/backup.py create

# Статус
python3 scripts/backup.py status

# Восстановление (список snapshot-ов)
restic -r /var/backups/cloud.ru-free-tier-vm snapshots
restic -r /var/backups/cloud.ru-free-tier-vm restore latest --target /
```

Backup автоматически запускается по cron в 2:00 ежедневно.

### Secrets
```bash
# Синхронизация из Bitwarden Secrets Manager
BW_ACCESS_TOKEN=bws_token_xxx python3 scripts/secrets.py sync
```

---

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| dpkg conffile prompt | `DEBIAN_FRONTEND=noninteractive` (уже в deploy.sh) |
| pip externally-managed | `--break-system-packages` (уже в deploy.sh) |
| aideinit 100% CPU | `aideinit --background`, проверь через 5 мин |
| Compliance < 100% | `audit` → `fix --force` → `audit` |
| BW_ACCESS_TOKEN not found | `export BW_ACCESS_TOKEN=...` (никогда в файл) |
| No space left | `apt clean` + `journalctl --vacuum-time=7d` |
| restore не работает | проверь `restic check`, `restic unlock` |

### Диагностика
```bash
echo "Python: $(python3 --version)"
echo "Disk: $(df -h / | tail -1 | awk '{print $4}') free"
echo "Memory: $(free -h | grep Mem | awk '{print $2}') total"
```

---

## Decision Log

Все архитектурные решения — в `docs/adr/INDEX.md`.
