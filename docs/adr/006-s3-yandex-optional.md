# ADR-006: S3 + Yandex Disk optional

## Статус
Accepted

## Контекст
Не у всех пользователей есть cloud.ru S3 Object Storage или Yandex Disk.
Деплой не должен фейлиться из-за отсутствия внешних хранилищ.

В то же время, для production-сервера 1-2-1 — обязательный стандарт, и внешние
хранилища должны автоматически подключаться как только credentials появятся.

## Решение
Два принципа:

1. **Graceful skip** — в `backup.py` проверка credentials перед каждым хранилищем:
   - S3: `if s3_key and s3_secret:` — иначе `⏭️ S3 credentials не заданы, пропускаю`
   - Yandex Disk: `if ya_token:` — иначе `⏭️ Yandex Disk token не задан, пропускаю`
   - Yandex Disk без rclone: `if not _check_rclone(): ⏭️ rclone не установлен`

 2. **Zero-config S3 + Yandex** — оба работают при наличии credentials в BSM / .env:
    - `restic/password` обязателен (иначе backup не имеет смысла)
    - При отсутствии — ошибка `❌ RESTIC_PASSWORD не задан`
    - `backup/backup.py status` показывает статус каждого хранилища: `S3: настроен / не настроен`

Поток:
```
backup.py create
  ├─ S3 — только если cloudru/s3/access-key + cloudru/s3/secret-key
  └─ Yandex Disk — только если yandex/disk/token + rclone установлен
```

## Альтернативы
- **Fail hard**: плохой UX — deploy падает на первом деплое
- **Интерактивный prompt**: deploy.sh не-interactive, не подходит
- **Отдельные конфигурационные профили**: over-engineering для single-сервера
- **Soft-fail (continue on error)**: логи ошибок, но backup считается успешным — вводит в заблуждение

## Последствия
- S3 + Yandex = zero-config при наличии credentials
- S3/Yandex auto-enable — достаточно добавить ключи в BSM / .env
- `backup.py status` — прозрачный статус: `S3: настроен` / `не настроен`
- `deploy.sh` не зависит от внешних хранилищ — `|| true` на все backup-команды
- При добавлении нового хранилища в будущем — паттерн уже задан (guard → skip message → optional init)
- Retention-очистка тоже опциональна — только для настроенных хранилищ
