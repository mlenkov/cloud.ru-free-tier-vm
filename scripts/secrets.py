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
        sys.exit(1)
    return token


def _create_client():
    from bws_sdk import BWSecretClient, Region
    token = _get_token()
    region = Region(
        api_url=os.environ.get("BW_API_URL", "https://api.bitwarden.com"),
        identity_url=os.environ.get("BW_IDENTITY_URL", "https://identity.bitwarden.com"),
    )
    return BWSecretClient(region=region, access_token=token)


def cmd_sync(args):
    client = _create_client()
    print(f"🔑 Организация: {client.auth.org_id}")

    old_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    result = client.sync(last_synced_date=old_date)
    secrets = result if isinstance(result, list) else result.secrets

    if not secrets:
        print("⚠️  Секреты не найдены")
        return

    print(f"📦 Найдено секретов: {len(secrets)}")

    env_data = {}
    for s in secrets:
        env_data[s.key] = s.value
        print(f"  ✅ {s.key}")

    output_path = Path(args.output) if args.output else Path(".env")
    lines = []
    for k, v in env_data.items():
        escaped = v.replace("'", "'\\''")
        lines.append(f"{k}='{escaped}'")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output_path.chmod(0o600)
    print(f"\n✅ Секреты сохранены в {output_path} (chmod 600)")


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
