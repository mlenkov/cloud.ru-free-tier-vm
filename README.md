# cloud.ru-free-tier-vm

Автоматическая настройка VPS: CIS Debian 12 Level 1 безопасность, 3-2-1 бэкап, управление секретами.

## Быстрый старт

1. Скопируй репозиторий:
   ```bash
   git clone https://github.com/mlenkov/cloud.ru-free-tier-vm.git
   cd cloud.ru-free-tier-vm
   ```

2. Запусти deploy.sh — всё остальное спросит интерактивно:
   ```bash
   ./deploy.sh
   ```

Скрипт запросит: IP сервера, SSH пользователя, путь к ключу (опционально) и BW_ACCESS_TOKEN.

Что делает: синхронизирует проект на сервер → секреты → CIS аудит → исправление → бэкап → генерация документации.

## Структура проекта

```
cloud.ru-free-tier-vm/
├── deploy.sh               # Установка одной командой (entry point)
├── cis_manager.py          # CIS аудит и исправление
├── config/
│   ├── cis_standard.yaml   # CIS Debian 12 Level 1 проверки
│   ├── backup.yaml         # Конфигурация 3-2-1 бэкапа
│   └── templates/
│       └── server.md       # Шаблон документации
├── scripts/
│   ├── backup.py           # Управление 3-2-1 бэкапом (локально + S3 + Yandex Disk)
│   ├── secrets.py          # Синхронизация с Bitwarden Secrets Manager
│   ├── docs_generator.py   # Генерация документации сервера
│   └── check_compliance.py # Проверка CIS compliance
├── AGENTS.md               # Документация AI Agent
└── README.md               # Этот файл
```

## Требуемые секреты (Bitwarden Secrets Manager)

| Ключ | Описание |
|------|----------|
| `cloudru/s3/access_key` | S3 Access Key |
| `cloudru/s3/secret_key` | S3 Secret Key |
| `cloudru/s3/bucket` | Имя S3 бакета |
| `cloudru/s3/endpoint` | S3 endpoint URL |
| `yandex/disk/token` | Yandex Disk OAuth токен |
| `restic/password` | Пароль шифрования restic |
| `github/token` | GitHub Personal Access Token |

## Возможности

- **CIS Debian 12 Level 1** — 59 проверок в 16 категориях
- **3-2-1 Бэкап** — локальный диск + cloud.ru S3 + Yandex Disk через restic
- **Управление секретами** — Bitwarden Secrets Manager (machine-to-machine)
- **Самодокументирование** — генерирует README сервера с результатами аудита
- **CI/CD готов** — GitHub Actions pipeline включён

## Ручные команды (на сервере)

```bash
python3 cis_manager.py audit          # Запуск CIS аудита
python3 cis_manager.py fix --force    # Применить все исправления
python3 scripts/backup.py create      # Создать 3-2-1 бэкап
python3 scripts/secrets.py sync       # Синхронизация из Bitwarden
```
