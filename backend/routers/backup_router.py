"""
Router: Google Drive / rclone Backup
  GET  /api/backup/config   - get config
  POST /api/backup/config   - save config
  GET  /api/backup/status   - get last run status + running flag
  POST /api/backup/run      - trigger manual backup (background)
  POST /api/backup/test     - test rclone connection
"""
from __future__ import annotations
import gzip
import json
import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AppSetting
from ..auth import get_current_user, require_permission

router = APIRouter(prefix="/api/backup", tags=["backup"],
                   dependencies=[Depends(get_current_user)])
_W = Depends(require_permission('settings', 'write'))

# Resolve actual DB file path from DATABASE_URL env
_DB_URL = os.getenv("DATABASE_URL", "sqlite:////opt/makerspace-erp/data/makerspace.db")
DB_PATH = _DB_URL[len("sqlite:///"):] if _DB_URL.startswith("sqlite:///") else _DB_URL

_backup_running = False
_backup_lock    = threading.Lock()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_setting(db: Session, key: str) -> dict:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row or not row.value:
        return {}
    try:
        return json.loads(row.value)
    except Exception:
        return {}


def _set_setting(db: Session, key: str, value: dict) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = json.dumps(value)
    else:
        db.add(AppSetting(key=key, value=json.dumps(value)))
    db.commit()


# ── Core backup logic ──────────────────────────────────────────────────────────

