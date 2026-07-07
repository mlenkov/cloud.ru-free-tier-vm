# ADR-003: AIDE background init + poll

## Статус
Accepted

## Контекст
`aideinit` генерирует базу хешей (SHA-512) для всех файлов в файловой системе.
На 2 vCPU это занимает ~2 минуты. Блокировать deploy.sh на это время — плохой UX.
Деплой должен завершаться за <30 секунд в типичном сценарии.

## Решение
Два подхода, работающих вместе:

1. **Фоновый запуск**: `aideinit --background` — процесс сразу возвращает управление
2. **Polling**: цикл 30×10 секунд (до 5 минут) ожидания `/var/lib/aide/aide.db.new`:

```bash
aideinit --background
for i in $(seq 1 30); do
    sleep 10
    if [ -f /var/lib/aide/aide.db.new ]; then
        mv /var/lib/aide/aide.db.new /var/lib/aide/aide.db
        break
    fi
done
```

Если aide.db уже существует — инициализация пропускается (идемпотентность).

## Альтернативы
- **Синхронный aideinit**: блокирует deploy на ~2 минуты
- **Pre-built DB в репозитории**: антипаттерн — хеши не соответствуют live-системе
- **Отложить инициализацию**: AIDE не активен до первого запуска, security gap

## Последствия
- Dploy.sh завершается за ~10 секунд (без учёта AIDE init)
- В худшем случае (aideinit затянулся) — timeout 5 минут
- Если aide.db.new не появился за 5 минут — deploy продолжается без AIDE (logged)
- При повторном запуске deploy.sh — aide.db уже есть, init пропускается
- AIDE аудит: `aide --check` вручную или через cron при необходимости
