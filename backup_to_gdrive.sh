#!/bin/bash
# =============================================================================
# Makerspace ERP — Google Drive Backup Script
# Uses rclone. Configure GDRIVE_PATH below after running rclone setup.
# =============================================================================

# ── Configuration ─────────────────────────────────────────────────────────────
DB_PATH="/opt/makerspace-erp/data/makerspace.db"
RCLONE_REMOTE="gdrive"                         # name you give rclone remote
GDRIVE_PATH="gdrive:makerspace-backups"        # change folder path as needed
RETAIN=7                                       # number of backups to keep
LOCAL_TMP="/tmp/makerspace-backups"
LOG_FILE="/var/log/makerspace-backup.log"

# ── Helpers ───────────────────────────────────────────────────────────────────
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# ── Check dependencies ────────────────────────────────────────────────────────
if ! command -v rclone &>/dev/null; then
  log "ERROR: rclone not found. Install with: sudo apt install rclone"
  exit 1
fi
if ! rclone listremotes | grep -q "^${RCLONE_REMOTE}:"; then
  log "ERROR: rclone remote '${RCLONE_REMOTE}' not configured. Run: rclone config"
  exit 1
fi

# ── Create backup ─────────────────────────────────────────────────────────────
mkdir -p "$LOCAL_TMP"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="${LOCAL_TMP}/makerspace_${TIMESTAMP}.db.gz"

log "Starting backup..."

# Copy DB to temp (avoids locking issues on live file)
cp "$DB_PATH" "${LOCAL_TMP}/makerspace_tmp.db" || { log "ERROR: Could not read database"; exit 1; }
gzip -c "${LOCAL_TMP}/makerspace_tmp.db" > "$BACKUP_FILE"
rm -f "${LOCAL_TMP}/makerspace_tmp.db"

SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
log "Created backup: $(basename $BACKUP_FILE) ($SIZE)"

# ── Upload to Google Drive ────────────────────────────────────────────────────
rclone copy "$BACKUP_FILE" "$GDRIVE_PATH/" --log-file="$LOG_FILE" --log-level INFO
if [ $? -ne 0 ]; then
  log "ERROR: Upload to Google Drive failed"
  rm -f "$BACKUP_FILE"
  exit 1
fi
log "Uploaded to ${GDRIVE_PATH}/"
rm -f "$BACKUP_FILE"

# ── Enforce retention (keep newest N copies) ──────────────────────────────────
log "Checking retention (keep ${RETAIN} copies)..."

# List all backups on Drive, sorted oldest first
REMOTE_FILES=$(rclone lsf "$GDRIVE_PATH/" --include "makerspace_*.db.gz" | sort)
TOTAL=$(echo "$REMOTE_FILES" | grep -c .)
DELETE_COUNT=$(( TOTAL - RETAIN ))

if [ "$DELETE_COUNT" -gt 0 ]; then
  TO_DELETE=$(echo "$REMOTE_FILES" | head -n "$DELETE_COUNT")
  while IFS= read -r fname; do
    [ -z "$fname" ] && continue
    rclone delete "${GDRIVE_PATH}/${fname}" --log-file="$LOG_FILE" --log-level INFO
    log "Deleted old backup: $fname"
  done <<< "$TO_DELETE"
else
  log "No old backups to remove (${TOTAL}/${RETAIN} slots used)"
fi

log "Backup complete."
