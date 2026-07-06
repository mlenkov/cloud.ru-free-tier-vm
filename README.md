# cloud.ru-free-tier-vm

Automated VPS provisioning: CIS Debian 12 Level 1 hardening, 3-2-1 backup, secrets management.

## Quick Start

```bash
# From this repo on your local machine:
BW_ACCESS_TOKEN="xxx" ./deploy.sh <hostname>
```

`deploy.sh` syncs the repo to the server and runs: secrets → CIS audit → fix → backup → docs.

## Project Structure

```
cloud.ru-free-tier-vm/
├── deploy.sh               # One-command installer (entry point)
├── cis_manager.py          # CIS audit and fix tool
├── config/
│   ├── cis_standard.yaml   # CIS Debian 12 Level 1 checks
│   ├── backup.yaml         # 3-2-1 backup config
│   └── templates/
│       └── server.md       # Documentation template
├── scripts/
│   ├── backup.py           # 3-2-1 backup manager (local + S3 + Yandex Disk)
│   ├── secrets.py          # Bitwarden Secrets Manager sync
│   ├── docs_generator.py   # Server documentation generator
│   └── check_compliance.py # CIS compliance validator
├── AGENTS.md               # AI Agent documentation
└── README.md               # This file
```

## Required Secrets (Bitwarden Secrets Manager)

| Key | Description |
|-----|-------------|
| `cloudru/s3/access_key` | S3 Access Key |
| `cloudru/s3/secret_key` | S3 Secret Key |
| `cloudru/s3/bucket` | S3 bucket name |
| `cloudru/s3/endpoint` | S3 endpoint URL |
| `yandex/disk/token` | Yandex Disk OAuth token |
| `restic/password` | Restic encryption password |
| `github/token` | GitHub Personal Access Token |

## Features

- **CIS Debian 12 Level 1** — 59 checks across 16 categories
- **3-2-1 Backup** — local disk + cloud.ru S3 + Yandex Disk via restic
- **Secrets Management** — Bitwarden Secrets Manager (machine-to-machine)
- **Self-documenting** — generates server README with audit results
- **CI/CD ready** — GitHub Actions pipeline included

## Manual Commands (on server)

```bash
python3 cis_manager.py audit          # Run CIS audit
python3 cis_manager.py fix --force    # Apply all fixes
python3 scripts/backup.py create      # Create 3-2-1 backup
python3 scripts/secrets.py sync       # Sync from Bitwarden
```
