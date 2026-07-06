# Prompt for next full deploy test

Скопируй и отправь новой сессии агента:

---

Начать настройку сервера с нуля. Репозиторий уже склонирован.

```
IP: 91.224.87.211
SSH user: mais
SSH key: ~/.ssh/MacBuka
BW_ACCESS_TOKEN: 0.6e3719e7-f47a-42e3-b650-b47e00fed076.DlnbeCArEFhvzW1GCHgR4F3YoqJEBT:VKIXCtkhwFTO41rzMgbZLA==
```

Выполни шаги:

1. SSH на сервер (с `-o ServerAliveInterval=60`), сделать `git pull` в `~/cloud.ru-free-tier-vm/`
2. Запустить: `sudo BW_ACCESS_TOKEN="<токен>" bash deploy.sh`
3. Дождись полного завершения deploy.sh

После завершения составь отчёт со следующими секциями:

### Общая информация
- IP, hostname, версия ОС

### Secrets
- Сколько секретов синхронизировано из Bitwarden
- Какие именно (список ключей)

### CIS Audit
- Результаты до fix (PASS/FAIL/Error)
- Результаты после fix
- Compliance %
- Сколько проверок всего

### Backup
- Локальный: статус
- S3: статус (должен работать)
- Yandex Disk: статус
- Cron: настроен/нет

### Ошибки и баги
- Какие ошибки встретились в процессе
- Любые неожиданные ⏭️ или ❌

### AIDE
- Статус инициализации БД (`aide.db` должна быть активирована, не `aide.db.new`)
- Время инициализации

### Что должно работать (все фиксы применены)
- Secrets 7/7 с оригинальными ключами
- CIS 59/59 (100%) + fail2ban с systemd backend
- Backup: Local + S3 + Yandex Disk (все три)
- AIDE: автоматическая активация БД (poll до 5 мин)
- `backup.py status`: работает от любого пользователя (cron через sudo)
- SSH: не обрывается по таймауту (ServerAliveInterval=60)

## Ускоренное тестирование
Для полного цикла без переустановки ОС:
```bash
ssh -o ServerAliveInterval=60 -i ~/.ssh/MacBuka mais@91.224.87.211
cd ~/cloud.ru-free-tier-vm && git pull
sudo BW_ACCESS_TOKEN="<токен>" python3 scripts/test_deploy.py
```
Скрипт сделает снепшот → deploy → audit → rollback → verify → re-deploy → отчёт.
