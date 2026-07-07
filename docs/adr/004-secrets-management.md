# ADR-004: Secrets management — BSM + manual .env merge

## Статус
Accepted

## Контекст
Проект управляет 7+ секретами: restic/password, cloudru/s3/access-key, cloudru/s3/secret-key,
cloudru/s3/tenant-id, cloudru/s3/bucket, cloudru/s3/endpoint, yandex/disk/token,
github/token. Некоторые пользователи не используют Bitwarden Secrets Manager.

Требования:
- BW_ACCESS_TOKEN никогда не сохранять на диск
- BSM опционально — без него deploy работает с локальным backup
- Ручной .env должен быть совместим с BSM (и BSM может перезаписать устаревшие значения)

## Решение
Двухслойная система с merge и BSM priority:

1. `secrets.py sync` — читает существующий `.env` → запрашивает BSM → мерджит (BSM перезаписывает) → пишет `.env` (chmod 600)
2. Кастомные ключи из `.env` (которых нет в BSM) сохраняются — нестираемый merge
3. `deploy.sh` — sync не фатален (`|| true`), если `.env` пуст после sync — нотация с примером
4. `secrets.py` — pure functions `_merge_env`, `_parse_env`, `_format_env` вынесены в тестируемые unit-функции

Поток:
```
.env (manual) → secrets.py sync → BSM override → merged .env
                                                     ↓
                                              deploy.sh source .env
                                                     ↓
                                              backup.py / cis_manager.py
```

## Альтернативы
- **Only BSM**: hard dependency, не работает без интернета/токена
- **Only .env**: секреты в незашифрованном файле (хоть и chmod 600), нет централизованного управления
- **Hashicorp Vault**: overkill для single-VPS, сложный bootstrap
- **Mozilla SOPS**: требует GPG/KMS, нет BSM-подобного API
- **Ansible Vault**: зависит от Ansible, проект без Ansible

## Последствия
- BSM опционально — deploy работает без него (local backup only)
- `.env` — root:root chmod 600, никогда не попадает в репозиторий
- Merge идемпотентен — повторный sync не дублирует ключи
- Кастомные env-ключи сохраняются при sync (не только BSM-ключи)
- Тесты: 20 unit-тестов для merge/parse/format логики
- BW_ACCESS_TOKEN — только env var, не пишется на диск (агент передаёт через `sudo BW_ACCESS_TOKEN=...`)
