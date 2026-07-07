# ADR-001: CIS Debian 12 Level 1

## Статус
Accepted

## Контекст
Для production-сервера требуется измеримый и воспроизводимый уровень безопасности.
CIS (Center for Internet Security) — де-факто стандарт для hardening Debian.
Профиль Level 1 покрывает базовые практики без нарушения работы сервисов.

## Решение
Выбран профиль **CIS Debian 12 Level 1 v1.1.0** (59 checks, 16 категорий).

Профиль реализован через:
- `config/cis_standard.yaml` — декларативное описание 59 проверок с fix-командами
- `cis_manager.py` — audit, fix, history, rollback, с подсчётом compliance (target 95%)
- Конвейер в `deploy.sh`: audit → fix → audit → check_compliance

Проверки охватывают: целостность (AIDE), core dumps, ASLR, fs layout, sudo, PAM, SSH,
systemd, auditd, cron, journald, network (sysctl, nftables), fail2ban, apparmor, updates.

## Альтернативы
- **CIS Level 2**: 167 checks, многие нарушают работу (например, модули ядра). Избыточно.
- **OpenSCAP + SSG**: тяжёлый рантайм (~150 MB), нестабилен на Debian 12.
- **Самописный checklist**: нет стандарта, сложно аудировать.

## Последствия
- Полная автоматизация audit → fix → rollback
- compliance_target = 95% (не 100%, чтобы допускать неизбежные отклонения)
- Compliance_critical_threshold = 80% (alarm)
- 59 checks = 59 unit-тестов безопасности
- Профиль привязан к версии Debian 12 — при major upgrade нужна новая версия профиля
