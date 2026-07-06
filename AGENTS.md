# 🤖 AI Employee - DevOps Agent Documentation

## 📋 Overview

**AI Employee** is an automated DevOps agent that provisions fresh VPS servers to production readiness:

1. **Connect** — SSH to the server, audit current state
2. **Harden** — Apply CIS Debian 12 Level 1 standards
3. **Backup** — Configure 3-2-1 backup (local + cloud.ru S3 + Yandex Disk)
4. **Secure** — Load secrets from Bitwarden Secrets Manager
5. **Document** — Generate README with audit results and hardware specs
6. **Verify** — Ensure compliance score meets threshold

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   CI/CD (GitHub Actions / GitVerse)           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  Setup   │  │  Verify  │  │  Backup  │  │    Docs      │ │
│  │  +Harden │  │Compliance│  │  3-2-1   │  │  Generation  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
│       │             │             │                │          │
│       └─────────────┴─────────────┴────────────────┘          │
│                              │                                 │
│                              ▼                                 │
│              ┌───────────────────────────────┐                │
│              │      AI Employee (Agent)       │                │
│              └──────┬──────────┬──────────┬──┘                │
└─────────────────────┼──────────┼──────────┼───────────────────┘
                      │          │          │
         ┌────────────┼─────┐ ┌──┴──┐ ┌────┴────┐
         │            │     │ │     │ │         │
         ▼            ▼     ▼ ▼     ▼ ▼         ▼
   ┌─────────┐ ┌────────┐ ┌────┐ ┌─────┐ ┌──────────┐
   │   CIS   │ │Bitwarden│ │3-2-1│ │GitVerse│ │ GitHub   │
   │ Manager │ │Secrets  │ │Back │ │CI/CD  │ │ Actions  │
   └─────────┘ └────────┘ └────┘ └─────┘ └──────────┘
```

---

## 🛠️ Agent Capabilities

### 1. Security Auditing

**Command**: `python3 cis_manager.py audit`

- CIS Debian 12 Level 1 compliance checking
- Category-based filtering (Network, SSH, Auth, etc.)
- JSON output for CI/CD integration
- 28 checks across 8 categories

### 2. Security Remediation

**Command**: `python3 cis_manager.py fix --force`

- Automatic remediation of failed checks
- Backup creation before changes
- Dry-run mode (`--dry-run`)
- Non-interactive (`--force` / `--yes` for CI/CD)

### 3. Secrets Management

**Command**: `python3 scripts/secrets.py sync`

- **Bitwarden Secrets Manager** integration
- Machine-to-machine authentication
- Commands: `sync`, `get`, `set`, `list`
- Secrets written to `.env` for other tools

**Required Secrets**:
| Key | Description |
|-----|-------------|
| `cloudru/s3/access_key` | S3 Access Key |
| `cloudru/s3/secret_key` | S3 Secret Key |
| `cloudru/s3/bucket` | S3 bucket name |
| `cloudru/s3/endpoint` | S3 endpoint URL |
| `yandex/disk/token` | Yandex Disk OAuth token |
| `restic/password` | Restic encryption password |
| `github/token` | GitHub Personal Access Token |

### 4. Backup 3-2-1

**Command**: `python3 scripts/backup.py create`

| Copy | Location | Technology |
|------|----------|------------|
| 1 | Local disk (`/var/backups`) | restic |
| 2 | cloud.ru S3 Object Storage | restic + AES-256 |
| 3 | Yandex Disk (offsite) | restic archive |

**Commands**:
- `backup.py create` — Create 3-2-1 backup
- `backup.py list` — List snapshots
- `backup.py restore --snapshot <id>` — Restore
- `backup.py setup` — Configure cron + init repos
- `backup.py status` — Backup system status

### 5. Documentation Generation

**Command**: `python3 scripts/docs_generator.py`

- Uses `config/templates/server.md` template
- Real CIS audit data (pass/fail per check)
- Hardware specifications
- Compliance history

### 6. Compliance Verification

**Command**: `python3 scripts/check_compliance.py --threshold 95`

- Validates compliance score
- Fails pipeline if below threshold
- Exit codes for CI/CD integration

---

## 📜 Agent Configuration

### Environment Variables

```bash
# Bitwarden Secrets Manager
BW_ACCESS_TOKEN="${BW_ACCESS_TOKEN}"
BW_ORG_ID="${BW_ORG_ID}"
BW_API_URL="https://vault.bitwarden.com"

# Backup
RESTIC_PASSWORD="${RESTIC_PASSWORD}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}"
YA_DISK_TOKEN="${YA_DISK_TOKEN}"

# Agent Configuration
CIS_TARGET="95"
LOG_LEVEL="INFO"
```

### Configuration Files

```
config/
├── cis_standard.yaml       # CIS check definitions
├── backup.yaml             # 3-2-1 backup configuration
└── templates/
    └── server.md           # README template