def _do_backup(cfg: dict) -> dict:
    """Run rclone backup. Returns {ok, output, timestamp, error?}."""
    remote     = cfg.get("remote", "gdrive")
    drive_path = cfg.get("drive_path", "makerspace-backups").strip("/")
    retain     = max(1, int(cfg.get("retain", 7)))
    target     = f"{remote}:{drive_path}"
    lines: list[str] = []

    def log(msg: str):
        lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    try:
        # Verify rclone
        r = subprocess.run(["rclone", "version"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise RuntimeError("rclone not found — install with: sudo apt install rclone")
        log("rclone ready")

        # Ensure target folder exists
        subprocess.run(["rclone", "mkdir", target], capture_output=True, text=True, timeout=30)

        # Compress DB to temp file
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"makerspace_{timestamp}.db.gz"
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_path = Path(tmpdir) / backup_name
            log(f"Compressing {DB_PATH} ...")
            with open(DB_PATH, "rb") as fin, gzip.open(backup_path, "wb") as fout:
                shutil.copyfileobj(fin, fout)
            size_kb = backup_path.stat().st_size // 1024
            log(f"Compressed → {backup_name} ({size_kb} KB)")

            # Upload
            log(f"Uploading to {target}/ ...")
            r = subprocess.run(
                ["rclone", "copy", str(backup_path), f"{target}/"],
                capture_output=True, text=True, timeout=180
            )
            if r.returncode != 0:
                raise RuntimeError(f"Upload failed: {(r.stderr or r.stdout).strip()}")
            log("✅ Upload complete")

        # Enforce retention
        log(f"Enforcing retention (keep {retain}) ...")
        r = subprocess.run(
            ["rclone", "lsf", target, "--include", "makerspace_*.db.gz"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0:
            files       = sorted(f.strip() for f in r.stdout.splitlines() if f.strip())
            to_delete   = files[:max(0, len(files) - retain)]
            for fname in to_delete:
                rd = subprocess.run(["rclone", "delete", f"{target}/{fname}"],
                                    capture_output=True, text=True, timeout=30)
                log(f"Deleted old backup: {fname}" if rd.returncode == 0
                    else f"Warning: could not delete {fname}")
            if not to_delete:
                log(f"Retention OK ({len(files)}/{retain} slots used)")

        return {"ok": True, "output": "\n".join(lines), "timestamp": datetime.now().isoformat()}

    except Exception as e:
        log(f"❌ ERROR: {e}")
        return {"ok": False, "output": "\n".join(lines),
                "timestamp": datetime.now().isoformat(), "error": str(e)}


def _backup_thread(cfg: dict):
    """Background thread: run backup, persist status."""
    global _backup_running
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        result = _do_backup(cfg)
        result["running"] = False
        _set_setting(db, "backup_status", result)
    except Exception as e:
        try:
            _set_setting(db, "backup_status", {
                "ok": False, "error": str(e), "running": False,
                "output": f"Fatal error: {e}",
                "timestamp": datetime.now().isoformat()
            })
        except Exception:
            pass
    finally:
        _backup_running = False
        db.close()


# ── Scheduler (called from main.py lifespan) ───────────────────────────────────

def start_scheduler():
    """Launch a background thread that triggers scheduled backups."""
    import time

    def _loop():
        while True:
            time.sleep(3600)  # check every hour
            try:
                from ..database import SessionLocal
                db = SessionLocal()
                try:
                    cfg = _get_setting(db, "backup")
                    if not cfg.get("enabled"):
                        continue
                    interval_days = int(cfg.get("interval_days", 1))
                    status        = _get_setting(db, "backup_status")
                    last_ts       = status.get("timestamp")
                    if last_ts:
                        last_dt = datetime.fromisoformat(last_ts)
                        elapsed_hours = (datetime.now() - last_dt).total_seconds() / 3600
                        if elapsed_hours < interval_days * 24:
                            continue
                    # Due — trigger backup
                    global _backup_running
                    if not _backup_running:
                        _backup_running = True
                        _set_setting(db, "backup_status", {
                            "running": True,
                            "timestamp": datetime.now().isoformat(),
                            "output": "Scheduled backup starting..."
                        })
                        t = threading.Thread(target=_backup_thread, args=(cfg,), daemon=True)
                        t.start()
                finally:
                    db.close()
            except Exception:
                pass

    threading.Thread(target=_loop, daemon=True).start()


# ── API Routes ─────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db)):
    return {"config": _get_setting(db, "backup")}


@router.post("/config")
def save_config(body: dict, _w=_W, db: Session = Depends(get_db)):
    _set_setting(db, "backup", body)
    return {"ok": True}


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    status = _get_setting(db, "backup_status")
    status["running"] = _backup_running
    return status


@router.post("/run")
def trigger_backup(_w=_W, db: Session = Depends(get_db)):
    global _backup_running
    if _backup_running:
        raise HTTPException(409, "Backup already in progress")
    cfg = _get_setting(db, "backup")
    if not cfg.get("remote") or not cfg.get("drive_path"):
        raise HTTPException(400, "Backup not configured — save settings first")
    _backup_running = True
    _set_setting(db, "backup_status", {
        "running": True,
        "timestamp": datetime.now().isoformat(),
        "output": "Backup starting..."
    })
    threading.Thread(target=_backup_thread, args=(cfg,), daemon=True).start()
    return {"ok": True, "message": "Backup started"}


@router.post("/test")
def test_connection(db: Session = Depends(get_db)):
    cfg    = _get_setting(db, "backup")
    remote = cfg.get("remote", "").strip()
    path   = cfg.get("drive_path", "").strip()
    if not remote:
        return {"ok": False, "message": "No remote name configured"}

    r = subprocess.run(["rclone", "version"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return {"ok": False, "message": "rclone not installed. Run: sudo apt install rclone"}

    remotes_r = subprocess.run(["rclone", "listremotes"], capture_output=True, text=True, timeout=10)
    if f"{remote}:" not in (remotes_r.stdout or ""):
        return {"ok": False,
                "message": f"Remote '{remote}' not found. Run 'rclone config' on the server to add it."}

    target = f"{remote}:{path}" if path else f"{remote}:"
    r2 = subprocess.run(["rclone", "lsd", target], capture_output=True, text=True, timeout=30)
    if r2.returncode != 0:
        # Try mkdir
        r3 = subprocess.run(["rclone", "mkdir", f"{remote}:{path}"],
                            capture_output=True, text=True, timeout=30)
        if r3.returncode != 0:
            return {"ok": False, "message": f"Cannot access {target}: {(r2.stderr or r2.stdout).strip()}"}
        return {"ok": True, "message": f"✅ Connected — folder '{path}' created on {remote}"}

    return {"ok": True, "message": f"✅ Connected to {target}"}
