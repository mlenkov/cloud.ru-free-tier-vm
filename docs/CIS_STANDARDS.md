# 📋 CIS Debian 12 Level 1 - Стандарты безопасности

## 🎯 Обзор

CIS Debian 12 Level 1 - это стандарты безопасности для Debian 12 (Bookworm), разработанные Center for Internet Security.

**Уровень 1**: Рекомендации, которые:
- Не нарушают функциональность
- Не требуют специфической конфигурации
- Работают для большинства систем

**Целевой показатель compliance**: 95%

---

## 📊 Структура проверок

```
CIS Debian 12 Level 1
├── 3. Сеть (Network)
├── 5. SSH
├── 6. Аутентификация
├── 7. Файловые права
├── 8. Fail2ban
└── 9. Обновления
```

---

## 🔗 3. Сеть (Network)

### 3.1 IP forwarding отключен

**Проверка**:
```bash
sysctl net.ipv4.ip_forward
# Ожидаемое: net.ipv4.ip_forward = 0
```

**Исправление**:
```bash
sysctl net.ipv4.ip_forward=0
# Добавить в /etc/sysctl.conf:
net.ipv4.ip_forward = 0
```

**Риск**: Если включен, сервер может использоваться для ретрансляции трафика.

---

### 3.2 Packet redirect sending отключен

**Проверка**:
```bash
sysctl net.ipv4.conf.all.send_redirects
# Ожидаемое: net.ipv4.conf.all.send_redirects = 0
```

**Исправление**:
```bash
sysctl net.ipv4.conf.all.send_redirects=0
```

---

### 3.3 Source routed packets отключены

**Проверка**:
```bash
sysctl net.ipv4.conf.all.accept_source_route
# Ожидаемое: net.ipv4.conf.all.accept_source_route = 0
```

**Исправление**:
```bash
sysctl net.ipv4.conf.all.accept_source_route=0
```

---

### 3.4 ICMP redirects отключены

**Проверка**:
```bash
sysctl net.ipv4.conf.all.accept_redirects
# Ожидаемое: net.ipv4.conf.all.accept_redirects = 0
```

**Исправление**:
```bash
sysctl net.ipv4.conf.all.accept_redirects=0
```

---

### 3.5 Reverse path filtering включен

**Проверка**:
```bash
sysctl net.ipv4.conf.all.rp_filter
# Ожидаемое: net.ipv4.conf.all.rp_filter = 1
```

**Исправление**:
```bash
sysctl net.ipv4.conf.all.rp_filter=1
```

**Риск**: Защита от spoofing атак.

---

### 3.6 Suspicious packets logging включен

**Проверка**:
```bash
sysctl net.ipv4.conf.all.log_martians
# Ожидаемое: net.ipv4.conf.all.log_martians = 1
```

**Исправление**:
```bash
sysctl net.ipv4.conf.all.log_martians=1
```

---

## 🔐 5. SSH Security

### 5.2 SSH: вход root отключен

**Проверка**:
```bash
grep "PermitRootLogin" /etc/ssh/sshd_config
# Ожидаемое: PermitRootLogin no
```

**Исправление**:
```bash
sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl reload sshd
```

---

### 5.3 SSH: MaxAuthTries <= 4

**Проверка**:
```bash
grep "MaxAuthTries" /etc/ssh/sshd_config
# Ожидаемое: MaxAuthTries 3 или меньше
```

**Исправление**:
```bash
sed -i 's/^MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config
systemctl reload sshd
```

---

### 5.4 SSH: IgnoreRhosts включен

**Проверка**:
```bash
grep "IgnoreRhosts" /etc/ssh/sshd_config
# Ожидаемое: IgnoreRhosts yes
```

**Исправление**:
```bash
sed -i 's/^IgnoreRhosts.*/IgnoreRhosts yes/' /etc/ssh/sshd_config
systemctl reload sshd
```

---

### 5.5 SSH: HostBasedAuthentication отключен

**Проверка**:
```bash
grep "HostBasedAuthentication" /etc/ssh/sshd_config
# Ожидаемое: HostBasedAuthentication no
```

**Исправление**:
```bash
sed -i 's/^HostBasedAuthentication.*/HostBasedAuthentication no/' /etc/ssh/sshd_config
systemctl reload sshd
```

---

### 5.6 SSH: PermitEmptyPasswords отключен

**Проверка**:
```bash
grep "PermitEmptyPasswords" /etc/ssh/sshd_config
# Ожидаемое: PermitEmptyPasswords no
```

**Исправление**:
```bash
sed -i 's/^PermitEmptyPasswords.*/PermitEmptyPasswords no/' /etc/ssh/sshd_config
systemctl reload sshd
```

---

### 5.7 SSH: X11Forwarding отключен

**Проверка**:
```bash
grep "X11Forwarding" /etc/ssh/sshd_config
# Ожидаемое: X11Forwarding no
```

