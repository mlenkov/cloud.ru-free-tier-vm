#!/usr/bin/env python3
"""
CIS Debian 12 Level 1 Server Manager for VPS
Professional hardening tool with audit, fix, history, and rollback capabilities
"""

import os
import sys
import subprocess
import json
import re
import shutil
import argparse
import logging
import shlex
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

# Цвета для вывода
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class Status:
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"

@dataclass
class CheckResult:
    cis_id: str
    category: str
    description: str
    status: str
    details: str = ""
    fix_command: str = ""
    backup_path: str = ""
    timestamp: str = ""

@dataclass
class AuditReport:
    timestamp: str
    hostname: str
    kernel: str
    total_checks: int
    passed: int
    failed: int
    errors: int
    compliance_score: float
    duration_seconds: float
    checks: List[Dict]
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "hostname": self.hostname,
            "kernel": self.kernel,
            "total_checks": self.total_checks,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "compliance_score": self.compliance_score,
            "duration_seconds": self.duration_seconds,
            "checks": [asdict(check) if isinstance(check, CheckResult) else check 
                      for check in self.checks]
        }

class CISManager:
    """Менеджер для CIS Debian 12 аудита и исправлений"""
    
    def __init__(self, data_dir: str = "./cis_data", log_level: str = "INFO"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.history_dir = self.data_dir / "history"
        self.history_dir.mkdir(exist_ok=True)
        self.backup_dir = self.data_dir / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.current_report_file = self.data_dir / "current_audit.json"

        # Настройка логирования
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO),
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)

        self._init_checks()
    
    def _init_checks(self):
        """Инициализация реестра проверок из YAML или хардкода"""
        yaml_path = Path("config/cis_standard.yaml")

        self.checks = self._load_checks_from_yaml(yaml_path) or self._default_checks()

    def _default_checks(self) -> Dict:
        """Хардкод-запасной список проверок (если YAML недоступен)"""
        return {
            "1.4.1": {"category": "CoreDumps", "description": "Core dumps отключены",
                       "check": lambda: self._check_core_dumps(),
                       "fix": lambda: self._fix_core_dumps()},
            "1.7.1": {"category": "Banners", "description": "/etc/issue содержит предупреждение",
                       "check": lambda: self._check_banner("/etc/issue"),
                       "fix": lambda: self._fix_banner("/etc/issue")},
            "1.7.2": {"category": "Banners", "description": "/etc/issue.net содержит предупреждение",
                       "check": lambda: self._check_banner("/etc/issue.net"),
                       "fix": lambda: self._fix_banner("/etc/issue.net")},
            "3.1": {"category": "Network", "description": "IP forwarding отключен",
                     "check": lambda: self._check_sysctl("net.ipv4.ip_forward", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.ip_forward", "0")},
            "3.2": {"category": "Network", "description": "Packet redirect sending отключен",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.send_redirects", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.send_redirects", "0")},
            "3.3": {"category": "Network", "description": "Source routed packets отключены",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.accept_source_route", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.accept_source_route", "0")},
            "3.4": {"category": "Network", "description": "ICMP redirects отключены",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.accept_redirects", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.accept_redirects", "0")},
            "3.5": {"category": "Network", "description": "Reverse path filtering включен",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.rp_filter", "1"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.rp_filter", "1")},
            "3.6": {"category": "Network", "description": "Suspicious packets logging включен",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.log_martians", "1"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.log_martians", "1")},
            "5.2": {"category": "SSH", "description": "SSH: вход root отключен",
                     "check": lambda: self._check_ssh_param("permitrootlogin", "no"),
                     "fix": lambda: self._fix_ssh_param("PermitRootLogin", "no")},
            "5.3": {"category": "SSH", "description": "SSH: MaxAuthTries <= 4",
                     "check": lambda: self._check_ssh_param_max("maxauthtries", 4),
                     "fix": lambda: self._fix_ssh_param("MaxAuthTries", "3")},
            "5.4": {"category": "SSH", "description": "SSH: IgnoreRhosts включен",
                     "check": lambda: self._check_ssh_param("ignorerhosts", "yes"),
                     "fix": lambda: self._fix_ssh_param("IgnoreRhosts", "yes")},
            "5.5": {"category": "SSH", "description": "SSH: HostBasedAuthentication отключен",
                     "check": lambda: self._check_ssh_param("hostbasedauthentication", "no"),
                     "fix": lambda: self._fix_ssh_param("HostBasedAuthentication", "no")},
            "5.6": {"category": "SSH", "description": "SSH: PermitEmptyPasswords отключен",
                     "check": lambda: self._check_ssh_param("permitemptypasswords", "no"),
                     "fix": lambda: self._fix_ssh_param("PermitEmptyPasswords", "no")},
            "5.7": {"category": "SSH", "description": "SSH: X11Forwarding отключен",
                     "check": lambda: self._check_ssh_param("x11forwarding", "no"),
                     "fix": lambda: self._fix_ssh_param("X11Forwarding", "no")},
            "6.1": {"category": "Auth", "description": "PASS_MAX_DAYS <= 365",
                     "check": lambda: self._check_login_def("PASS_MAX_DAYS", max_val=365, min_val=1),
                     "fix": lambda: self._fix_login_def("PASS_MAX_DAYS", "365")},
            "6.2": {"category": "Auth", "description": "PASS_MIN_DAYS >= 1",
                     "check": lambda: self._check_login_def("PASS_MIN_DAYS", min_val=1),
                     "fix": lambda: self._fix_login_def("PASS_MIN_DAYS", "1")},
            "6.3": {"category": "Auth", "description": "UMASK >= 027",
                     "check": lambda: self._check_umask("027"),
                     "fix": lambda: self._fix_login_def("UMASK", "027")},
            "7.1": {"category": "Files", "description": "/etc/passwd права = 644",
                     "check": lambda: self._check_file_perms("/etc/passwd", "644"),
                     "fix": lambda: self._fix_file_perms("/etc/passwd", "644")},
            "7.2": {"category": "Files", "description": "/etc/shadow права <= 640",
                     "check": lambda: self._check_file_perms_max("/etc/shadow", "640"),
                     "fix": lambda: self._fix_file_perms("/etc/shadow", "640")},
            "7.3": {"category": "Files", "description": "/etc/group права = 644",
                     "check": lambda: self._check_file_perms("/etc/group", "644"),
                     "fix": lambda: self._fix_file_perms("/etc/group", "644")},
            "7.4": {"category": "Files", "description": "/etc/ssh/sshd_config права <= 600",
                     "check": lambda: self._check_file_perms_max("/etc/ssh/sshd_config", "600"),
                     "fix": lambda: self._fix_file_perms("/etc/ssh/sshd_config", "600")},
            "8.1": {"category": "Fail2ban", "description": "Fail2ban установлен и запущен",
                     "check": lambda: self._check_fail2ban_installed(),
                     "fix": lambda: self._fix_fail2ban_installed()},
            "8.2": {"category": "Fail2ban", "description": "Fail2ban: SSH защита активна",
                     "check": lambda: self._check_fail2ban_ssh(),
                     "fix": lambda: self._fix_fail2ban_ssh()},
            "8.3": {"category": "Fail2ban", "description": "Fail2ban: бан после 3 попыток",
                     "check": lambda: self._check_fail2ban_maxretry(),
                     "fix": lambda: self._fix_fail2ban_maxretry()},
            "9.1": {"category": "Updates", "description": "Unattended-upgrades установлен",
                     "check": lambda: self._check_unattended_upgrades(),
                     "fix": lambda: self._fix_unattended_upgrades()},
            "9.2": {"category": "Updates", "description": "Unattended-upgrades настроен",
                     "check": lambda: self._check_unattended_upgrades_config(),
                     "fix": lambda: self._fix_unattended_upgrades_config()},
            "10.1": {"category": "Updates", "description": "Needrestart установлен",
                      "check": lambda: self._check_needrestart(),
                      "fix": lambda: self._fix_needrestart()},
        }

    def _load_checks_from_yaml(self, yaml_path: Path) -> Optional[Dict]:
        """Загружает реестр проверок из YAML-конфига"""
        try:
            import yaml
        except ImportError:
            self.logger.warning("PyYAML не установлен, использую хардкод")
            return None

        if not yaml_path.exists():
            self.logger.info(f"YAML конфиг не найден: {yaml_path}, использую хардкод")
            return None

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Ошибка загрузки YAML: {e}")
            return None

        if not data or 'checks' not in data:
            self.logger.warning("YAML не содержит секции checks")
            return None

        registry = self._build_check_registry()
        yaml_category_map = {
            'network': 'Network', 'ssh': 'SSH', 'authentication': 'Auth',
            'file_permissions': 'Files', 'fail2ban': 'Fail2ban', 'updates': 'Updates',
        }

        checks = {}
        for yaml_cat, items in data['checks'].items():
            cat = yaml_category_map.get(yaml_cat, yaml_cat.capitalize())
            for item in items:
                cis_id = item['cis_id']
                if cis_id in registry:
                    checks[cis_id] = {
                        "category": cat,
                        "description": item.get('description', ''),
                        "check": registry[cis_id]['check'],
                        "fix": registry[cis_id]['fix'],
                    }
                else:
                    self.logger.warning(f"Чек {cis_id} из YAML не найден в реестре реализаций")

        # Добавляем проверки, которые есть в реестре, но не в YAML
        extras = {'1.4.1', '1.7.1', '1.7.2'}
        for eid in extras:
            if eid in registry and eid not in checks:
                checks[eid] = registry[eid]

        self.logger.info(f"Загружено {len(checks)} проверок из YAML")
        return checks

    def _build_check_registry(self) -> Dict:
        """Строит реестр проверок с привязкой к реализациям"""
        return {
            "1.4.1": {"category": "CoreDumps", "description": "Core dumps отключены",
                       "check": lambda: self._check_core_dumps(),
                       "fix": lambda: self._fix_core_dumps()},
            "1.7.1": {"category": "Banners", "description": "/etc/issue содержит предупреждение",
                       "check": lambda: self._check_banner("/etc/issue"),
                       "fix": lambda: self._fix_banner("/etc/issue")},
            "1.7.2": {"category": "Banners", "description": "/etc/issue.net содержит предупреждение",
                       "check": lambda: self._check_banner("/etc/issue.net"),
                       "fix": lambda: self._fix_banner("/etc/issue.net")},
            "3.1": {"category": "Network", "description": "IP forwarding отключен",
                     "check": lambda: self._check_sysctl("net.ipv4.ip_forward", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.ip_forward", "0")},
            "3.2": {"category": "Network", "description": "Packet redirect sending отключен",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.send_redirects", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.send_redirects", "0")},
            "3.3": {"category": "Network", "description": "Source routed packets отключены",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.accept_source_route", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.accept_source_route", "0")},
            "3.4": {"category": "Network", "description": "ICMP redirects отключены",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.accept_redirects", "0"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.accept_redirects", "0")},
            "3.5": {"category": "Network", "description": "Reverse path filtering включен",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.rp_filter", "1"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.rp_filter", "1")},
            "3.6": {"category": "Network", "description": "Suspicious packets logging включен",
                     "check": lambda: self._check_sysctl("net.ipv4.conf.all.log_martians", "1"),
                     "fix": lambda: self._fix_sysctl("net.ipv4.conf.all.log_martians", "1")},
            "5.2": {"category": "SSH", "description": "SSH: вход root отключен",
                     "check": lambda: self._check_ssh_param("permitrootlogin", "no"),
                     "fix": lambda: self._fix_ssh_param("PermitRootLogin", "no")},
            "5.3": {"category": "SSH", "description": "SSH: MaxAuthTries <= 4",
                     "check": lambda: self._check_ssh_param_max("maxauthtries", 4),
                     "fix": lambda: self._fix_ssh_param("MaxAuthTries", "3")},
            "5.4": {"category": "SSH", "description": "SSH: IgnoreRhosts включен",
                     "check": lambda: self._check_ssh_param("ignorerhosts", "yes"),
                     "fix": lambda: self._fix_ssh_param("IgnoreRhosts", "yes")},
            "5.5": {"category": "SSH", "description": "SSH: HostBasedAuthentication отключен",
                     "check": lambda: self._check_ssh_param("hostbasedauthentication", "no"),
                     "fix": lambda: self._fix_ssh_param("HostBasedAuthentication", "no")},
            "5.6": {"category": "SSH", "description": "SSH: PermitEmptyPasswords отключен",
                     "check": lambda: self._check_ssh_param("permitemptypasswords", "no"),
                     "fix": lambda: self._fix_ssh_param("PermitEmptyPasswords", "no")},
            "5.7": {"category": "SSH", "description": "SSH: X11Forwarding отключен",
                     "check": lambda: self._check_ssh_param("x11forwarding", "no"),
                     "fix": lambda: self._fix_ssh_param("X11Forwarding", "no")},
            "6.1": {"category": "Auth", "description": "PASS_MAX_DAYS <= 365",
                     "check": lambda: self._check_login_def("PASS_MAX_DAYS", max_val=365, min_val=1),
                     "fix": lambda: self._fix_login_def("PASS_MAX_DAYS", "365")},
            "6.2": {"category": "Auth", "description": "PASS_MIN_DAYS >= 1",
                     "check": lambda: self._check_login_def("PASS_MIN_DAYS", min_val=1),
                     "fix": lambda: self._fix_login_def("PASS_MIN_DAYS", "1")},
            "6.3": {"category": "Auth", "description": "UMASK >= 027",
                     "check": lambda: self._check_umask("027"),
                     "fix": lambda: self._fix_login_def("UMASK", "027")},
            "7.1": {"category": "Files", "description": "/etc/passwd права = 644",
                     "check": lambda: self._check_file_perms("/etc/passwd", "644"),
                     "fix": lambda: self._fix_file_perms("/etc/passwd", "644")},
            "7.2": {"category": "Files", "description": "/etc/shadow права <= 640",
                     "check": lambda: self._check_file_perms_max("/etc/shadow", "640"),
                     "fix": lambda: self._fix_file_perms("/etc/shadow", "640")},
            "7.3": {"category": "Files", "description": "/etc/group права = 644",
                     "check": lambda: self._check_file_perms("/etc/group", "644"),
                     "fix": lambda: self._fix_file_perms("/etc/group", "644")},
            "7.4": {"category": "Files", "description": "/etc/ssh/sshd_config права <= 600",
                     "check": lambda: self._check_file_perms_max("/etc/ssh/sshd_config", "600"),
                     "fix": lambda: self._fix_file_perms("/etc/ssh/sshd_config", "600")},
            "8.1": {"category": "Fail2ban", "description": "Fail2ban установлен и запущен",
                     "check": lambda: self._check_fail2ban_installed(),
                     "fix": lambda: self._fix_fail2ban_installed()},
            "8.2": {"category": "Fail2ban", "description": "Fail2ban: SSH защита активна",
                     "check": lambda: self._check_fail2ban_ssh(),
                     "fix": lambda: self._fix_fail2ban_ssh()},
            "8.3": {"category": "Fail2ban", "description": "Fail2ban: бан после 3 попыток",
                     "check": lambda: self._check_fail2ban_maxretry(),
                     "fix": lambda: self._fix_fail2ban_maxretry()},
            "9.1": {"category": "Updates", "description": "Unattended-upgrades установлен",
                     "check": lambda: self._check_unattended_upgrades(),
                     "fix": lambda: self._fix_unattended_upgrades()},
            "9.2": {"category": "Updates", "description": "Unattended-upgrades настроен",
                     "check": lambda: self._check_unattended_upgrades_config(),
                     "fix": lambda: self._fix_unattended_upgrades_config()},
            "10.1": {"category": "Updates", "description": "Needrestart установлен",
                      "check": lambda: self._check_needrestart(),
                      "fix": lambda: self._fix_needrestart()},
        }
    
    def _run_cmd(self, cmd: str, check: bool = True) -> Tuple[int, str, str]:
        """Безопасное выполнение команд через shlex.split()"""
        try:
            args = shlex.split(cmd)
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=10,
                check=check
            )
            return result.returncode, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timeout"
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout.strip() if e.stdout else "", e.stderr.strip() if e.stderr else ""
        except Exception as e:
            return -1, "", str(e)
    
    # ============ Network Checks ============
    
    def _check_sysctl(self, param: str, expected: str) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd(f"sysctl -n {param}")
        if rc == 0 and out == expected:
            return Status.PASS, ""
        return Status.FAIL, f"Текущее: {out}, ожидалось: {expected}"
    
    def _fix_sysctl(self, param: str, value: str) -> Tuple[bool, str]:
        sysctl_file = Path("/etc/sysctl.d/99-cis-vps.conf")
        
        if sysctl_file.exists():
            content = sysctl_file.read_text()
        else:
            content = "# CIS Debian 12 VPS Hardening\n"
        
        pattern = rf"^{re.escape(param)}\s*="
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{param} = {value}", content, flags=re.MULTILINE)
        else:
            content += f"\n{param} = {value}"
        
        sysctl_file.write_text(content)
        
        rc, _, err = self._run_cmd("sysctl --system")
        if rc == 0:
            return True, "Применено"
        return False, err
    
    # ============ SSH Checks ============
    
    def _check_ssh_param(self, param: str, expected: str) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("sshd -T")
        if rc != 0:
            return Status.ERROR, "Не удалось получить конфигурацию SSH"
        
        for line in out.split('\n'):
            if line.lower().startswith(param.lower()):
                value = line.split()[-1].lower()
                if value == expected.lower():
                    return Status.PASS, ""
                return Status.FAIL, f"Текущее: {value}, ожидалось: {expected}"
        
        return Status.FAIL, f"Параметр {param} не найден"
    
    def _check_ssh_param_max(self, param: str, max_val: int) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("sshd -T")
        if rc != 0:
            return Status.ERROR, "Не удалось получить конфигурацию SSH"
        
        for line in out.split('\n'):
            if line.lower().startswith(param.lower()):
                try:
                    value = int(line.split()[-1])
                    if value <= max_val:
                        return Status.PASS, f"Значение: {value}"
                    return Status.FAIL, f"Текущее: {value}, максимум: {max_val}"
                except ValueError:
                    return Status.ERROR, "Не удалось преобразовать в число"
        
        return Status.FAIL, f"Параметр {param} не найден"
    
    def _fix_ssh_param(self, param: str, value: str) -> Tuple[bool, str]:
        sshd_dir = Path("/etc/ssh/sshd_config.d")
        sshd_dir.mkdir(exist_ok=True)
        conf_file = sshd_dir / "99-cis-hardening.conf"
        
        if conf_file.exists():
            content = conf_file.read_text()
        else:
            content = "# CIS Debian 12 VPS Hardening - SSH\n"
        
        pattern = rf"^{re.escape(param)}\s+"
        if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
            content = re.sub(pattern, f"{param} {value}\n", content, 
                           flags=re.MULTILINE | re.IGNORECASE)
        else:
            content += f"\n{param} {value}"
        
        conf_file.write_text(content)
        
        rc, _, err = self._run_cmd("sshd -t")
        if rc != 0:
            return False, f"Ошибка синтаксиса: {err}"
        
        rc, _, err = self._run_cmd("systemctl restart ssh")
        if rc == 0:
            return True, "SSH перезапущен"
        return False, f"Ошибка перезапуска: {err}"
    
    # ============ Auth Checks ============
    
    def _check_login_def(self, param: str, max_val: int = None, 
                         min_val: int = None) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd(f"grep '^\\s*{param}' /etc/login.defs")
        if rc != 0:
            return Status.FAIL, f"Параметр {param} не найден"
        
        try:
            value = int(out.split()[-1])
            
            if max_val is not None and value > max_val:
                return Status.FAIL, f"Текущее: {value}, максимум: {max_val}"
            if min_val is not None and value < min_val:
                return Status.FAIL, f"Текущее: {value}, минимум: {min_val}"
            
            return Status.PASS, f"Значение: {value}"
        except (ValueError, IndexError):
            return Status.ERROR, "Не удалось определить значение"
    
    def _fix_login_def(self, param: str, value: str) -> Tuple[bool, str]:
        login_def = Path("/etc/login.defs")
        content = login_def.read_text()
        
        pattern = rf"^(\s*{param}\s+)\d+"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, rf"\g<1>{value}", content, flags=re.MULTILINE)
            login_def.write_text(content)
            return True, "Обновлено"
        else:
            with open(login_def, "a") as f:
                f.write(f"\n{param}   {value}\n")
            return True, "Добавлено"
    
    def _check_umask(self, min_umask: str) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("grep '^\\s*UMASK' /etc/login.defs")
        if rc != 0:
            return Status.FAIL, "UMASK не найден"
        
        try:
            value = out.split()[-1]
            value_int = int(value, 8)
            min_int = int(min_umask, 8)
            
            if value_int >= min_int:
                return Status.PASS, f"Значение: {value}"
            return Status.FAIL, f"Текущее: {value}, минимум: {min_umask}"
        except (ValueError, IndexError):
            return Status.ERROR, "Не удалось определить значение"
    
    # ============ File Permissions Checks ============
    
    def _check_file_perms(self, path: str, expected: str) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd(f"stat -c %a {path}")
        if rc == 0 and out == expected:
            return Status.PASS, ""
        return Status.FAIL, f"Текущие права: {out}, ожидались: {expected}"
    
    def _check_file_perms_max(self, path: str, max_perms: str) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd(f"stat -c %a {path}")
        if rc != 0:
            return Status.ERROR, "Не удалось получить права"
        
        try:
            current = int(out, 8)
            maximum = int(max_perms, 8)
            
            if current <= maximum:
                return Status.PASS, f"Права: {out}"
            return Status.FAIL, f"Текущие: {out}, максимум: {max_perms}"
        except ValueError:
            return Status.ERROR, "Не удалось преобразовать права"
    
    def _fix_file_perms(self, path: str, perms: str) -> Tuple[bool, str]:
        rc, _, err = self._run_cmd(f"chmod {perms} {path}")
        if rc == 0:
            return True, "Права обновлены"
        return False, err
    
    # ============ Banner Checks ============
    
    def _check_banner(self, path: str) -> Tuple[str, str]:
        if not Path(path).exists():
            return Status.FAIL, "Файл не существует"
        
        rc, out, _ = self._run_cmd(f"cat {path}")
        keywords = ["unauthorized", "prohibited", "secured", "monitored"]
        
        if any(keyword in out.lower() for keyword in keywords):
            return Status.PASS, ""
        return Status.FAIL, "Баннер отсутствует или не содержит ключевых слов"
    
    def _fix_banner(self, path: str) -> Tuple[bool, str]:
        banner = """-------------------------------------------------------------------------
*                           NOTICE TO USER                                    *
* This is a secured system. Unauthorized access is prohibited.                *
* All activities on this system are logged and monitored.                     *
-------------------------------------------------------------------------
"""
        Path(path).write_text(banner)
        return True, "Баннер создан"
    
    # ============ Core Dumps Checks ============
    
    def _check_core_dumps(self) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("grep -E '^\\*.*hard.*core.*0' /etc/security/limits.conf")
        if rc == 0 and out:
            return Status.PASS, ""
        return Status.FAIL, "Правило не найдено"
    
    def _fix_core_dumps(self) -> Tuple[bool, str]:
        limits_file = Path("/etc/security/limits.conf")
        content = limits_file.read_text()
        
        if "* hard core 0" in content:
            return True, "Уже настроено"
        
        with open(limits_file, "a") as f:
            f.write("\n* hard core 0\n")
        return True, "Добавлено"
    
    # ============ Fail2ban Methods ============
    
    def _check_fail2ban_installed(self) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("dpkg -l fail2ban | grep ^ii")
        if rc == 0 and out:
            rc2, status, _ = self._run_cmd("systemctl is-active fail2ban")
            if rc2 == 0 and status == "active":
                return Status.PASS, "Установлен и запущен"
            return Status.FAIL, "Установлен, но не запущен"
        return Status.FAIL, "Не установлен"
    
    def _fix_fail2ban_installed(self) -> Tuple[bool, str]:
        rc, _, err = self._run_cmd("apt-get update && apt-get install -y fail2ban")
        if rc != 0:
            return False, f"Ошибка установки: {err}"
        
        rc, _, err = self._run_cmd("systemctl enable --now fail2ban")
        if rc == 0:
            return True, "Установлен и запущен"
        return False, err
    
    def _check_fail2ban_ssh(self) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("fail2ban-client status")
        if rc == 0 and "sshd" in out:
            rc2, status, _ = self._run_cmd("fail2ban-client status sshd")
            if rc2 == 0:
                return Status.PASS, "SSH jail активен"
            return Status.FAIL, "SSH jail неактивен"
        return Status.FAIL, "SSH jail не настроен"
    
    def _fix_fail2ban_ssh(self) -> Tuple[bool, str]:
        jail_local = Path("/etc/fail2ban/jail.local")
        
        content = """# Fail2ban configuration for SSH
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
"""
        
        jail_local.write_text(content)
        
        rc, _, err = self._run_cmd("systemctl restart fail2ban")
        if rc == 0:
            return True, "SSH jail настроен"
        return False, err
    
    def _check_fail2ban_maxretry(self) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("fail2ban-client get sshd maxretry")
        if rc == 0:
            try:
                maxretry = int(out.strip())
                if maxretry <= 3:
                    return Status.PASS, f"maxretry = {maxretry}"
                return Status.FAIL, f"maxretry = {maxretry}, должно быть <= 3"
            except ValueError:
                return Status.ERROR, "Не удалось определить maxretry"
        return Status.FAIL, "Не удалось получить maxretry"
    
    def _fix_fail2ban_maxretry(self) -> Tuple[bool, str]:
        jail_local = Path("/etc/fail2ban/jail.local")
        if not jail_local.exists():
            success, msg = self._fix_fail2ban_ssh()
            if not success:
                return False, msg
        
        content = jail_local.read_text()
        content = content.replace("maxretry = 5", "maxretry = 3")
        content = content.replace("maxretry = 4", "maxretry = 3")
        jail_local.write_text(content)
        
        rc, _, err = self._run_cmd("systemctl restart fail2ban")
        if rc == 0:
            return True, "maxretry установлен в 3"
        return False, err
    
    # ============ Unattended Upgrades Methods ============
    
    def _check_unattended_upgrades(self) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("dpkg -l unattended-upgrades | grep ^ii")
        if rc == 0 and out:
            return Status.PASS, "Установлен"
        return Status.FAIL, "Не установлен"
    
    def _fix_unattended_upgrades(self) -> Tuple[bool, str]:
        rc, _, err = self._run_cmd("apt-get install -y unattended-upgrades")
        if rc == 0:
            return True, "Установлен"
        return False, err
    
    def _check_unattended_upgrades_config(self) -> Tuple[str, str]:
        config_file = Path("/etc/apt/apt.conf.d/20auto-upgrades")
        if not config_file.exists():
            return Status.FAIL, "Конфиг не найден"
        
        content = config_file.read_text()
        if 'APT::Periodic::Unattended-Upgrade "1"' in content:
            return Status.PASS, "Настроен правильно"
        return Status.FAIL, "Неправильная конфигурация"
    
    def _fix_unattended_upgrades_config(self) -> Tuple[bool, str]:
        config_content = """APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
"""
        
        config_file = Path("/etc/apt/apt.conf.d/20auto-upgrades")
        config_file.write_text(config_content)
        
        rc, _, err = self._run_cmd("systemctl enable --now unattended-upgrades")
        if rc == 0:
            return True, "Настроен и запущен"
        return False, err
    
    # ============ Needrestart Methods ============
    
    def _check_needrestart(self) -> Tuple[str, str]:
        rc, out, _ = self._run_cmd("dpkg -l needrestart | grep ^ii")
        if rc == 0 and out:
            return Status.PASS, "Установлен"
        return Status.FAIL, "Не установлен"
    
    def _fix_needrestart(self) -> Tuple[bool, str]:
        rc, _, err = self._run_cmd("apt-get install -y needrestart")
        if rc == 0:
            return True, "Установлен"
        return False, err
    
    # ============ Public Methods ============
    
    def audit(self, categories: List[str] = None, output_format: str = "text", output_path: str = None) -> AuditReport:
        """Запуск аудита системы"""
        start_time = datetime.now()
        results = []
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}🔍 CIS Debian 12 Level 1 Server Audit{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")
        
        for cis_id, check_data in sorted(self.checks.items()):
            if categories and check_data["category"] not in categories:
                continue
            
            print(f"{Colors.BLUE}[{cis_id}]{Colors.NC} {check_data['description']}... ", end="")
            
            try:
                status, details = check_data["check"]()
                
                if status == Status.PASS:
                    print(f"{Colors.GREEN}✅ PASS{Colors.NC}")
                elif status == Status.FAIL:
                    print(f"{Colors.RED}❌ FAIL{Colors.NC}")
                    if details:
                        print(f"      {Colors.YELLOW}└─ {details}{Colors.NC}")
                else:
                    print(f"{Colors.MAGENTA}⚠️  ERROR{Colors.NC}")
                    if details:
                        print(f"      {Colors.YELLOW}└─ {details}{Colors.NC}")
                
                results.append(CheckResult(
                    cis_id=cis_id,
                    category=check_data["category"],
                    description=check_data["description"],
                    status=status,
                    details=details,
                    timestamp=datetime.now().isoformat()
                ))
                
            except Exception as e:
                print(f"{Colors.MAGENTA}⚠️  ERROR{Colors.NC}")
                print(f"      {Colors.RED}└─ {str(e)}{Colors.NC}")
                results.append(CheckResult(
                    cis_id=cis_id,
                    category=check_data["category"],
                    description=check_data["description"],
                    status=Status.ERROR,
                    details=str(e),
                    timestamp=datetime.now().isoformat()
                ))
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        passed = sum(1 for r in results if r.status == Status.PASS)
        failed = sum(1 for r in results if r.status == Status.FAIL)
        errors = sum(1 for r in results if r.status == Status.ERROR)
        total = len(results)
        score = (passed / total * 100) if total > 0 else 0
        
        _, hostname, _ = self._run_cmd("hostname")
        _, kernel, _ = self._run_cmd("uname -r")
        
        report = AuditReport(
            timestamp=end_time.isoformat(),
            hostname=hostname,
            kernel=kernel,
            total_checks=total,
            passed=passed,
            failed=failed,
            errors=errors,
            compliance_score=round(score, 2),
            duration_seconds=round(duration, 2),
            checks=results
        )
        
        save_path = output_path or self.current_report_file
        self._save_report(report, save_path)
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"{Colors.BOLD}📊 РЕЗУЛЬТАТЫ АУДИТА{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"✅ Пройдено: {Colors.GREEN}{passed}{Colors.NC}")
        print(f"❌ Провалено: {Colors.RED}{failed}{Colors.NC}")
        print(f"⚠️  Ошибки: {Colors.MAGENTA}{errors}{Colors.NC}")
        print(f"🎯 Compliance: {Colors.BOLD}{score:.1f}%{Colors.NC}")
        print(f"⏱️  Время: {duration:.2f}s")
        print(f"💾 Отчет: {save_path}")
        
        if failed > 0:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ ТРЕБУЮТ ИСПРАВЛЕНИЯ:{Colors.NC}")
            for r in results:
                if r.status == Status.FAIL:
                    print(f"  {Colors.RED}[{r.cis_id}]{Colors.NC} {r.description}")
                    if r.details:
                        print(f"    {Colors.YELLOW}└─ {r.details}{Colors.NC}")
        
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")
        
        return report
    
    def _save_report(self, report: AuditReport, report_path: str = None):
        """Сохранение отчета в историю"""
        path = Path(report_path) if report_path else self.current_report_file
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        
        history_file = self.history_dir / f"audit_{report.timestamp.replace(':', '-')}.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
    
    def fix(self, categories: List[str] = None, cis_ids: List[str] = None, 
            dry_run: bool = False, force: bool = False) -> Tuple[int, int]:
        """Исправление нарушений"""
        if not self.current_report_file.exists():
            print(f"{Colors.RED}❌ Сначала запустите аудит: cis_manager.py audit{Colors.NC}")
            return 0, 0
        
        with open(self.current_report_file, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        
        failed_checks = [
            check for check in report_data["checks"] 
            if check["status"] == "FAIL"
        ]
        
        if not failed_checks:
            print(f"{Colors.GREEN}✅ Система полностью соответствует CIS!{Colors.NC}")
            return 0, 0
        
        if categories:
            failed_checks = [c for c in failed_checks if c["category"] in categories]
        if cis_ids:
            failed_checks = [c for c in failed_checks if c["cis_id"] in cis_ids]
        
        if not failed_checks:
            print(f"{Colors.YELLOW}⚠️  Нет нарушений для исправления{Colors.NC}")
            return 0, 0
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}🔧 CIS Fix Tool{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        
        if dry_run:
            print(f"\n{Colors.YELLOW}🔍 DRY-RUN MODE (без реальных изменений){Colors.NC}\n")
        elif not force:
            print(f"\n{Colors.YELLOW}⚠️  Будет исправлено {len(failed_checks)} нарушений{Colors.NC}")
            print(f"{Colors.RED}⚠️  ВАЖНО: Не закрывайте текущую SSH-сессию!{Colors.NC}\n")
            
            response = input("Продолжить? (y/N): ")
            if response.lower() != 'y':
                print(f"{Colors.YELLOW}❌ Операция отменена{Colors.NC}")
                return 0, 0
        
        backup_id = None
        if not dry_run:
            backup_id = self._create_backup()
            print(f"\n💾 Backup создан: {backup_id}\n")
        
        fixed = 0
        failed = 0
        
        for check in failed_checks:
            cis_id = check["cis_id"]
            
            if cis_id not in self.checks:
                print(f"{Colors.YELLOW}⚠️  [{cis_id}] Нет функции исправления{Colors.NC}")
                continue
            
            print(f"{Colors.BLUE}[{cis_id}]{Colors.NC} {check['description']}... ", end="")
            
            if dry_run:
                print(f"{Colors.CYAN}🔍 WOULD FIX{Colors.NC}")
                fixed += 1
                continue
            
            try:
                success, message = self.checks[cis_id]["fix"]()
                
                if success:
                    print(f"{Colors.GREEN}✅ FIXED{Colors.NC}")
                    fixed += 1
                else:
                    print(f"{Colors.RED}❌ FAILED{Colors.NC}")
                    print(f"      {Colors.YELLOW}└─ {message}{Colors.NC}")
                    failed += 1
            except Exception as e:
                print(f"{Colors.RED}❌ ERROR{Colors.NC}")
                print(f"      {Colors.YELLOW}└─ {str(e)}{Colors.NC}")
                failed += 1
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"{Colors.BOLD}📊 РЕЗУЛЬТАТЫ ИСПРАВЛЕНИЯ{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"✅ Исправлено: {Colors.GREEN}{fixed}{Colors.NC}")
        print(f"❌ Ошибок: {Colors.RED}{failed}{Colors.NC}")
        
        if not dry_run and fixed > 0:
            print(f"\n{Colors.CYAN}ℹ️  Запустите аудит для проверки: cis_manager.py audit{Colors.NC}")
            if backup_id:
                print(f"{Colors.CYAN}ℹ️  Для отката: cis_manager.py rollback {backup_id}{Colors.NC}")
        
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")
        
        return fixed, failed
    
    def _create_backup(self) -> str:
        """Создание backup критичных файлов"""
        backup_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / backup_id
        backup_path.mkdir(exist_ok=True)
        
        files_to_backup = [
            "/etc/sysctl.d/99-cis-vps.conf",
            "/etc/ssh/sshd_config.d/99-cis-hardening.conf",
            "/etc/login.defs",
            "/etc/issue",
            "/etc/issue.net",
            "/etc/security/limits.conf",
            "/etc/fail2ban/jail.local",
            "/etc/apt/apt.conf.d/20auto-upgrades",
        ]
        
        for file_path in files_to_backup:
            src = Path(file_path)
            if src.exists():
                try:
                    shutil.copy2(src, backup_path / src.name)
                except Exception as e:
                    print(f"{Colors.YELLOW}⚠️  Не удалось сделать backup {file_path}: {e}{Colors.NC}")
        
        return backup_id
    
    def rollback(self, backup_id: str, force: bool = False):
        """Откат к backup"""
        backup_path = self.backup_dir / backup_id
        
        if not backup_path.exists():
            print(f"{Colors.RED}❌ Backup не найден: {backup_id}{Colors.NC}")
            print(f"   Доступные backup: {', '.join([p.name for p in self.backup_dir.iterdir()])}")
            return
        
        print(f"\n{Colors.YELLOW}⚠️  Откат к backup: {backup_id}{Colors.NC}")
        print(f"   Файлы в backup: {', '.join([f.name for f in backup_path.iterdir()])}")
        
        if not force:
            response = input("\nПродолжить? (y/N): ")
            if response.lower() != 'y':
                print(f"{Colors.YELLOW}❌ Операция отменена{Colors.NC}")
                return
        
        file_map = {
            "99-cis-vps.conf": "/etc/sysctl.d/99-cis-vps.conf",
            "99-cis-hardening.conf": "/etc/ssh/sshd_config.d/99-cis-hardening.conf",
            "login.defs": "/etc/login.defs",
            "issue": "/etc/issue",
            "issue.net": "/etc/issue.net",
            "limits.conf": "/etc/security/limits.conf",
            "jail.local": "/etc/fail2ban/jail.local",
            "20auto-upgrades": "/etc/apt/apt.conf.d/20auto-upgrades",
        }
        
        for backup_file in backup_path.iterdir():
            if backup_file.name in file_map:
                target = file_map[backup_file.name]
                shutil.copy2(backup_file, target)
                print(f"✅ Восстановлен: {target}")
        
        self._run_cmd("sysctl --system")
        self._run_cmd("systemctl restart ssh")
        self._run_cmd("systemctl restart fail2ban")
        
        print(f"\n{Colors.GREEN}✅ Откат завершен{Colors.NC}")
        print(f"{Colors.CYAN}ℹ️  Запустите audit для проверки{Colors.NC}")
    
    def history(self, limit: int = 10):
        """Показать историю аудитов"""
        history_files = sorted(self.history_dir.glob("audit_*.json"), reverse=True)[:limit]
        
        if not history_files:
            print(f"{Colors.YELLOW}⚠️  История пуста{Colors.NC}")
            return
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"{Colors.BOLD}📜 ИСТОРИЯ АУДИТОВ{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")
        
        print(f"{'Дата':<25} {'Compliance':<15} {'Passed':<10} {'Failed':<10}")
        print("-" * 70)
        
        for history_file in history_files:
            with open(history_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            timestamp = datetime.fromisoformat(report["timestamp"])
            date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            score = report["compliance_score"]
            passed = report["passed"]
            failed = report["failed"]
            
            if score >= 90:
                score_color = Colors.GREEN
            elif score >= 70:
                score_color = Colors.YELLOW
            else:
                score_color = Colors.RED
            
            print(f"{date_str:<25} {score_color}{score:.1f}%{Colors.NC}{'':<8} {passed:<10} {failed:<10}")
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")
    
    def diff(self, report1_path: str, report2_path: str):
        """Сравнить два отчета"""
        try:
            with open(report1_path, 'r', encoding='utf-8') as f:
                report1 = json.load(f)
            with open(report2_path, 'r', encoding='utf-8') as f:
                report2 = json.load(f)
        except FileNotFoundError as e:
            print(f"{Colors.RED}❌ Файл не найден: {e}{Colors.NC}")
            return
        
        checks1 = {c["cis_id"]: c["status"] for c in report1["checks"]}
        checks2 = {c["cis_id"]: c["status"] for c in report2["checks"]}
        
        all_ids = set(checks1.keys()) | set(checks2.keys())
        
        improved = []
        degraded = []
        
        for cis_id in all_ids:
            status1 = checks1.get(cis_id)
            status2 = checks2.get(cis_id)
            
            if status1 == "FAIL" and status2 == "PASS":
                improved.append(cis_id)
            elif status1 == "PASS" and status2 == "FAIL":
                degraded.append(cis_id)
        
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
        print(f"{Colors.BOLD}📊 СРАВНЕНИЕ ОТЧЕТОВ{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")
        
        print(f"Отчет 1: {report1['timestamp']} - {report1['compliance_score']:.1f}%")
        print(f"Отчет 2: {report2['timestamp']} - {report2['compliance_score']:.1f}%\n")
        
        if improved:
            print(f"{Colors.GREEN}✅ УЛУЧШЕНО ({len(improved)}):{Colors.NC}")
            for cis_id in improved:
                print(f"  {Colors.GREEN}[{cis_id}]{Colors.NC}")
        
        if degraded:
            print(f"\n{Colors.RED}❌ УХУДШЕНО ({len(degraded)}):{Colors.NC}")
            for cis_id in degraded:
                print(f"  {Colors.RED}[{cis_id}]{Colors.NC}")
        
        if not improved and not degraded:
            print(f"{Colors.YELLOW}⚠️  Изменений не обнаружено{Colors.NC}")
        
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")


def main():
    parser = argparse.ArgumentParser(
        description="CIS Debian 12 Level 1 Server Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s audit                          # Полный аудит
  %(prog)s audit --categories Network SSH # Аудит только сети и SSH
  %(prog)s fix                            # Исправить все
  %(prog)s fix --dry-run                  # Показать, что будет исправлено
  %(prog)s fix --categories Network       # Исправить только сеть
  %(prog)s history                        # Показать историю
  %(prog)s rollback 20260705_143022       # Откатить изменения
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Команды")
    
    audit_parser = subparsers.add_parser("audit", help="Запустить аудит")
    audit_parser.add_argument("--categories", nargs="+",
                             help="Категории для проверки")
    audit_parser.add_argument("--format", choices=["text", "json"], default="text",
                             help="Формат вывода")
    audit_parser.add_argument("--output", "-o",
                             help="Путь для сохранения JSON отчета (по умолч. cis_data/current_audit.json)")

    fix_parser = subparsers.add_parser("fix", help="Исправить нарушения")
    fix_parser.add_argument("--categories", nargs="+",
                           help="Категории для исправления")
    fix_parser.add_argument("--cis-ids", nargs="+",
                           help="Конкретные CIS ID для исправления")
    fix_parser.add_argument("--dry-run", action="store_true",
                           help="Показать, что будет исправлено (без изменений)")
    fix_parser.add_argument("--force", action="store_true",
                           help="Автоматическое подтверждение (без запросов)")
    fix_parser.add_argument("--yes", action="store_true",
                           help="То же, что --force (для обратной совместимости)")

    history_parser = subparsers.add_parser("history", help="Показать историю аудитов")
    history_parser.add_argument("--limit", type=int, default=10,
                               help="Количество записей (по умолчанию 10)")

    rollback_parser = subparsers.add_parser("rollback", help="Откатить изменения")
    rollback_parser.add_argument("backup_id", help="ID backup для восстановления")
    rollback_parser.add_argument("--force", action="store_true",
                                help="Автоматический откат (без запросов)")
    rollback_parser.add_argument("--yes", action="store_true",
                                help="То же, что --force (для обратной совместимости)")
    
    diff_parser = subparsers.add_parser("diff", help="Сравнить два отчета")
    diff_parser.add_argument("report1", help="Путь к первому отчету")
    diff_parser.add_argument("report2", help="Путь ко второму отчету")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if os.geteuid() != 0:
        print(f"{Colors.RED}❌ Требуется root (используйте sudo){Colors.NC}")
        sys.exit(1)
    
    manager = CISManager()
    
    force = getattr(args, 'force', False) or getattr(args, 'yes', False)

    if args.command == "audit":
        manager.audit(categories=args.categories, output_format=args.format, output_path=args.output)
    elif args.command == "fix":
        manager.fix(categories=args.categories, cis_ids=args.cis_ids,
                    dry_run=args.dry_run, force=force)
    elif args.command == "history":
        manager.history(limit=args.limit)
    elif args.command == "rollback":
        manager.rollback(args.backup_id, force=force)
    elif args.command == "diff":
        manager.diff(args.report1, args.report2)


if __name__ == "__main__":
    main()