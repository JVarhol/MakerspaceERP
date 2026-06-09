# Makerspace ERP

A self-hosted inventory and asset management system for home makerspaces. Single-file frontend, FastAPI + SQLite backend, runs as a systemd service.

**Current version: ALPHA v1.4.64**

Come chat, see new development and report bugs: https://discord.gg/MSwYkzRKU

*Not compatible with bcrypt 4.0*
You may get password not valid prompt for the default user name and pass use:
```bash
sudo /opt/makerspace-erp/venv/bin/pip install "bcrypt==3.2.2"
sudo systemctl restart makerspace-erp 
```

---

## Features

### Inventory
- Items with full CRUD, package behavior (bulk/spool), category custom fields, CSV import/export
- **Item Merge** — combine duplicate items, summing quantities and re-parenting all transactions, locations, supplier links, PO lines, kit items, and assembly components. Supports bulk merge of 3+ items and per-location quantity routing control
- **Spool tracking** — individual spool management with sealed/open state, remaining quantity per spool, and scale weighing support
- **Scale / Weigh QTY** — use a connected scale to count bulk items by weight or measure remaining filament on open spools. Available in item detail, item form, and add-item screen
- Low stock alerts, stock take, barcode scanning (camera + photo upload + USB scanner)

### Locations
- Hierarchical storage with visual Shelf Map, drag-and-drop layout
- Custom location types — add your own types beyond the built-in set (bin, shelf, drawer, etc.)

### Kits & Assemblies
- Stock replenishment bundles with **CSV import** — fuzzy-matches CSV rows to existing inventory items, lets you search or create new items for unmatched rows
- BOM management with build button that deducts components

### Assets
- Check-out/return, status tracking, photos, asset tags

### Purchase Orders
- Multi-line POs with per-line receiving

### Projects
- BOM management, cost estimator (materials + labor + markup), invoice generator

### Integrations
- **MQTT** — bidirectional Home Assistant auto-discovery, TLS support, scale entity
- **HA REST API** — push item/asset states to Home Assistant on update

### Branding
- Custom logo image (replaces sidebar title) and favicon, uploaded directly or set by URL — persisted server-side

### Users & Auth
- JWT auth, per-section permissions, bcrypt passwords, login rate limiting

### Reports & UI
- Inventory snapshots, usage trends, printable labels
- Global Search (Ctrl+K) across items, assets, projects, locations
- Dashboard with customizable widgets

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
git clone https://github.com/YOUR_USERNAME/makerspace-erp.git
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

### 3. Create data directories

```bash
sudo mkdir -p /opt/makerspace-erp/data/uploads/branding
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

```bash
sudo cp -r backend frontend /opt/makerspace-erp/
sudo systemctl restart makerspace-erp
```

### Database migrations

Check `migrations/` for any new SQL files since your last update and run the ones you haven't applied:

```bash
sqlite3 /opt/makerspace-erp/data/makerspace.db < migrations/migrate_vXXX.sql
```

#### v1.4.x migration (run once if upgrading from v1.3.x)

```bash
sqlite3 /opt/makerspace-erp/data/makerspace.db "ALTER TABLE items ADD COLUMN spool_empty_weight REAL;"
sqlite3 /opt/makerspace-erp/data/makerspace.db "ALTER TABLE items ADD COLUMN unit_weight REAL;"
```

Also create the branding uploads directory if it doesn't exist:

```bash
sudo mkdir -p /opt/makerspace-erp/data/uploads/branding
sudo chown -R makerspace:makerspace /opt/makerspace-erp/data/uploads/
```

---

## Configuration

All settings are stored in the database under **Settings** in the UI. No config files to edit.

| Setting | Location in UI |
|---|---|
| MQTT broker | Settings → MQTT |
| Home Assistant URL + token | Settings → Home Assistant |
| Company info (for invoices) | Settings → Company |
| Custom logo + favicon | Settings → Branding |
| Theme / accent color | Settings → Theme |
| User accounts | Users page (admin only) |

### Environment variables

The service file sets these — edit `/etc/systemd/system/makerspace-erp.service` to override:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:////opt/makerspace-erp/data/makerspace.db` | SQLAlchemy DB URL |
| `UPLOADS_DIR` | `/opt/makerspace-erp/data/uploads` | Where uploaded images are stored |