**Исправление**:
```bash
sed -i 's/^X11Forwarding.*/X11Forwarding no/' /etc/ssh/sshd_config
systemctl reload sshd
```

---

## 🔑 6. Аутентификация

### 6.1 PASS_MAX_DAYS <= 365

**Проверка**:
```bash
grep "PASS_MAX_DAYS" /etc/login.defs
# Ожидаемое: PASS_MAX_DAYS 365 или меньше
```

**Исправление**:
```bash
sed -i 's/^PASS_MAX_DAYS.*/PASS_MAX_DAYS 365/' /etc/login.defs
```

---

### 6.2 PASS_MIN_DAYS >= 1

**Проверка**:
```bash
grep "PASS_MIN_DAYS" /etc/login.defs
# Ожидаемое: PASS_MIN_DAYS 1 или больше
```

**Исправление**:
```bash
sed -i 's/^PASS_MIN_DAYS.*/PASS_MIN_DAYS 1/' /etc/login.defs
```

---

### 6.3 UMASK >= 027

**Проверка**:
```bash
grep "UMASK" /etc/login.defs
# Ожидаемое: UMASK 027 или строже
```

**Исправление**:
```bash
sed -i 's/^UMASK.*/UMASK 027/' /etc/login.defs
```

---

## 📁 7. Файловые права

### 7.1 /etc/passwd права = 644

**Проверка**:
```bash
stat -c "%a" /etc/passwd
# Ожидаемое: 644
```

**Исправление**:
```bash
chmod 644 /etc/passwd
```

---

### 7.2 /etc/shadow права <= 640

**Проверка**:
```bash
stat -c "%a" /etc/shadow
# Ожидаемое: 640 или строже
```

**Исправление**:
```bash
chmod 640 /etc/shadow
```

---

### 7.3 /etc/group права = 644

**Проверка**:
```bash
stat -c "%a" /etc/group
# Ожидаемое: 644
```

**Исправление**:
```bash
chmod 644 /etc/group
```

---

### 7.4 /etc/ssh/sshd_config права <= 600

**Проверка**:
```bash
stat -c "%a" /etc/ssh/sshd_config
# Ожидаемое: 600 или строже
```

**Исправление**:
```bash
chmod 600 /etc/ssh/sshd_config
```

---

## 🛡️ 8. Fail2ban

### 8.1 Fail2ban установлен и запущен

**Проверка**:
```bash
systemctl is-active fail2ban
# Ожидаемое: active
```

**Исправление**:
```bash
apt-get install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

---

### 8.2 Fail2ban: SSH защита активна

**Проверка**:
```bash
grep -A5 \"\\[sshd\\]\" /etc/fail2ban/jail.local
# Ожидаемое: enabled = true
```

**Исправление**:
```bash
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
maxretry = 3
findtime = 600
bantime = 3600
EOF
systemctl restart fail2ban
```

---

### 8.3 Fail2ban: бан после 3 попыток

**Проверка**:
```bash
grep "maxretry" /etc/fail2ban/jail.local
# Ожидаемое: maxretry = 3
```

**Исправление**: См. 8.2

---

## 🔄 9. Обновления

### 9.1 Unattended-upgrades установлен

**Проверка**:
```bash
dpkg -l | grep unattended-upgrades
# Ожидаемое: ii  unattended-upgrades
```

**Исправление**:
```bash
apt-get install -y unattended-upgrades
```

---

### 9.2 Unattended-upgrades настроен

**Проверка**:
```bash
ls /etc/apt/apt.conf.d/20auto-upgrades
# Ожидаемое: файл существует
```

**Исправление**:
```bash
dpkg-reconfigure -plow unattended-upgrades
```

---

### 10.1 Needrestart установлен

**Проверка**:
```bash
dpkg -l | grep needrestart
# Ожидаемое: ii  needrestart
```

**Исправление**:
```bash
apt-get install -y needrestart
```

---

## 📈 Метрики compliance

| Категория | Проверок | Критичных | % |
|-----------|----------|-----------|----|
| Network | 6 | 6 | 100% |
| SSH | 6 | 6 | 100% |
| Authentication | 3 | 3 | 100% |
| File Permissions | 4 | 4 | 100% |
| Fail2ban | 3 | 3 | 100% |
| Updates | 3 | 3 | 100% |
| **Всего** | **25** | **25** | **100%** |

**Целевой показатель**: 95%

---

## 📚 Официальные ссылки

- [CIS Debian 12 Benchmark](https://www.cisecurity.org/cis-benchmarks/)
- [CIS Debian 12 Level 1](https://www.cisecurity.org/benchmark/debian_linux/)
- [Debian Security Hardening](https://wiki.debian.org/SecurityHardening)

---

*Документация генерируется AI Employee на основе config/cis_standard.yaml*
