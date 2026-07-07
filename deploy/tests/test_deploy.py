#!/usr/bin/env python3
"""
Deploy Pipeline Test — SSH-оркестрация, retry-петля, откат.
Цикл: deploy → audit → если FAIL → restore snapshot → retry → до PASS.

Usage:
  sudo python3 deploy/tests/test_deploy.py
  sudo python3 deploy/tests/test_deploy.py --attempts 5
  sudo python3 deploy/tests/test_deploy.py --skip-cleanup

Connects to server via docs/connection.md, uploads project,
runs deploy.sh, verifies compliance. On fail → rollback → retry.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
CONNECTION_FILE = PROJECT_DIR / "docs" / "connection.md"
SNAPSHOT_DIR = PROJECT_DIR / ".test_snapshot"
SNAPSHOT_FILE = SNAPSHOT_DIR / "snapshot.json"
MAX_ATTEMPTS = 3

TRACKED_SYSCTL = [
    "net.ipv4.ip_forward",
    "net.ipv4.conf.all.send_redirects",
    "net.ipv4.conf.all.accept_source_route",
    "net.ipv4.conf.all.accept_redirects",
    "net.ipv4.conf.all.rp_filter",
    "net.ipv4.conf.all.log_martians",
    "kernel.randomize_va_space",
]

TRACKED_SERVICES = [
    "fail2ban", "chrony", "unattended-upgrades", "ssh",
]

TRACKED_PERMISSIONS = [
    "/etc/passwd", "/etc/shadow", "/etc/group", "/etc/gshadow",
    "/etc/ssh/sshd_config",
]


def _ok(msg): print(f"  [+] {msg}")
def _fail(msg): print(f"  [!] {msg}")
def _info(msg): print(f"  [*] {msg}")


def load_connection() -> dict:
    if not CONNECTION_FILE.exists():
        print(f"Connection file not found: {CONNECTION_FILE}")
        print("Create docs/connection.md with: IP, User, SSH Key")
        sys.exit(1)
    text = CONNECTION_FILE.read_text()
    info = {}
    m = re.search(r'\*\*IP\*\*:\s*(\S+)', text)
    if m: info["ip"] = m.group(1)
    m = re.search(r'\*\*User\*\*:\s*(\S+)', text)
    if m: info["user"] = m.group(1)
    m = re.search(r'\*\*SSH Key\*\*:\s*(\S+)', text)
    if m: info["key"] = m.group(1)
    if not all(k in info for k in ("ip", "user", "key")):
        print("Connection file missing required fields (IP, User, SSH Key)")
        sys.exit(1)
    return info


class SSHClient:
    def __init__(self, conn: dict):
        self.conn = conn
        self.prefix = ["ssh", "-o", "StrictHostKeyChecking=no",
                       "-o", "ServerAliveInterval=30",
                       "-i", conn["key"],
                       f"{conn['user']}@{conn['ip']}"]
        self.remote_dir = self._resolve_home()

    def _resolve_home(self) -> str:
        rc, out, _ = self.run(f"eval echo ~{self.conn['user']}", sudo=False, timeout=10)
        return out.strip() if rc == 0 else f"/home/{self.conn['user']}"

    def run(self, cmd: str, timeout: int = 60, sudo: bool = True) -> tuple:
        wrapped = f"sudo bash -c '{cmd}'" if sudo else cmd
        full_cmd = self.prefix + [wrapped]
        try:
            r = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "timeout"
        except Exception as e:
            return -1, "", str(e)

    def put_file(self, local: Path, remote: str, timeout: int = 30):
        cmd = ["scp", "-o", "StrictHostKeyChecking=no",
               "-i", self.conn["key"],
               str(local),
               f"{self.conn['user']}@{self.conn['ip']}:{remote}"]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
        except Exception as e:
            print(f"  scp failed: {e}")
            sys.exit(1)

    def put_project(self):
        _info("Uploading project to server...")
        tmp_tar = tempfile.mktemp(suffix=".tar.gz")
        try:
            subprocess.run(
                ["tar", "-czf", tmp_tar, "-C", str(PROJECT_DIR),
                 "--exclude=.git", "--exclude=__pycache__", "--exclude=*.pyc",
                 "--exclude=.test_snapshot", "--exclude=deploy/tests", "."],
                capture_output=True, text=True, timeout=30, check=True)
            self.run(f"mkdir -p {self.remote_dir}", timeout=10)
            local_tar = f"{self.remote_dir}.tar.gz"
            self.put_file(Path(tmp_tar), local_tar)
            rc, out, err = self.run(
                f"cd {self.remote_dir} && tar -xzf {local_tar} "
                f"&& rm {local_tar}", timeout=30)
            if rc != 0:
                print(f"  extract failed: {err}")
                sys.exit(1)
            _ok("Project uploaded")
        finally:
            Path(tmp_tar).unlink(missing_ok=True)


class SystemSnapshot:
    def __init__(self):
        self.timestamp = ""
        self.sysctl = {}
        self.services = {}
        self.permissions = {}
        self.audit = {}

    def capture(self, ssh: SSHClient) -> "SystemSnapshot":
        _info("Capturing system state...")
        self.timestamp = datetime.now().isoformat()
        for param in TRACKED_SYSCTL:
            rc, out, _ = ssh.run(f"sysctl -n {param} 2>/dev/null")
            if rc == 0:
                self.sysctl[param] = out.strip()
        for svc in TRACKED_SERVICES:
            _, enabled, _ = ssh.run(f"systemctl is-enabled {svc} 2>/dev/null")
            _, active, _ = ssh.run(f"systemctl is-active {svc} 2>/dev/null")
            if enabled or active:
                self.services[svc] = {"enabled": enabled.strip(), "active": active.strip()}
        for path in TRACKED_PERMISSIONS:
            rc, out, _ = ssh.run(f"stat -c '%a:%u:%g' {path} 2>/dev/null")
            if rc == 0:
                self.permissions[path] = out.strip()
        self.audit = self._run_audit(ssh)
        _ok(f"Snapshot: {len(self.sysctl)} sysctl, {len(self.services)} svc, "
            f"{len(self.permissions)} perms")
        return self

    def restore(self, ssh: SSHClient):
        _info("Restoring system state...")
        for param, value in self.sysctl.items():
            ssh.run(f"sysctl -w {param}={value}", timeout=10)
        for svc, state in self.services.items():
            if state["enabled"] == "enabled":
                ssh.run(f"systemctl enable --now {svc}", timeout=15)
            elif state["enabled"] == "disabled":
                ssh.run(f"systemctl disable --now {svc}", timeout=15)
        for path, perms in self.permissions.items():
            parts = perms.split(":")
            if len(parts) == 3:
                ssh.run(f"chmod {parts[0]} {path} && chown {parts[1]}:{parts[2]} {path}", timeout=10)
        ssh.run("systemctl restart ssh fail2ban 2>/dev/null || true", timeout=15)
        _ok("System restored")

    def _run_audit(self, ssh: SSHClient) -> dict:
        rc, out, err = ssh.run(f"cd {ssh.remote_dir} && python3 cis/manager.py audit --format json 2>/dev/null", timeout=120)
        if rc != 0:
            return {"passed": 0, "failed": 0, "errors": 0, "compliance_score": 0}
        try:
            rc2, out2, _ = ssh.run(f"cat {ssh.remote_dir}/cis/data/current_audit.json 2>/dev/null")
            if rc2 == 0:
                d = json.loads(out2)
                return {"passed": d.get("passed", 0), "failed": d.get("failed", 0),
                        "errors": d.get("errors", 0),
                        "compliance_score": d.get("compliance_score", 0)}
        except (json.JSONDecodeError, ValueError):
            pass
        return {"passed": 0, "failed": 0, "errors": 0, "compliance_score": 0}


def run_deploy(ssh: SSHClient, token: str = "") -> tuple:
    _info("Running deploy...")
    env_var = f"BW_ACCESS_TOKEN='{token}'" if token else ""
    cmd = f"cd {ssh.remote_dir} && {env_var} bash deploy/deploy.sh"
    rc, out, err = ssh.run(cmd, timeout=600)
    if rc != 0:
        print(f"  deploy exit code: {rc}")
        if err:
            print(f"  stderr: {err[-300:]}")
    return rc, out, err


def verify_cleanup(ssh: SSHClient) -> bool:
    _info("Verifying cleanup...")
    ok = True
    for path in ["deploy", ".gitignore", ".github", "requirements.txt"]:
        rc, out, _ = ssh.run(f"test -e {ssh.remote_dir}/{path} 2>/dev/null && echo EXISTS || echo GONE")
        if "EXISTS" in out:
            print(f"  [!] leftover: {path}")
            ok = False
    if ok:
        _ok("Deploy artifacts removed")
    return ok


def verify_compliance(audit: dict, threshold: int = 95) -> bool:
    score = audit.get("compliance_score", 0)
    passed = audit.get("passed", 0)
    failed = audit.get("failed", 0)
    print(f"  PASS: {passed}  FAIL: {failed}  Score: {score:.1f}%  (threshold: {threshold}%)")
    return score >= threshold


def print_summary(title: str, audit: dict):
    print(f"  {title}: PASS {audit.get('passed',0)} / FAIL {audit.get('failed',0)} "
          f"/ ERR {audit.get('errors',0)} = {audit.get('compliance_score',0):.1f}%")


def cmd_test(args):
    conn = load_connection()
    ssh = SSHClient(conn)
    attempts = args.attempts or MAX_ATTEMPTS
    token = os.environ.get("BW_ACCESS_TOKEN", "")

    for attempt in range(1, attempts + 1):
        print(f"\n{'='*60}")
        print(f"  Attempt {attempt}/{attempts}")
        print(f"{'='*60}")

        ssh.put_project()

        snap_before = SystemSnapshot()
        snap_before.capture(ssh)
        print_summary("Before deploy", snap_before.audit)

        run_deploy(ssh, token)

        snap_after = SystemSnapshot()
        snap_after.capture(ssh)
        print_summary("After deploy", snap_after.audit)

        if verify_compliance(snap_after.audit):
            _ok(f"Compliance PASSED on attempt {attempt}")
            verify_cleanup(ssh)
            print(f"\n{'='*60}")
            print(f"  DEPLOY SUCCESS (attempt {attempt}/{attempts})")
            print(f"{'='*60}")
            return

        if attempt < attempts:
            _info(f"Compliance FAILED, restoring snapshot and retrying...")
            snap_before.restore(ssh)
            snap_restored = SystemSnapshot()
            snap_restored.capture(ssh)
            print_summary("After rollback", snap_restored.audit)
        else:
            _fail(f"All {attempts} attempts exhausted")

    _fail("Deploy pipeline FAILED")
    sys.exit(1)


def main():
    p = argparse.ArgumentParser(description="Deploy Pipeline Test with SSH orchestration")
    p.add_argument("--attempts", "-a", type=int, default=MAX_ATTEMPTS,
                   help=f"Max retry attempts (default: {MAX_ATTEMPTS})")
    p.add_argument("--skip-cleanup", action="store_true", help="Skip deploy artifact cleanup")
    args = p.parse_args()

    cmd_test(args)


if __name__ == "__main__":
    main()