```

---

## 🤖 AI Agent Workflow

### Full Provisioning (fresh VPS → production ready)

```bash
# 1. Sync secrets from Bitwarden Secrets Manager
python3 scripts/secrets.py sync

# 2. Run initial audit
python3 cis_manager.py audit

# 3. Apply all CIS fixes
python3 cis_manager.py fix --force

# 4. Re-audit to verify
python3 cis_manager.py audit --format json

# 5. Setup backup system (cron + restic repos)
python3 scripts/backup.py setup

# 6. Create initial 3-2-1 backup
python3 scripts/backup.py create

# 7. Generate documentation
python3 scripts/docs_generator.py

# 8. Verify compliance
python3 scripts/check_compliance.py --threshold 95
```

### Quick Commands Reference

```bash
# Audit & Fix
python3 cis_manager.py audit --categories Network SSH
python3 cis_manager.py fix --dry-run
python3 cis_manager.py fix --force
python3 cis_manager.py history
python3 cis_manager.py rollback <backup_id>

# Secrets
python3 scripts/secrets.py list
python3 scripts/secrets.py get restic/password
python3 scripts/secrets.py set cloudru/s3/access_key AKID123

# Backup
python3 scripts/backup.py status
python3 scripts/backup.py create
python3 scripts/backup.py list
python3 scripts/backup.py restore --snapshot abc123
python3 scripts/backup.py restore --source s3

# Docs & Verify
python3 scripts/docs_generator.py
python3 scripts/check_compliance.py --threshold 95
```

---

## 🔄 Pipeline Stages

### Stage 1: Setup & Harden
- Install dependencies (Python, restic)
- Sync secrets from Bitwarden
- Run CIS audit
- Apply security fixes

### Stage 2: Verify Compliance
- Validate compliance score ≥ 95%
- Generate audit report
- Fail pipeline if below threshold

### Stage 3: Backup 3-2-1
- Create restic backup (local + S3)
- Upload archive to Yandex Disk
- Prune old snapshots per retention policy

### Stage 4: Documentation
- Generate README from template
- Include audit results and hardware specs
- Commit and push

---

## 🔑 Secrets Management

### Bitwarden Secrets Manager Setup

1. Create access token in [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/)
2. Set environment variables:
   ```bash
   export BW_ACCESS_TOKEN="<your-machine-token>"
   export BW_ORG_ID="<your-org-id>"
   ```
3. Sync secrets:
   ```bash
   python3 scripts/secrets.py sync
   ```

### Required Secrets Structure

```
cloudru/
  s3/
    access_key     # S3 Access Key
    secret_key     # S3 Secret Key
    bucket         # S3 Bucket name
    endpoint       # S3 Endpoint URL
yandex/
  disk/
    token          # Yandex Disk OAuth token
restic/
  password         # Restic encryption password
```

---

## 🐛 Troubleshooting

### Common Issues

| Error | Solution |
|-------|----------|
| `BW_ACCESS_TOKEN не задан` | Set `BW_ACCESS_TOKEN` env var |
| `restic не установлен` | `apt install restic` or `brew install restic` |
| `RESTIC_PASSWORD не задан` | Create secret `restic/password` in Bitwarden |
| `Compliance < 95%` | Run `cis_manager.py fix --force` |
| `Permission denied` | Run with `sudo` or as root |
| `S3 credentials не заданы` | Set `cloudru/s3/*` secrets in Bitwarden |

---

## 📊 Key Performance Indicators

| Metric | Description | Target |
|--------|-------------|--------|
| Compliance Score | CIS compliance percentage | ≥95% |
| Backup Duration | Time to complete 3-2-1 backup | <30 min |
| Secrets Sync | Secrets loaded from Bitwarden | 100% |
| Documentation | README generated on each run | Always current |

---

## 🚀 Deployment

### Initial Setup on Fresh VPS

```bash
# Clone repository
git clone <repo-url> cloud.ru-free-tier-vm
cd cloud.ru-free-tier-vm

# Set environment
export BW_ACCESS_TOKEN="<token>"
export BW_ORG_ID="<org-id>"

# Run full provisioning
bash deploy.sh
```

### Manual Execution

```bash
# Full provisioning (AI agent mode)
python3 scripts/secrets.py sync && \
python3 cis_manager.py audit && \
python3 cis_manager.py fix --force && \
python3 scripts/backup.py setup && \
python3 scripts/backup.py create && \
python3 scripts/docs_generator.py && \
python3 scripts/check_compliance.py --threshold 95
```

---

## 📚 Additional Resources

- [CIS Debian 12 Benchmark](https://www.cisecurity.org/cis-benchmarks/)
- [Bitwarden Secrets Manager API](https://bitwarden.com/help/secrets-manager/)
- [Restic Documentation](https://restic.readthedocs.io/)
- [cloud.ru S3 Object Storage](https://cloud.ru/docs/storage/)
- [Yandex Disk REST API](https://yandex.ru/dev/disk/)

---

*AI Employee v2.0.0 — GitHub/GitVerse DevOps Agent*
