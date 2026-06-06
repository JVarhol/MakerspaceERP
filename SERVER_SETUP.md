# Makerspace ERP — Proxmox VM Setup Guide
Proxmox VE 8 · Debian 12 (Bookworm) · Bare metal systemd

---

## Part 1 — Download the Debian ISO to Proxmox

1. In the Proxmox web UI, go to **Datacenter → your node → local (storage) → ISO Images**.
2. Click **Download from URL** and paste:
   ```
   https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.10.0-amd64-netinst.iso
   ```
   > Grab the latest netinstall URL from https://www.debian.org/CD/netinst/ if this one is outdated.
3. Click **Query URL** → **Download**. Wait for it to finish (usually < 1 min on a fast connection).

---

## Part 2 — Create the VM

Go to **Datacenter → Create VM** (top-right button).

### General tab
| Field | Value |
|-------|-------|
| VM ID | any free number, e.g. `200` |
| Name | `makerspace-erp` |

### OS tab
| Field | Value |
|-------|-------|
| ISO Image | `debian-12.10.0-amd64-netinst.iso` (just downloaded) |
| Guest OS Type | Linux |
| Version | 6.x - 2.6 Kernel |

### System tab
| Field | Value |
|-------|-------|
| Machine | q35 |
| BIOS | SeaBIOS (default) |
| SCSI Controller | VirtIO SCSI single |
| Qemu Agent | ✅ checked |

### Disks tab
| Field | Value |
|-------|-------|
| Bus/Device | VirtIO Block 0 |
| Storage | your preferred storage (e.g. `local-lvm`) |
| Disk size | **32 GB** (plenty; ERP + DB will use < 1 GB) |
| Cache | Write back |
| Discard | ✅ checked (if on SSD/NVMe) |

### CPU tab
| Field | Value |
|-------|-------|
| Sockets | 1 |
| Cores | **2** |
| Type | host |

### Memory tab
| Field | Value |
|-------|-------|
| Memory | **2048 MB** (2 GB) |
| Balloon | ✅ (allows dynamic shrink when idle) |

### Network tab
| Field | Value |
|-------|-------|
| Bridge | `vmbr0` (your LAN bridge) |
| Model | VirtIO (paravirtualized) |
| VLAN Tag | set if you use VLANs, otherwise leave blank |

Click **Finish**. Do **not** check "Start after created" yet.

---

## Part 3 — Install Debian 12

1. Select the VM in the left panel → **Start** → **Console** (or press ▶ then open the noVNC console).
2. Boot into the Debian installer. Choose **Install** (text mode — faster than graphical).

### Installer answers (accept defaults unless noted)

| Screen | Answer |
|--------|--------|
| Language | English |
| Location | United States (or yours) |
| Keymap | American English |
| Hostname | `makerspace` |
| Domain | leave blank or your local domain |
| Root password | set a strong one, write it down |
| Full name / Username | `jaret` (or whatever you want) |
| User password | set one |
| Timezone | your timezone |
| Partitioning | **Guided – use entire disk** → all files in one partition → **Finish → Yes** |
| Mirror | pick a nearby Debian mirror |
| Popularity contest | No |
| **Software selection** | **Uncheck everything except `SSH server` and `standard system utilities`** — no desktop needed |
| GRUB | Yes → `/dev/vda` |

Installation takes 3–8 minutes depending on mirror speed. The VM will reboot into Debian.

---

## Part 4 — First Boot Configuration

Log in as **root** via the console, or SSH to the IP shown on login.

### 4a. Find the IP (if you don't know it)
```bash
ip a show ens18   # or ens3, eth0 — whatever shows up
```

### 4b. Update the system
```bash
apt update && apt upgrade -y
```

### 4c. Install the QEMU guest agent (enables Proxmox to see the IP, do clean shutdowns)
```bash
apt install -y qemu-guest-agent
systemctl enable --now qemu-guest-agent
```

### 4d. Set a static IP (recommended for a server)
Edit the network config:
```bash
nano /etc/network/interfaces
```

Replace the `ens18` (or your interface name) block with:
```
auto ens18
iface ens18 inet static
    address 192.168.1.50        # ← pick a free IP on your LAN
    netmask 255.255.255.0
    gateway 192.168.1.1         # ← your router's IP
    dns-nameservers 1.1.1.1 8.8.8.8
```

```bash
systemctl restart networking
```

> After this, reconnect via SSH at the new static IP.

### 4e. (Optional) Allow your user to sudo
```bash
apt install -y sudo
usermod -aG sudo jaret
```

---

## Part 5 — Deploy the Makerspace ERP

### 5a. Copy the app files to the server

From your Windows machine, use SCP (Windows Terminal / WSL / WinSCP):
```powershell
# In Windows Terminal (PowerShell):
scp -r "C:\Users\jaret\AppData\Roaming\Claude\...\outputs\makerspace-erp" root@192.168.1.50:/tmp/
```

Or use **WinSCP** — drag the `makerspace-erp` folder to `/tmp/` on the server.

### 5b. Run the installer
```bash
cd /tmp/makerspace-erp
chmod +x setup.sh
sudo bash setup.sh
```

The script will:
- Install Python 3 and pip
- Create a `makerspace` system user
- Set up a Python venv at `/opt/makerspace-erp/venv`
- Install all Python dependencies
- Create the data directory at `/opt/makerspace-erp/data/`
- Register and start the `makerspace-erp` systemd service

### 5c. Verify it's running
```bash
sudo systemctl status makerspace-erp
# Should show: Active: active (running)

# Tail logs live:
sudo journalctl -u makerspace-erp -f
```

### 5d. Open in your browser
```
http://192.168.1.50:8080
```

---

## Part 6 — Optional but Recommended

### Nginx reverse proxy (access on port 80, cleaner URLs)
```bash
apt install -y nginx

cat > /etc/nginx/sites-available/makerspace-erp <<'EOF'
server {
    listen 80;
    server_name makerspace.local _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

ln -s /etc/nginx/sites-available/makerspace-erp /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
```

Now browse to `http://192.168.1.50` (no port needed).

### Local DNS hostname (access via http://makerspace.local)

On your **router** (or Pi-hole/AdGuard if you run one), add an A record:
```
makerspace.local  →  192.168.1.50
```

Or add it to `C:\Windows\System32\drivers\etc\hosts` on your Windows machine:
```
192.168.1.50    makerspace.local
```

### Automatic backups of the database
```bash
# Add to root's crontab (crontab -e):
0 3 * * * cp /opt/makerspace-erp/data/makerspace.db /opt/makerspace-erp/data/makerspace.db.$(date +\%Y\%m\%d) 2>/dev/null
# Keep last 7 days:
0 4 * * * find /opt/makerspace-erp/data/ -name "*.db.*" -mtime +7 -delete
```

### Proxmox VM snapshot before major changes
In Proxmox UI → VM → **Snapshots** → **Take Snapshot**. Free, instant, and saves you if an update goes sideways.

---

## Quick Reference

| Task | Command |
|------|---------|
| Start ERP | `sudo systemctl start makerspace-erp` |
| Stop ERP | `sudo systemctl stop makerspace-erp` |
| Restart ERP | `sudo systemctl restart makerspace-erp` |
| View logs | `sudo journalctl -u makerspace-erp -f` |
| Database location | `/opt/makerspace-erp/data/makerspace.db` |
| App directory | `/opt/makerspace-erp/` |
| Update app files | Copy new files → `sudo systemctl restart makerspace-erp` |
