#!/usr/bin/env python3
"""
Bitwarden Secrets Manager — sync, get, set, list
AI Employee: управление секретами для VPS
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _get_token() -> str:
    token = os.environ.get("BW_ACCESS_TOKEN")
    if not token:
        print("❌ BW_ACCESS_TOKEN не задан")
        print("   Получите токен в Bitwarden Secrets Manager: Settings → Access Tokens")
        print("   Или создайте .env вручную (см. README.md → Секреты)")
        sys.exit(1)
    return token


def _create_client():
    try:
        from bws_sdk import BWSecretClient, Region
    except ImportError:
        print("❌ bws-sdk не установлен")
        print("   Установите: pip install bws-sdk")
        print("   Или создайте .env вручную (см. README.md → Секреты)")
        sys.exit(1)
    token = _get_token()
    region = Region(
        api_url=os.environ.get("BW_API_URL", "https://api.bitwarden.com"),
        identity_url=os.environ.get("BW_IDENTITY_URL", "https://identity.bitwarden.com"),
    )
    return BWSecretClient(region=region, access_token=token)


def _merge_env(existing: dict, secrets: list) -> dict:
    """Merge existing .env with BSM secrets. BSM values override existing."""
    merged = dict(existing)
    if secrets:
        for s in secrets:
            merged[s.key] = s.value
    return merged


def _parse_env(text: str) -> dict:
    """Parse .env file content into a dict."""
    env = {}
    for line in text.strip().split("\n"):
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env


def _format_env(env: dict) -> str:
    """Format dict as .env file content (var='value')."""
    lines = []
    for k, v in env.items():
        escaped = v.replace("'", "'\\''")
        lines.append(f"{k}='{escaped}'")
    return "\n".join(lines) + "\n"


def cmd_sync(args):
    output_path = Path(args.output) if args.output else Path(".env")

    # 1. Read existing .env as base (если есть)
    existing = {}
    if output_path.exists():
        existing = _parse_env(output_path.read_text(encoding="utf-8"))

    # 2. BSM override + merge
    client = _create_client()
    print(f"🔑 Организация: {client.auth.org_id}")

    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    result = client.sync(last_synced_date=old_date)
    bsm_secrets = result if isinstance(result, list) else result.secrets

    if bsm_secrets:
        print(f"📦 Найдено секретов BSM: {len(bsm_secrets)}")
        for s in bsm_secrets:
            print(f"  ✅ {s.key}")

    merged = _merge_env(existing, bsm_secrets)

    if existing and bsm_secrets:
        overlap = set(existing.keys()) & set(s.key for s in bsm_secrets)
        if overlap:
            print(f"  🔄 BSM перезаписал: {', '.join(overlap)}")
        kept = set(existing.keys()) - set(s.key for s in bsm_secrets)
        if kept:
            print(f"  💾 Сохранено из .env (нет в BSM): {len(kept)}")

    if not merged:
        print("⚠️  Секреты не найдены (ни BSM, ни .env)")
        return

    # 3. Write merged
    output_path.write_text(_format_env(merged), encoding="utf-8")
    output_path.chmod(0o600)
    print(f"\n✅ Секреты сохранены в {output_path} (chmod 600, {len(merged)} ключей)")


def cmd_get(args):
    client = _create_client()

    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    result = client.sync(last_synced_date=old_date)
    secrets = result if isinstance(result, list) else result.secrets

    for s in secrets:
        if s.key == args.key:
            print(s.value)
            return

    print(f"❌ Секрет '{args.key}' не найден")
    sys.exit(1)


def cmd_set(args):
    print("⚠️  Создание/обновление секретов через API требует клиентского шифрования.")
    print("   Рекомендуется создавать секреты в Bitwarden Secrets Manager UI.")
    print(f"   Для создания вручную используйте:")
    print(f"   https://vault.bitwarden.com/#/organizations/{_create_client().auth.org_id}/secrets")
    sys.exit(1)


def cmd_list(args):
    client = _create_client()

    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    result = client.sync(last_synced_date=old_date)
    secrets = result if isinstance(result, list) else result.secrets

    if not secrets:
        print("⚠️  Секреты не найдены")
        return

    print(f"{'KEY':<40} {'ID':<36}")
    print("-" * 78)
    for s in secrets:
        print(f"{s.key:<40} {s.id}")


def main():
    parser = argparse.ArgumentParser(
        description="Bitwarden Secrets Manager — управление секретами VPS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s sync                      # Загрузить все секреты в .env
  %(prog)s get restic/password       # Получить значение секрета
  %(prog)s list                      # Список всех секретов

Переменные окружения:
  BW_ACCESS_TOKEN   - Токен machine-to-machine (обязательно)
  BW_API_URL        - API URL (по умолч. https://api.bitwarden.com)
  BW_IDENTITY_URL   - Identity URL (по умолч. https://identity.bitwarden.com)
  BW_ORG_ID         - Больше не требуется (извлекается из JWT)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Команды")

    sync_parser = subparsers.add_parser("sync", help="Загрузить секреты в .env")
    sync_parser.add_argument("--output", "-o", help="Файл для сохранения (по умолч. .env)")

    get_parser = subparsers.add_parser("get", help="Получить секрет")
    get_parser.add_argument("key", help="Ключ секрета")

    set_parser = subparsers.add_parser("set", help="Создать/обновить секрет (требует UI)")
    set_parser.add_argument("key", help="Ключ секрета")
    set_parser.add_argument("value", help="Значение секрета")

    list_parser = subparsers.add_parser("list", help="Список секретов")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "get":
        cmd_get(args)
    elif args.command == "set":
        cmd_set(args)
    elif args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
