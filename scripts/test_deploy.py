#!/usr/bin/env python3
"""
Deploy Pipeline Test — snapshot, deploy, audit, rollback, diff report.
Usage:
  sudo python3 scripts/test_deploy.py            # Full cycle
  sudo python3 scripts/test_deploy.py --deploy   # Deploy only, no rollback
  sudo python3 scripts/test_deploy.py --verify   # Rollback + verify only
"""

import argparse
import difflib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = PROJECT_DIR / ".test_snapshot"
SNAPSHOT_FILE = SNAPSHOT_DIR / "snapshot.json"
CIS_DATA_DIR = PROJECT_DIR / "cis_data"
MAX_FIX_ITERATIONS = 5

DEPLOY_PACKAGES = [
    "git", "python3-pip", "restic", "rclone", "curl",
    "aide", "fail2ban", "chrony", "needrestart",
    "unattended-upgrades", "build-essential",
]

TRACKED_CONFIGS = [
    "/etc/ssh/sshd_config",
    "/etc/fail2ban/jail.local",
    "/etc/issue",
    "/etc/issue.net",
    "/etc/chrony/chrony.conf",
    "/etc/security/pwquality.conf",
    "/etc/login.defs",
    "/etc/apt/apt.conf.d/50unattended-upgrades",
    "/etc/aide/aide.conf",
]

TRACKED_SYSCTL = [
    "net.ipv4.ip_forward",
    "net.ipv4.conf.all.send_redirects",
    "net.ipv4.conf.default.send_redirects",
    "net.ipv4.conf.all.accept_source_route",
    "net.ipv4.conf.default.accept_source_route",
    "net.ipv4.conf.all.accept_redirects",
    "net.ipv4.conf.default.accept_redirects",
    "net.ipv4.conf.all.secure_redirects",
    "net.ipv4.conf.default.secure_redirects",
    "net.ipv4.conf.all.rp_filter",
    "net.ipv4.conf.default.rp_filter",
    "net.ipv4.conf.all.log_martians",
    "net.ipv4.conf.default.log_martians",
    "kernel.randomize_va_space",
    "fs.suid_dumpable",
]

TRACKED_SERVICES = [
    "fail2ban", "chrony", "unattended-upgrades", "ssh",
    "dailyaidecheck.timer", "exim4",
]

TRACKED_PERMISSIONS = [
    "/etc/passwd", "/etc/shadow", "/etc/group", "/etc/gshadow",
    "/etc/ssh/sshd_config",
    "/etc/passwd-", "/etc/shadow-", "/etc/group-", "/etc/gshadow-",
]


def _run(cmd: str, timeout: int = 30) -> subprocess.CompletedProcess:
    use_shell = "|" in cmd or ">" in cmd or "<" in cmd or "&&" in cmd
    try:
        if use_shell:
            return subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout, shell=True)
        args = shlex.split(cmd)
        return subprocess.run(args, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args if not use_shell else cmd,
                                           returncode=-1, stdout="", stderr="Timeout")


def _run_cmd(cmd: str, timeout: int = 30) -> tuple:
    r = _run(cmd, timeout)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _ok(msg): print(f"  ✅ {msg}")
def _skip(msg): print(f"  ⏭️  {msg}")
def _fail(msg): print(f"  ❌ {msg}")


