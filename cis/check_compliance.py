#!/usr/bin/env python3
"""Скрипт проверки compliance score"""

import json
import argparse
import sys
from pathlib import Path

def check_compliance(threshold: int = 95, audit_file: str = None) -> bool:
    """Проверка compliance score"""
    
    audit_path = Path(audit_file) if audit_file else Path("cis/data/current_audit.json")
    
    if not audit_path.exists():
        print(f"❌ {audit_path} not found. Run `python3 cis/manager.py audit` first.")
        return False
    
    with open(audit_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    score = data.get('compliance_score', 0)
    passed = data.get('passed', 0)
    failed = data.get('failed', 0)
    
    print(f"📊 Compliance Score: {score}%")
    print(f"   Passed: {passed}")
    print(f"   Failed: {failed}")
    print(f"   Threshold: {threshold}%")
    
    if score >= threshold:
        print(f"✅ Compliance check passed ({score}% >= {threshold}%)")
        return True
    else:
        print(f"❌ Compliance check failed ({score}% < {threshold}%)")
        print(f"\n💡 To fix failed checks:")
        print(f"   Run: python3 cis/manager.py fix --force")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Check CIS compliance score"
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=95,
        help="Minimum required compliance score (default: 95)"
    )
    parser.add_argument(
        '--audit-file',
        help="Path to audit JSON file (default: cis/data/current_audit.json)"
    )
    
    args = parser.parse_args()
    
    success = check_compliance(args.threshold, args.audit_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
