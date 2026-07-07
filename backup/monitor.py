#!/usr/bin/env python3
"""Health monitor — disk, memory, load average."""

import os
import shutil

def _ok(msg): print(f"  ✅ {msg}")
def _warn(msg): print(f"  ⚠️ {msg}")

def check_disk(threshold=85):
    total, used, free = shutil.disk_usage("/")
    pct = used / total * 100
    msg = f"disk: {pct:.0f}% used ({used//2**30}G / {total//2**30}G)"
    if pct >= threshold:
        _warn(msg)
    else:
        _ok(msg)

def check_memory(threshold=90):
    mem = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":")
        mem[k.strip()] = int(v.strip().split()[0]) * 1024
    total = mem.get("MemTotal", 1)
    available = mem.get("MemAvailable", 0)
    pct = (1 - available / total) * 100 if total else 0
    msg = f"memory: {pct:.0f}% used ({(total-available)//2**20}M / {total//2**20}M)"
    if pct >= threshold:
        _warn(msg)
    else:
        _ok(msg)

def check_load(threshold=None):
    load = os.getloadavg()[0]
    cores = os.cpu_count() or 1
    limit = threshold or cores
    msg = f"load: {load:.2f} (cores: {cores})"
    if load >= limit:
        _warn(msg)
    else:
        _ok(msg)

def main():
    print(f"📊 Health Check — {__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 50)
    check_disk()
    check_memory()
    check_load()

if __name__ == "__main__":
    main()