class Snapshot:
    def __init__(self):
        self.timestamp = ""
        self.packages = {}
        self.configs = {}
        self.sysctl = {}
        self.services = {}
        self.cron = ""
        self.permissions = {}

    def capture(self) -> "Snapshot":
        print("\n📸 Capturing system snapshot...")
        self.timestamp = datetime.now().isoformat()
        print("  Packages...")
        for pkg in DEPLOY_PACKAGES:
            rc, out, _ = _run_cmd(f"dpkg -l {pkg} 2>/dev/null | awk '/^ii/{{print $3}}'")
            if rc == 0 and out:
                self.packages[pkg] = out.split('\n')[-1]
        print("  Configs...")
        for path in TRACKED_CONFIGS:
            p = Path(path)
            if p.exists():
                self.configs[path] = p.read_text(encoding="utf-8", errors="replace")
        print("  Sysctl...")
        for param in TRACKED_SYSCTL:
            rc, out, _ = _run_cmd(f"sysctl -n {param} 2>/dev/null")
            if rc == 0 and out:
                self.sysctl[param] = out.strip()
        print("  Services...")
        for svc in TRACKED_SERVICES:
            _, enabled, _ = _run_cmd(f"systemctl is-enabled {svc} 2>/dev/null")
            _, active, _ = _run_cmd(f"systemctl is-active {svc} 2>/dev/null")
            if enabled or active:
                self.services[svc] = {"enabled": enabled or "unknown",
                                      "active": active or "unknown"}
        print("  Cron...")
        rc, out, _ = _run_cmd("crontab -l 2>/dev/null || sudo crontab -l 2>/dev/null || true")
        self.cron = out
        print("  Permissions...")
        for path in TRACKED_PERMISSIONS:
            p = Path(path)
            if p.exists():
                stat = p.stat()
                self.permissions[path] = f"{oct(stat.st_mode & 0o777)}:{stat.st_uid}:{stat.st_gid}"
        self._save()
        _ok(f"Snapshot saved ({len(self.packages)} pkgs, {len(self.configs)} configs, "
            f"{len(self.services)} services)")
        return self

    def _save(self):
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(json.dumps({
            "timestamp": self.timestamp,
            "packages": self.packages,
            "configs": {k: v for k, v in self.configs.items()},
            "sysctl": self.sysctl,
            "services": self.services,
            "cron": self.cron,
            "permissions": self.permissions,
        }, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls) -> Optional["Snapshot"]:
        if not SNAPSHOT_FILE.exists():
            return None
        try:
            data = json.loads(SNAPSHOT_FILE.read_text())
            snap = cls()
            snap.timestamp = data.get("timestamp", "")
            snap.packages = data.get("packages", {})
            snap.configs = data.get("configs", {})
            snap.sysctl = data.get("sysctl", {})
            snap.services = data.get("services", {})
            snap.cron = data.get("cron", "")
            snap.permissions = data.get("permissions", {})
            return snap
        except (json.JSONDecodeError, KeyError):
            return None

    def restore(self):
        print("\n⏪ Restoring system from snapshot...")
        print("  1. Configs...")
        for path, content in self.configs.items():
            try:
                Path(path).write_text(content)
                _ok(f"{path} restored")
            except Exception as e:
                _fail(f"{path}: {e}")
        print("  2. Sysctl...")
        for param, value in self.sysctl.items():
            _run_cmd(f"sysctl -w {param}={value} 2>/dev/null")
        print("  3. Packages...")
        for pkg in DEPLOY_PACKAGES:
            rc, _, _ = _run_cmd(f"dpkg -l {pkg} 2>/dev/null | grep ^ii")
            was_installed = pkg in self.packages
            is_installed = rc == 0
            if is_installed and not was_installed:
                _run_cmd(f"apt-get purge -y -qq {pkg} 2>/dev/null", timeout=60)
                _ok(f"{pkg} removed")
        print("  4. Services...")
        for svc, state in self.services.items():
            if state["enabled"] == "enabled":
                _run_cmd(f"systemctl enable --now {svc} 2>/dev/null")
            elif state["enabled"] == "disabled":
                _run_cmd(f"systemctl disable {svc} 2>/dev/null")
                _run_cmd(f"systemctl stop {svc} 2>/dev/null")
        print("  5. Cron...")
        if self.cron:
            tf = tempfile.NamedTemporaryFile(mode="w", delete=False)
            tf.write(self.cron + "\n")
            tf.close()
            _run_cmd(f"crontab {tf.name} 2>/dev/null")
            Path(tf.name).unlink(missing_ok=True)
        print("  6. Permissions...")
        for path, perm_str in self.permissions.items():
            p = Path(path)
            if p.exists():
                try:
                    parts = perm_str.split(":")
                    if len(parts) == 3:
                        _run_cmd(f"chmod {parts[0]} {path}")
                        _run_cmd(f"chown {parts[1]}:{parts[2]} {path}")
                except Exception:
                    pass
        _run_cmd("systemctl restart ssh 2>/dev/null", timeout=10)
        _run_cmd("systemctl restart fail2ban 2>/dev/null || true", timeout=10)
        _ok("System restored from snapshot")

    def diff_text(self, current: "Snapshot") -> str:
        lines = [f"=== Snapshot Diff ===", f"Snapshot:  {self.timestamp}",
                 f"Current:   {current.timestamp}", ""]
        added = [p for p in current.packages if p not in self.packages]
        removed = [p for p in self.packages if p not in current.packages]
        modified = [(p, self.packages[p], current.packages[p])
                     for p in self.packages if p in current.packages
                     and self.packages[p] != current.packages[p]]
        if added:
            lines.append(f"+ Added packages: {', '.join(sorted(added))}")
        if removed:
            lines.append(f"- Removed packages: {', '.join(sorted(removed))}")
        for p, ov, nv in modified:
            lines.append(f"~ {p}: {ov} → {nv}")
        for path in sorted(set(self.configs) | set(current.configs)):
            oc = self.configs.get(path, "")
            nc = current.configs.get(path, "")
            if oc != nc:
                lines.append(f"\n--- {path}")
                lines.extend(difflib.unified_diff(oc.splitlines(), nc.splitlines(),
                              fromfile=f"a{path}", tofile=f"b{path}", lineterm=""))
        for param in sorted(set(self.sysctl) | set(current.sysctl)):
            ov = self.sysctl.get(param, "N/A")
            nv = current.sysctl.get(param, "N/A")
            if ov != nv:
                lines.append(f"\nsysctl {param}: {ov} → {nv}")
        for svc in sorted(set(self.services) | set(current.services)):
            os_ = self.services.get(svc, {})
            ns_ = current.services.get(svc, {})
            if os_ != ns_:
                lines.append(f"\nservice {svc}: enable {os_.get('enabled','N/A')}→{ns_.get('enabled','N/A')}, "
                           f"active {os_.get('active','N/A')}→{ns_.get('active','N/A')}")
        for path in sorted(set(self.permissions) | set(current.permissions)):
            op = self.permissions.get(path, "")
            np_ = current.permissions.get(path, "")
            if op != np_:
                lines.append(f"\nperm {path}: {op} → {np_}")
        return "\n".join(lines)


def run_audit() -> dict:
    print("\n🔍 Running CIS audit...")
    _run_cmd(f"cd {PROJECT_DIR} && python3 cis_manager.py audit --format json", timeout=60)
    report = CIS_DATA_DIR / "current_audit.json"
    if not report.exists():
        return {"passed": 0, "failed": 0, "errors": 0, "compliance_score": 0,
                "total": 0, "timestamp": ""}
    try:
        d = json.loads(report.read_text())
        return {"passed": d.get("passed", 0), "failed": d.get("failed", 0),
                "errors": d.get("errors", 0),
                "compliance_score": d.get("compliance_score", 0),
                "total": d.get("total_checks", d.get("passed", 0) + d.get("failed", 0)),
                "timestamp": d.get("timestamp", datetime.now().isoformat())}
    except (json.JSONDecodeError, FileNotFoundError):
        return {"passed": 0, "failed": 0, "errors": 0, "compliance_score": 0,
                "total": 0, "timestamp": ""}


def run_deploy():
    print("\n🚀 Running deploy...")
    token = os.environ.get("BW_ACCESS_TOKEN", "")
    if not token:
        print("  ⚠️  BW_ACCESS_TOKEN not set, secrets will be skipped")
    env = os.environ.copy()
    if token:
        env["BW_ACCESS_TOKEN"] = token
    try:
        r = subprocess.run(["bash", str(PROJECT_DIR / "deploy.sh")],
                           capture_output=True, text=True, timeout=600, env=env)
        if r.returncode != 0:
            print(f"  ⚠️  deploy.sh exit {r.returncode}")
            if r.stderr:
                print(f"  stderr: {r.stderr.strip()[-500:]}")
        return r
    except subprocess.TimeoutExpired:
        print("  ⏰ deploy.sh timed out (10 min)")
        return None


def run_cis_fix():
    print("\n🔧 Running CIS fix...")
    _run_cmd(f"cd {PROJECT_DIR} && python3 cis_manager.py fix --force", timeout=120)


def run_fix_loop(max_iterations: int = MAX_FIX_ITERATIONS) -> list:
    """Run audit → fix → audit loop until 100% compliance. Returns iteration history."""
    fix_iters = []
    attempts = 0
    while attempts < max_iterations:
        attempts += 1
        audit_before = run_audit()
        score = audit_before.get("compliance_score", 0)
        entry = {"attempt": attempts, "audit_before_fix": audit_before}
        print_audit(f"Iteration {attempts} (before fix):", audit_before)
        if score >= 100:
            entry["status"] = "already_100"
            fix_iters.append(entry)
            break
        run_cis_fix()
        audit_after = run_audit()
        entry["audit_after_fix"] = audit_after
        entry["status"] = "fixed" if audit_after.get("compliance_score", 0) >= 100 else "partial"
        print_audit(f"Iteration {attempts} (after fix):", audit_after)
        fix_iters.append(entry)
        if audit_after.get("compliance_score", 0) >= 100:
            break
    return fix_iters


def print_audit(label: str, d: dict):
    print(f"\n  {label}")
    print(f"    PASS: {d.get('passed',0):<5}  FAIL: {d.get('failed',0):<5}  "
          f"ERR: {d.get('errors',0):<5}  Total: {d.get('total',0):<5}  "
          f"Compliance: {d.get('compliance_score',0):.1f}%")


def final_report(snap_before, audit_before, audit_deploy, snap_after, audit_rb=None, fix_iters=None):
    print("\n" + "=" * 65)
    print("  DEPLOY PIPELINE TEST REPORT")
    print("=" * 65)
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _, host, _ = _run_cmd("hostname -f")
    print(f"  Server: {host or 'unknown'}\n")
    print("  ── CIS Compliance ──")
    print_audit("Before deploy:", audit_before)
    print_audit("After deploy:", audit_deploy)
    if audit_rb:
        print_audit("After rollback:", audit_rb)
    print(f"\n  Δ Passed: {audit_deploy['passed'] - audit_before['passed']:+d}")
    print(f"  Δ Compliance: {audit_deploy['compliance_score'] - audit_before['compliance_score']:+.1f}%")
    if fix_iters:
        print(f"\n  ── CIS Fix Loop ({len(fix_iters)} iteration(s)) ──")
        for it in fix_iters:
            before = it.get("audit_before_fix", {}).get("compliance_score", 0)
            after = it.get("audit_after_fix", {}).get("compliance_score", 0) if "audit_after_fix" in it else before
            status = it.get("status", "")
            print(f"    #{it['attempt']}: {before:.1f}% → {after:.1f}%  ({status})")
    print("\n  ── Changes Applied ──")
    diff = snap_before.diff_text(snap_after)
    for line in diff.split("\n"):
        if any(line.startswith(x) for x in ("+ Added", "- Removed", "--- ", "sysctl ", "service ", "perm ")):
            print(f"    {line}")
    if audit_rb:
        print("\n  ── Rollback Verification ──")
        match = (audit_rb["passed"] == audit_before["passed"] and
                 audit_rb["failed"] == audit_before["failed"])
        _ok("Audit matches original state") if match else _fail("Audit mismatch")
    print("\n" + "=" * 65 + "\n")
    report_path = PROJECT_DIR / "test_report.json"
    report_path.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "audit_before": audit_before, "audit_after_deploy": audit_deploy,
        "audit_after_rollback": audit_rb,
        "fix_iterations": len(fix_iters) if fix_iters else 0,
        "fix_iteration_details": fix_iters or [],
        "changes": diff,
    }, indent=2, ensure_ascii=False))
    print(f"  Report: {report_path}")


