# Makerspace ERP

A self-hosted inventory and asset management system for home makerspaces. Single-file frontend, FastAPI + SQLite backend, runs as a systemd service.

**Current version: v1.3.83**

---

## Features

- **Inventory** — Items with full CRUD, package behavior (bulk/spool), category custom fields, CSV import/export
- **Locations** — Hierarchical storage with visual Shelf Map, drag-and-drop layout
- **Assets** — Check-out/return, status tracking, photos, asset tags
- **Purchase Orders** — Multi-line POs with per-line receiving
- **Kits & Assemblies** — Stock replenishment bundles, BOM with build button
- **Projects** — BOM management, cost estimator, invoice generator
- **MQTT** — Bidirectional Home Assistant auto-discovery, TLS support
- **HA REST API** — Push item/asset states to Home Assistant on update
- **Users & Auth** — JWT auth, per-section permissions, bcrypt passwords
- **Reports** — Inventory snapshots, usage trends, printable labels
- **Global Search** — Ctrl+K overlay across items, assets, projects, locations

---

## Requirements

- Linux (Debian 11/12 or Ubuntu 22.04/24.04 recommended)
- Python 3.10+
- ~100 MB disk space (plus your data)

For Proxmox VM setup, see [SERVER_SETUP.md](SERVER_SETUP.md).

---

## Quick Install (automated)

Run as root on a fresh Debian/Ubuntu machine:

```bash
git clone https://github.com/JVarhol/MakerspaceERP.git
cd makerspace-erp
sudo bash setup.sh
```

The installer will:
1. Install Python 3 and system dependencies
2. Create a dedicated `makerspace` system user
3. Copy files to `/opt/makerspace-erp/`
4. Create a Python virtual environment and install packages
5. Install and start the systemd service on port **8080**

Open `http://<your-server-ip>:8080` in a browser.  
Default login: **admin / admin123** (you will be forced to change this on first login).

---

## Manual Install

### 1. Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
```

### 2. Copy files to server

```bash
sudo mkdir -p /opt/makerspace-erp
sudo cp -r backend frontend migrations /opt/makerspace-erp/
sudo cp makerspace-erp.service /etc/systemd/system/
```

### 3. Create data directory

```bash
sudo mkdir -p /opt/makerspace-erp/data/uploads
```

### 4. Create a dedicated system user

```bash
sudo useradd --system --shell /usr/sbin/nologin --home /opt/makerspace-erp makerspace
sudo chown -R makerspace:makerspace /opt/makerspace-erp
```

### 5. Set up Python virtual environment

```bash
cd /opt/makerspace-erp
sudo -u makerspace python3 -m venv venv
sudo -u makerspace venv/bin/pip install --upgrade pip
sudo -u makerspace venv/bin/pip install -r backend/requirements.txt
```

### 6. Start the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable makerspace-erp
sudo systemctl start makerspace-erp
```

Check it's running:

```bash
sudo systemctl status makerspace-erp
sudo journalctl -u makerspace-erp -f
```

---

## Updating an Existing Install

### Pull new code

```bash
cd /path/to/your/clone
git pull
sudo cp -r backend frontend /opt/makerspace-erp/
sudo systemctl restart makerspace-erp
```

### Database migrations

After updating, check `migrations/` for any new SQL files and run the ones you haven't applied:

```bash
sqlite3 /opt/makerspace-erp/data/makerspace.db < migrations/migrate_vXXX.sql
```

Or apply inline with:

```bash
sqlite3 /opt/makerspace-erp/data/makerspace.db "ALTER TABLE ..."
```

**v1.3.83 migration** (user theme preferences — run once if upgrading):

```bash
sqlite3 /opt/makerspace-erp/data/makerspace.db "ALTER TABLE users ADD COLUMN preferences TEXT;"
```

---

## Configuration

All settings are stored in the database under **Settings** in the UI. No config files to edit.

| Setting | Location in UI |
|---|---|
| MQTT broker | Settings → MQTT |
| Home Assistant URL + token | Settings → Home Assistant |
| Company info (for invoices) | Settings → Company |
| Theme / accent color | Settings → Theme |
| User accounts | Users page (admin only) |

### Environment variables

The service file sets these — edit `/etc/systemd/system/makerspace-erp.service` to override:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:////opt/makerspace-erp/data/makerspace.db` | SQLAlchemy DB URL |
| `UPLOADS_DIR` | `/opt/makerspace-erp/data/uploads` | Where item/asset photos are stored |

After editing the service file:

```bash
sudo systemctl daemon-reload
sudo systemctl restart makerspace-erp
```

---

## Home Assistant Integration

### REST API (built-in)

Configure under **Settings → Home Assistant**:
- **URL** — your HA instance URL (e.g. `http://192.168.0.X:8123`)
- **Long-lived access token** — generate one in HA under your profile

Items and assets with **HA Exposed** enabled will be pushed as sensor entities whenever they are updated.

### MQTT (built-in)

Configure under **Settings → MQTT**:
- Supports TLS and password auth
- Auto-discovery for Home Assistant
- Bidirectional — HA can update quantities via MQTT

### Custom HA Integration (advanced)

A custom component scaffold is in `ha_integration/`. This is a work-in-progress for a full native integration that appears in the HA Integrations page.

---


## License

MIT