After editing the service file:

```bash
sudo systemctl daemon-reload
sudo systemctl restart makerspace-erp
```

---

## Camera / Barcode Scanning

Live camera scanning requires the app to be served over **HTTPS** (browsers block camera access on plain HTTP for non-localhost addresses). If you're on HTTP, use the **📁 Scan from Photo** button instead — it decodes barcodes from an uploaded image without needing camera permission.

To enable HTTPS, put an Nginx reverse proxy with a self-signed cert in front of the app.

---

## Home Assistant Integration

### REST API (built-in)

Configure under **Settings → Home Assistant**:
- **URL** — your HA instance URL (e.g. `http://192.168.0.X:8123`)
- **Long-lived access token** — generate one in HA under your profile

Items and assets with **HA Exposed** enabled are pushed as sensor entities on every update.

### MQTT (built-in)

Configure under **Settings → MQTT**:
- Supports TLS and password auth
- Auto-discovery for Home Assistant
- Bidirectional — HA can update quantities via MQTT
- Scale entity mode — ERP creates a writable HA number entity for scale readings

### Custom HA Integration (advanced)

A custom component scaffold is in `ha_integration/`. Work-in-progress for a full native integration.

---

## File Structure

```
makerspace-erp/
├── backend/                  # FastAPI application
│   ├── main.py               # App entry point, serves frontend
│   ├── models.py             # SQLAlchemy ORM models
│   ├── schemas.py            # Pydantic schemas
│   ├── auth.py               # JWT + bcrypt auth helpers
│   ├── database.py           # SQLAlchemy engine / session
│   ├── mqtt_service.py       # MQTT client + scale globals
│   ├── ha_service.py         # HA REST push service
│   ├── requirements.txt
│   └── routers/
│       ├── items.py          # Items + merge endpoint
│       ├── locations.py
│       ├── categories.py
│       ├── transactions.py
│       ├── kits.py
│       ├── barcode.py
│       ├── category_fields.py
│       ├── settings.py       # Settings + asset upload endpoint
│       ├── scale_router.py
│       ├── auth_router.py
│       └── users_router.py
├── frontend/
│   └── index.html            # Single-file SPA (~370 KB)
├── migrations/               # SQL upgrade scripts for existing installs
├── ha_integration/           # Home Assistant custom component (WIP)
├── data/
│   ├── uploads/              # Uploaded images (gitignored except .gitkeep)
│   │   └── branding/         # Logo and favicon uploads
├── makerspace-erp.service    # systemd unit file
├── setup.sh                  # Automated installer
├── CHANGELOG.md              # Version history
└── SERVER_SETUP.md           # Proxmox VM setup guide
```

---

## Backup

The entire application state is in one file:

```bash
cp /opt/makerspace-erp/data/makerspace.db ~/makerspace-backup-$(date +%Y%m%d).db
```

To also back up uploaded images (logos, favicons, item photos):

```bash
tar -czf ~/makerspace-backup-$(date +%Y%m%d).tar.gz \
  /opt/makerspace-erp/data/makerspace.db \
  /opt/makerspace-erp/data/uploads/
```

---

## Troubleshooting

**Service won't start**
```bash
sudo journalctl -u makerspace-erp -n 50
```

**Port 8080 already in use**  
Edit `/etc/systemd/system/makerspace-erp.service`, change `--port 8080` to another port, then:
```bash
sudo systemctl daemon-reload && sudo systemctl restart makerspace-erp
```

**Forgot admin password**  
Reset via the Users admin page, or directly:
```bash
sqlite3 /opt/makerspace-erp/data/makerspace.db \
  "UPDATE users SET force_pw_change=1 WHERE username='admin';"
```

**Reset to factory defaults**
```bash
sudo systemctl stop makerspace-erp
rm /opt/makerspace-erp/data/makerspace.db
sudo systemctl start makerspace-erp
```
The database is recreated on next startup with the default admin account.

---

## License

MIT