def cmd_full(args):
    sb = Snapshot().capture()
    ab = run_audit()
    print_audit("Before deploy", ab)
    run_deploy()
    fix_iters = run_fix_loop()
    ad = run_audit()
    print_audit("After deploy + fix", ad)
    sa = Snapshot().capture()
    sb.restore()
    ar = run_audit()
    print_audit("After rollback", ar)
    final_report(sb, ab, ad, sa, ar, fix_iters)
    print("\n🚀 Re-deploying to restore working state...")
    run_deploy()
    af = run_audit()
    print_audit("Final deploy", af)
    if af.get("compliance_score", 0) >= 95:
        _ok("Server ready")
    else:
        _fail(f"Compliance {af.get('compliance_score',0):.1f}% < 95%")


def cmd_deploy(args):
    sb = Snapshot().capture() if not args.no_snapshot else Snapshot.load()
    if not sb:
        print("❌ No snapshot found. Run without --deploy first")
        sys.exit(1)
    ab = run_audit()
    print_audit("Before deploy", ab)
    run_deploy()
    fix_iters = run_fix_loop()
    ad = run_audit()
    print_audit("After deploy + fix", ad)
    final_report(sb, ab, ad, Snapshot().capture(), fix_iters=fix_iters)


def cmd_verify(args):
    sb = Snapshot.load()
    if not sb:
        print(f"❌ No snapshot at {SNAPSHOT_FILE}")
        sys.exit(1)
    ab = run_audit()
    print_audit("Before rollback", ab)
    sb.restore()
    ar = run_audit()
    print_audit("After rollback", ar)
    if ar["passed"] == ab["passed"] and ar["failed"] == ab["failed"]:
        _ok("Rollback verified")
    else:
        _fail(f"Mismatch: before {ab['passed']}/{ab['failed']}, after {ar['passed']}/{ar['failed']}")


def main():
    p = argparse.ArgumentParser(description="Deploy Pipeline Test")
    p.add_argument("--deploy", action="store_true", help="Deploy only")
    p.add_argument("--verify", action="store_true", help="Rollback only")
    p.add_argument("--no-snapshot", action="store_true", help="Reuse snapshot")
    args = p.parse_args()
    if os.geteuid() != 0:
        print("❌ Must run as root (sudo)")
        sys.exit(1)
    if args.verify:
        cmd_verify(args)
    elif args.deploy:
        cmd_deploy(args)
    else:
        cmd_full(args)


if __name__ == "__main__":
    main()
