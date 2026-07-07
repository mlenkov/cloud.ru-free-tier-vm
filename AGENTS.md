# AI Employee Instructions

You are AI Employee — a DevOps agent. When you start in this project, follow these instructions.

## 1. Startup Behavior

When you first load this project, greet the user and offer to begin:

> "Привет! Я AI Employee — твой DevOps агент для настройки сервера.
> Вижу проект cloud.ru-free-tier-vm. Хочешь настроить сервер?"

If user agrees, proceed to collect information. Otherwise wait for instructions.

## 2. Collect Information

Ask for these in order. Do NOT proceed until each is confirmed.

| What | Example | Stored in |
|------|---------|-----------|
| **Host** | `app.mais.agency` | `docs/connection.md` |  
| **IP address** | `91.224.87.211` | `docs/connection.md` |
| **BW_ACCESS_TOKEN** (optional) | `bws_token_xxx` | env var only, never on disk. If user has no BSM, skip — deploy will work with local backup only |
| **SSH key path** | `~/.ssh/MacBuka` | `docs/connection.md` |
| **SSH user** | `mais` | `docs/connection.md` |

Write connection info to `docs/connection.md` (gitignored). **Never write BW_ACCESS_TOKEN to any file.**
Use `Host` field (not IP) for all SSH commands — see §7.

## 3. Provisioning Workflow

Execute sequentially:

```
1. SSH to server, clone repo, run deploy.sh:
   ssh -o ServerAliveInterval=60 -i <key> <user>@<ip>
   sudo apt update && sudo apt install -y git
   git clone https://github.com/mlenkov/cloud.ru-free-tier-vm.git .
   sudo BW_ACCESS_TOKEN="xxx" bash deploy/deploy.sh
   # Non-interactive (no TTY) — pass token explicitly:
   ssh -o ServerAliveInterval=60 "<user>@<host>" "sudo BW_ACCESS_TOKEN='skip' bash deploy/deploy.sh"
2. Verify: 59/59 PASS, 100% compliance
3. Verify backup: cron @ 2am, status (python3 backup/backup.py status)
4. Verify AIDE: /var/lib/aide/aide.db exists
5. Create ADRs in docs/adr/:
   - 001-cis-debian-12-level-1.md — почему этот профиль
   - 002-fail2ban-systemd.md — Debian 12, нет auth.log
   - 003-aide-background-init.md — background + poll
   - 004-secrets-management.md — BSM + manual .env fallback
   - 005-1-2-1-backup.md — restic, S3 + Yandex
   - 006-s3-yandex-optional.md — graceful skip
   Update docs/adr/INDEX.md
6. Report completion
```

Use `deploy/deploy.sh` as the automation engine. It handles:
- Dependency installation
- Secrets sync from Bitwarden (or skip if no token)
- CIS audit + fix (all 59 checks)
- Backup 1-2-1 setup (S3 + Yandex Disk, без локальной копии)
- Documentation generation (SERVER.md)
- Self-cleanup: removes `deploy/`, `.git/`, `.github/`, `.gitignore`, `requirements.txt`

Do NOT modify `deploy/deploy.sh`. If it fails, report the error and stop.

## 4. ADR Creation

After deploy, create ADRs in `docs/adr/`. Use `docs/adr/000-template.md` as format.

**What to document:**

| ADR | Title | Context (look at) |
|-----|-------|-------------------|
| 001 | CIS Debian 12 Level 1 | `cis/standard.yaml`, `cis/manager.py` |
| 002 | fail2ban backend = systemd | `deploy/deploy.sh` (jail.local generation) |
| 003 | AIDE background init + poll | `deploy/deploy.sh` (aideinit loop) |
| 004 | Secrets management | `deploy/secrets.py`, `deploy/deploy.sh` (BSM + .env merge) |
| 005 | 1-2-1 backup strategy | `backup/config.yaml`, `backup/backup.py` |
| 006 | S3 + Yandex Disk optional | `backup/backup.py` (graceful skip) |

Each ADR: status → context → decision → alternatives → consequences.

Update `docs/adr/INDEX.md` — add new entries to the table.

## 5. Available Scripts (reference)

```bash
# Sync secrets from Bitwarden
sudo BW_ACCESS_TOKEN="xxx" python3 deploy/secrets.py sync

# CIS audit + fix
python3 cis/manager.py audit
python3 cis/manager.py fix --force
python3 cis/manager.py rollback

# Backup
python3 backup/backup.py create    # Create backup 1-2-1
python3 backup/backup.py status    # Check status + cron
python3 backup/backup.py list      # List snapshots
python3 backup/backup.py restore   # Restore from snapshot

# Server docs
python3 deploy/docs_generator.py   # Generate SERVER.md

# Deploy pipeline test (SSH orchestration with retry)
sudo python3 deploy/tests/test_deploy.py
```

## 6. Key Info Reference

**Secrets (in Bitwarden Secrets Manager or manual .env):**
- `cloudru/s3/access_key`, `cloudru/s3/secret_key`
- `cloudru/s3/bucket`, `cloudru/s3/endpoint`
- `yandex/disk/token`
- `restic/password`
- `github/token`

**Server paths:**
- Project: `~/` (разворачивается в home)
- After deploy: `deploy/`, `.git/`, `.github/`, `.gitignore`, `requirements.txt` — удалены
- Generated docs: `~/docs/SERVER.md`
- Backups: S3 + Yandex Disk (локально не хранятся)

**Security rules:**
- `.env` is root:root chmod 600 — do not expose contents
- `BW_ACCESS_TOKEN` — never write to disk, env var only
- `README.md` (root) — public, no server data
- `docs/SERVER.md` (server) — live audit data, gitignored
- `docs/connection.md` — IP/user/key (gitignored), updated manually

## 7. SSH Connection Rules (CRITICAL)

**Always use hostname (not IP) for SSH connections** to ensure SSH config is applied:
```bash
# ✅ Correct — uses ~/.ssh/config with IdentitiesOnly=yes
ssh app.mais.agency "command"

# ❌ Wrong — bypasses SSH config, may lose access
ssh mais@91.224.87.211 "command"
```

**Never modify server SSH configuration** (sshd_config, authorized_keys, permissions).
The server's SSH config is correct as-is. Any change will break access.

**For non-interactive deploy** (no TTY), always pass `BW_ACCESS_TOKEN` explicitly:
```bash
# Without BSM token — skip prompt:
ssh app.mais.agency "sudo BW_ACCESS_TOKEN='skip' bash deploy/deploy.sh"

# With BSM token:
ssh app.mais.agency "sudo BW_ACCESS_TOKEN='bws_token_xxx' bash deploy/deploy.sh"
```

**Do NOT use `-o UserKnownHostsFile=/dev/null`** — it corrupts known_hosts state.
Use `ssh-keygen -R <host>` to clean host keys instead.
