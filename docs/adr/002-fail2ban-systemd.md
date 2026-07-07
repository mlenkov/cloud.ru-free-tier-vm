# ADR-002: fail2ban backend = systemd

## Статус
Accepted

## Контекст
Debian 12 не пишет логи SSH в `/var/log/auth.log` — journald является основным логгером.
По умолчанию fail2ban ищет `auth.log` и не работает без явного указания backend.

## Решение
В `deploy.sh` генерируется `/etc/fail2ban/jail.local` с `backend = systemd`:

```
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
backend = systemd
maxretry = 3
```

Параметры:
- bantime = 1 час
- findtime = 10 минут
- maxretry = 3 попытки

## Альтернативы
- **journalctl polling**: неэффективно, нет built-in триггеров fail2ban
- **rsyslog + auth.log**: добавление сервиса только ради fail2ban, лишний surface
- **nftables rate-limit**: нет гибкости fail2ban (белые списки, уведомления)

## Последствия
- fail2ban работает на Debian 12 без дополнительной настройки
- systemd journal — единый источник логов для fail2ban
- bantime/findtime/maxretry выбраны для баланса безопасности и UX
- При смене ОС (например, на Ubuntu) нужно проверить backend
