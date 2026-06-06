#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Makerspace ERP – bare-metal Linux installer
# Tested on Debian 11/12, Ubuntu 22.04/24.04
# Run as root:  sudo bash setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/opt/makerspace-erp"
DATA_DIR="$APP_DIR/data"
SERVICE_USER="makerspace"
PORT=8080

echo "=== Makerspace ERP Installer ==="

# 1. System deps
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv curl

# 2. Create dedicated user
if ! id "$SERVICE_USER" &>/dev/null; then
  useradd --system --shell /usr/sbin/nologin --home "$APP_DIR" "$SERVICE_USER"
  echo "✓ Created system user: $SERVICE_USER"
fi

# 3. Copy application files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
  mkdir -p "$APP_DIR"
  cp -r "$SCRIPT_DIR/backend"  "$APP_DIR/"
  cp -r "$SCRIPT_DIR/frontend" "$APP_DIR/"
  echo "✓ Copied application files to $APP_DIR"
else
  echo "✓ Already running from $APP_DIR"
fi

# 4. Create data directory
mkdir -p "$DATA_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"
echo "✓ Data directory: $DATA_DIR"

# 5. Python virtual environment
if [ ! -d "$APP_DIR/venv" ]; then
  python3 -m venv "$APP_DIR/venv"
  echo "✓ Created Python venv"
fi

"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/backend/requirements.txt"
echo "✓ Python dependencies installed"

chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# 6. Install and enable systemd service
cp "$SCRIPT_DIR/makerspace-erp.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable makerspace-erp
systemctl restart makerspace-erp
echo "✓ systemd service installed and started"

# 7. Done
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Makerspace ERP is running on port $PORT"
echo ""
echo "  Open in browser:  http://$(hostname -I | awk '{print $1}'):$PORT"
echo "  Service status:   sudo systemctl status makerspace-erp"
echo "  View logs:        sudo journalctl -u makerspace-erp -f"
echo "  Database:         $DATA_DIR/makerspace.db"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
