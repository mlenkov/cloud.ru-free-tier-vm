#!/usr/bin/env python3
"""
Backup 3-2-1 Manager — restic + cloud.ru S3 + Yandex Disk
AI Employee: автоматическое резервное копирование VPS
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path("config/backup.yaml")


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"❌ Конфиг не найден: {CONFIG_PATH}")
        print("   Запустите: python3 scripts/backup.py setup")
        sys.exit(1)

    try:
        import yaml
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        print("❌ PyYAML не установлен (pip install pyyaml)")
        sys.exit(1)


def _run(cmd: list, env: dict = None, timeout: int = 3600) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=merged_env)
    except subprocess.TimeoutExpired:
        print(f"❌ Команда превысила таймаут {timeout}с: {' '.join(cmd)}")
        sys.exit(1)


def _check_restic() -> bool:
    result = _run(["restic", "version"], timeout=10)
    if result.returncode != 0:
        print("❌ restic не установлен. Установите: brew install restic / apt install restic")
        return False
    return True


def _check_rclone() -> bool:
    result = _run(["rclone", "version"], timeout=10)
    if result.returncode != 0:
        print("   ⚠️  rclone не установлен. Установите: brew install rclone / apt install rclone")
        return False
    return True


def _yadisk_config_file(token: str) -> Path:
    """Create a temporary rclone config file for Yandex Disk."""
    import tempfile, json
    token_json = json.dumps({
        "access_token": token,
        "token_type": "bearer",
        "refresh_token": token,
    })
    cf = tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False)
    cf.write(f"[yadisk]\ntype = yandex\nclient_id =\nclient_secret =\ntoken = {token_json}\n")
    cf.close()
    return Path(cf.name)


def _load_env(env_file: Path = Path(".env")) -> dict:
    env = {}
    if env_file.exists():
        for line in env_file.read_text().strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env[k] = v
                nk = k.replace('/', '_').replace('-', '_').upper()
                if nk != k:
                    env[nk] = v
    return env


def cmd_create(args):
    config = _load_config()
    if not _check_restic():
        sys.exit(1)

    env = _load_env()
    backup_cfg = config.get("backup", {})
    local_path = backup_cfg.get("local_path", "/var/backups/cloud.ru-free-tier-vm")
    sources = backup_cfg.get("sources", ["/etc", "/home", "/var/www"])
    restic_pass = env.get("restic/password") or os.environ.get("RESTIC_PASSWORD")

    if not restic_pass:
        print("❌ RESTIC_PASSWORD не задан (секрет restic/password)")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    print(f"💾 Backup 3-2-1 — {timestamp}")
    print("=" * 60)

    # --- Copy 1: Local backup ---
    print(f"\n📀 Copy 1: Local -> {local_path}")
    local_repo = f"local:{local_path}"
    restic_env = {"RESTIC_REPOSITORY": local_repo, "RESTIC_PASSWORD": restic_pass}

    rc = _run(["restic", "snapshots"], env=restic_env, timeout=30).returncode
    if rc != 0:
        print("   ⚠️  Инициализация локального репозитория...")
        _run(["restic", "init"], env=restic_env)

    result = _run(["restic", "backup"] + sources, env=restic_env)
    if result.returncode == 0:
        print(f"   ✅ Локальный backup завершён")
    else:
        print(f"   ❌ Ошибка: {result.stderr.strip()[-200:]}")

    # --- Copy 2: cloud.ru S3 ---
    print(f"\n☁️  Copy 2: cloud.ru S3")
    s3_key = env.get("cloudru/s3/access-key") or os.environ.get("AWS_ACCESS_KEY_ID")
    s3_secret = env.get("cloudru/s3/secret-key") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    s3_cfg = backup_cfg.get("s3", {})
    s3_bucket = s3_cfg.get("bucket") or env.get("cloudru/s3/bucket") or ""
    s3_endpoint = s3_cfg.get("endpoint") or env.get("cloudru/s3/endpoint") or ""
    s3_prefix = s3_cfg.get("prefix", "")
    s3_region = s3_cfg.get("region", "ru-central-1")
    tenant_id = env.get("cloudru/s3/tenant-id")
    if tenant_id and s3_key and ":" not in s3_key:
        s3_key = f"{tenant_id}:{s3_key}"

    if s3_key and s3_secret:
        s3_host = s3_endpoint.replace("https://", "").replace("http://", "")
        s3_path = f"{s3_bucket}/{s3_prefix}".strip("/") if s3_prefix else s3_bucket
        s3_repo = f"s3:{s3_host}/{s3_path}"
        s3_env = {
            "RESTIC_REPOSITORY": s3_repo,
            "RESTIC_PASSWORD": restic_pass,
            "AWS_ACCESS_KEY_ID": s3_key,
            "AWS_SECRET_ACCESS_KEY": s3_secret,
            "AWS_DEFAULT_REGION": s3_region,
        }

        rc = _run(["restic", "snapshots"], env=s3_env, timeout=30).returncode
        if rc != 0:
            print("   ⚠️  Инициализация S3 репозитория...")
            _run(["restic", "init"], env=s3_env)

        result = _run(["restic", "backup"] + sources, env=s3_env)
        if result.returncode == 0:
            print(f"   ✅ S3 backup завершён")
        else:
            print(f"   ❌ Ошибка: {result.stderr.strip()[-200:]}")
    else:
        print("   ⏭️  S3 credentials не заданы, пропускаю")

    # --- Copy 3: Yandex Disk (offsite) ---
    print(f"\n🌐  Copy 3: Yandex Disk (offsite)")
    ya_token = env.get("yandex/disk/token") or os.environ.get("YA_DISK_TOKEN")
    ya_path = backup_cfg.get("yandex_disk", {}).get("path") or env.get("yandex/disk/path") or "/backups/cloud.ru-free-tier-vm"
    yadisk_env = None

    if ya_token:
        yadisk_env = _yadisk_backup(sources, restic_pass, ya_token, ya_path)
    else:
        print("   ⏭️  Yandex Disk token не задан, пропускаю")

    # Prune old snapshots (retention) — все репозитории
    retention = backup_cfg.get("retention", {})
    if retention:
        repos_for_prune = [("local", restic_env)]
        if s3_key and s3_secret:
            repos_for_prune.append(("s3", s3_env))
        if yadisk_env:
            repos_for_prune.append(("yadisk", yadisk_env))

        for name, repo_env in repos_for_prune:
            print(f"\n🧹 Очистка старых snapshot-ов ({name})...")
            forget_cmd = ["restic", "forget"]
            for k, v in retention.items():
                flag = {"keep_daily": "--keep-daily", "keep_weekly": "--keep-weekly",
                        "keep_monthly": "--keep-monthly", "keep_yearly": "--keep-yearly"}.get(k)
                if flag:
                    forget_cmd.extend([flag, str(v)])
            forget_cmd.append("--prune")
            _run(forget_cmd, env=repo_env)

    # Cleanup yadisk temp config
    if yadisk_env and "RCLONE_CONFIG" in yadisk_env:
        Path(yadisk_env["RCLONE_CONFIG"]).unlink(missing_ok=True)

    print(f"\n✅ Backup 3-2-1 завершён: {timestamp}")


def _yadisk_backup(sources: list, restic_pass: str, token: str, remote_path: str) -> Optional[dict]:
    """Backup на Yandex Disk через restic + rclone. Возвращает env для prune."""
    if not _check_rclone():
        print("   ⏭️  rclone не установлен, пропускаю Yandex Disk")
        return None

    config_file = _yadisk_config_file(token)

    repo = f"rclone:yadisk:{remote_path}"
    env = {
        "RESTIC_REPOSITORY": repo,
        "RESTIC_PASSWORD": restic_pass,
        "RCLONE_CONFIG": str(config_file),
        "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
    }

    rc = _run(["restic", "snapshots"], env=env, timeout=30).returncode
    if rc != 0:
        print("   ⚠️  Инициализация Yandex Disk репозитория...")
        _run(["restic", "init"], env=env)

    result = _run(["restic", "backup"] + sources, env=env)
    if result.returncode == 0:
        print(f"   ✅ Yandex Disk backup завершён (restic + rclone)")
    else:
        print(f"   ❌ Ошибка: {result.stderr.strip()[-200:]}")

    return env


def cmd_list(args):
    config = _load_config()
    if not _check_restic():
        sys.exit(1)

    env = _load_env()
    backup_cfg = config.get("backup", {})
    local_path = backup_cfg.get("local_path", "/var/backups/cloud.ru-free-tier-vm")
    restic_pass = env.get("restic/password") or os.environ.get("RESTIC_PASSWORD")

    if not restic_pass:
        print("❌ RESTIC_PASSWORD не задан")
        sys.exit(1)

    for repo_name, repo_url in [("Local", f"local:{local_path}")]:
        env_vars = {"RESTIC_REPOSITORY": repo_url, "RESTIC_PASSWORD": restic_pass}
        result = _run(["restic", "snapshots"], env=env_vars)
        print(f"\n📀 {repo_name}:")
        print(result.stdout if result.returncode == 0 else "   (пусто)")

    s3_key = env.get("cloudru/s3/access-key") or os.environ.get("AWS_ACCESS_KEY_ID")
    s3_secret = env.get("cloudru/s3/secret-key") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    s3_cfg = backup_cfg.get("s3", {})
    s3_endpoint = s3_cfg.get("endpoint") or env.get("cloudru/s3/endpoint") or ""
    s3_bucket = s3_cfg.get("bucket") or env.get("cloudru/s3/bucket") or ""
    s3_prefix = s3_cfg.get("prefix", "")
    s3_region = s3_cfg.get("region", "ru-central-1")
    tenant_id = env.get("cloudru/s3/tenant-id")
    if tenant_id and s3_key and ":" not in s3_key:
        s3_key = f"{tenant_id}:{s3_key}"

    if s3_key and s3_secret:
        s3_host = s3_endpoint.replace("https://", "").replace("http://", "")
        s3_path = f"{s3_bucket}/{s3_prefix}".strip("/") if s3_prefix else s3_bucket
        s3_env = {
            "RESTIC_REPOSITORY": f"s3:{s3_host}/{s3_path}",
            "RESTIC_PASSWORD": restic_pass,
            "AWS_ACCESS_KEY_ID": s3_key,
            "AWS_SECRET_ACCESS_KEY": s3_secret,
            "AWS_DEFAULT_REGION": s3_region,
        }
        result = _run(["restic", "snapshots"], env=s3_env)
        print(f"\n☁️  S3:")
        print(result.stdout if result.returncode == 0 else "   (пусто)")

    ya_token = env.get("yandex/disk/token") or os.environ.get("YA_DISK_TOKEN")
    ya_path = backup_cfg.get("yandex_disk", {}).get("path") or env.get("yandex/disk/path") or "/backups/cloud.ru-free-tier-vm"
    if ya_token and _check_rclone():
        cf = _yadisk_config_file(ya_token)
        ya_env = {
            "RESTIC_REPOSITORY": f"rclone:yadisk:{ya_path}",
            "RESTIC_PASSWORD": restic_pass,
            "RCLONE_CONFIG": str(cf),
            "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        }
        result = _run(["restic", "snapshots"], env=ya_env)
        print(f"\n🌐  Yandex Disk:")
        print(result.stdout if result.returncode == 0 else "   (пусто)")
        Path(cf.name).unlink(missing_ok=True)


def cmd_restore(args):
    config = _load_config()
    if not _check_restic():
        sys.exit(1)

    env = _load_env()
    restic_pass = env.get("restic/password") or os.environ.get("RESTIC_PASSWORD")
    if not restic_pass:
        print("❌ RESTIC_PASSWORD не задан")
        sys.exit(1)

    target = args.target or "/"
    source = args.source or "local"
    backup_cfg = config.get("backup", {})

    if source == "s3":
        s3_key = env.get("cloudru/s3/access-key") or os.environ.get("AWS_ACCESS_KEY_ID")
        s3_secret = env.get("cloudru/s3/secret-key") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        s3_cfg = backup_cfg.get("s3", {})
        s3_bucket = s3_cfg.get("bucket") or env.get("cloudru/s3/bucket") or ""
        s3_endpoint = s3_cfg.get("endpoint") or env.get("cloudru/s3/endpoint") or ""
        s3_prefix = s3_cfg.get("prefix", "")
        s3_region = s3_cfg.get("region", "ru-central-1")
        tenant_id = env.get("cloudru/s3/tenant-id")
        if tenant_id and s3_key and ":" not in s3_key:
            s3_key = f"{tenant_id}:{s3_key}"
        s3_host = s3_endpoint.replace("https://", "").replace("http://", "")
        s3_path = f"{s3_bucket}/{s3_prefix}".strip("/") if s3_prefix else s3_bucket
        repo = f"s3:{s3_host}/{s3_path}"
        restic_env = {
            "RESTIC_REPOSITORY": repo,
            "RESTIC_PASSWORD": restic_pass,
            "AWS_ACCESS_KEY_ID": s3_key,
            "AWS_SECRET_ACCESS_KEY": s3_secret,
            "AWS_DEFAULT_REGION": s3_region,
        }
    elif source == "yadisk":
        ya_token = env.get("yandex/disk/token") or os.environ.get("YA_DISK_TOKEN")
        ya_path = backup_cfg.get("yandex_disk", {}).get("path") or env.get("yandex/disk/path") or "/backups/cloud.ru-free-tier-vm"
        cf = _yadisk_config_file(ya_token)
        repo = f"rclone:yadisk:{ya_path}"
        restic_env = {
            "RESTIC_REPOSITORY": repo,
            "RESTIC_PASSWORD": restic_pass,
            "RCLONE_CONFIG": str(cf),
            "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        }
    else:
        local_path = backup_cfg.get("local_path", "/var/backups/cloud.ru-free-tier-vm")
        repo = f"local:{local_path}"
        restic_env = {"RESTIC_REPOSITORY": repo, "RESTIC_PASSWORD": restic_pass}

    snapshot_id = args.snapshot
    if not snapshot_id:
        result = _run(["restic", "snapshots", "--json"], env=restic_env)
        if result.returncode != 0 or not result.stdout.strip():
            print("❌ Нет snapshot-ов для восстановления")
            sys.exit(1)
        snapshots = json.loads(result.stdout)
        snapshot_id = snapshots[-1]["short_id"]
        print(f"📋 Использую последний snapshot: {snapshot_id}")

    print(f"🔄 Восстановление из {source} (snapshot: {snapshot_id}) -> {target}")
    result = _run(["restic", "restore", snapshot_id, "--target", target], env=restic_env)

    if source == "yadisk":
        Path(restic_env.get("RCLONE_CONFIG", "")).unlink(missing_ok=True)

    if result.returncode == 0:
        print(f"✅ Восстановление завершено")
    else:
        print(f"❌ Ошибка: {result.stderr.strip()[-200:]}")
        sys.exit(1)


def cmd_status(args):
    config = _load_config()
    backup_cfg = config.get("backup", {})
    local_path = backup_cfg.get("local_path", "/var/backups/cloud.ru-free-tier-vm")
    schedule = backup_cfg.get("schedule", "not configured")

    print(f"\n📊 Backup 3-2-1 Status")
    print("=" * 60)
    print(f"📀 Локальный путь: {local_path}")
    print(f"⏰ Расписание: {schedule}")
    print(f"📁 Размер: {_get_size(local_path)}")

    if Path(local_path).exists():
        result = _run(["restic", "-r", f"local:{local_path}", "stats"], timeout=30)
        if result.returncode == 0:
            print(f"📦 Snapshot-ы: {result.stdout.strip()[:100]}")

    print()

    # Check cron/systemd timer
    cron = _run(["sudo", "crontab", "-l"], timeout=10)
    backup_cron = [l for l in cron.stdout.split("\n") if "backup.py" in l]
    if backup_cron:
        print("✅ Cron: настроен")
        for l in backup_cron:
            print(f"   {l.strip()}")
    else:
        systemd = _run(["systemctl", "list-timers", "--all"], timeout=10)
        if "backup" in systemd.stdout:
            print("✅ Systemd timer: настроен")
        else:
            print("⚠️  Backup не настроен в cron/systemd")
            print("   Запустите: python3 scripts/backup.py setup")


def _get_size(path: str) -> str:
    try:
        result = _run(["du", "-sh", path], timeout=10)
        return result.stdout.split()[0] if result.stdout.strip() else "0B"
    except Exception:
        return "unknown"


def cmd_setup(args):
    config = _load_config()
    backup_cfg = config.get("backup", {})
    local_path = backup_cfg.get("local_path", "/var/backups/cloud.ru-free-tier-vm")
    schedule = backup_cfg.get("schedule", "0 2 * * *")

    print("🔧 Настройка backup 3-2-1...")

    Path(local_path).mkdir(parents=True, exist_ok=True)

    # Init local restic repo
    env = _load_env()
    restic_pass = env.get("restic/password") or os.environ.get("RESTIC_PASSWORD")
    if restic_pass:
        restic_env = {"RESTIC_REPOSITORY": f"local:{local_path}", "RESTIC_PASSWORD": restic_pass}
        rc = _run(["restic", "snapshots"], env=restic_env, timeout=30).returncode
        if rc != 0:
            print("⚡ Инициализация restic репозитория...")
            _run(["restic", "init"], env=restic_env)
        print("✅ Локальный restic репозиторий готов")

    # Init Yandex Disk restic repo
    ya_token = env.get("yandex/disk/token") or os.environ.get("YA_DISK_TOKEN")
    ya_path = backup_cfg.get("yandex_disk", {}).get("path") or env.get("yandex/disk/path") or "/backups/cloud.ru-free-tier-vm"
    if ya_token and restic_pass and _check_rclone():
        cf = _yadisk_config_file(ya_token)
        ya_env = {
            "RESTIC_REPOSITORY": f"rclone:yadisk:{ya_path}",
            "RESTIC_PASSWORD": restic_pass,
            "RCLONE_CONFIG": str(cf),
            "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
        }
        rc = _run(["restic", "snapshots"], env=ya_env, timeout=30).returncode
        if rc != 0:
            print("⚡ Инициализация Yandex Disk restic репозитория...")
            _run(["restic", "init"], env=ya_env)
        print("✅ Yandex Disk restic репозиторий готов")
        Path(cf.name).unlink(missing_ok=True)

    # Setup cron
    import tempfile
    cron_line = f"{schedule} cd {os.getcwd()} && python3 scripts/backup.py create >> /var/log/backup.log 2>&1"
    existing = _run(["crontab", "-l"], timeout=10).stdout

    if cron_line not in existing:
        new_cron = existing.strip() + "\n" + cron_line + "\n"
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(new_cron)
            tmp = f.name
        _run(["crontab", tmp], timeout=10)
        Path(tmp).unlink(missing_ok=True)
        print(f"✅ Cron добавлен: {schedule}")
    else:
        print("✅ Cron уже настроен")

    print(f"\n✅ Backup система готова")
    print(f"   📀 Локальный путь: {local_path}")
    print(f"   ☁️  S3: {'настроен' if env.get('cloudru/s3/access-key') else 'не настроен'}")
    print(f"   🌐 Yandex Disk: {'настроен' if ya_token else 'не настроен'}")
    print(f"   ⏰ Расписание: {schedule}")
    print(f"\n   Создайте первый backup:")
    print(f"   python3 scripts/backup.py create")


def main():
    parser = argparse.ArgumentParser(
        description="Backup 3-2-1 Manager — restic + cloud.ru S3 + Yandex Disk",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s create                          # Создать backup (3 копии)
  %(prog)s list                            # Список snapshot-ов
  %(prog)s restore --snapshot abc123       # Восстановить из snapshot
  %(prog)s restore --source s3             # Восстановить из S3
  %(prog)s setup                           # Настроить backup систему
  %(prog)s status                          # Статус backup системы

Backup 3-2-1 стратегия:
   1. Локальный backup (restic в /var/backups)
   2. cloud.ru S3 Object Storage (restic + AES-256)
   3. Yandex Disk (offsite, restic + rclone)

Зависимости: restic, rclone

Переменные окружения:
  restic/password         - Пароль шифрования restic
  cloudru/s3/access-key   - S3 Access Key
  cloudru/s3/secret-key   - S3 Secret Key
  cloudru/s3/bucket       - S3 Bucket name
  cloudru/s3/endpoint     - S3 Endpoint URL
  cloudru/s3/tenant-id    - S3 Tenant ID (префикс для access-key)
  yandex/disk/token       - Yandex Disk OAuth token
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Команды")

    create_parser = subparsers.add_parser("create", help="Создать backup 3-2-1")

    list_parser = subparsers.add_parser("list", help="Список snapshot-ов")

    restore_parser = subparsers.add_parser("restore", help="Восстановить из backup")
    restore_parser.add_argument("--snapshot", help="ID snapshot (по умолч. последний)")
    restore_parser.add_argument("--target", default="/", help="Целевая директория (по умолч. /)")
    restore_parser.add_argument("--source", choices=["local", "s3", "yadisk"], default="local",
                                help="Источник для восстановления")

    setup_parser = subparsers.add_parser("setup", help="Настроить backup систему")

    status_parser = subparsers.add_parser("status", help="Статус backup системы")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "create":
        cmd_create(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "restore":
        cmd_restore(args)
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
