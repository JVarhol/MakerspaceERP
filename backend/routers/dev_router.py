"""
Developer Mode API — admin-only endpoints for diagnostics, raw data access,
MQTT publishing, SQL queries, and test data seeding.
"""
from __future__ import annotations
import json, os, re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect as sa_inspect
from typing import Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ── SQL safety ────────────────────────────────────────────────────────────────
_STRIP_COMMENTS = re.compile(r'(--[^\n]*|/\*.*?\*/)', re.DOTALL)
# Keywords that must never appear anywhere in the query
_DANGEROUS_KW = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|ANALYZE)\b',
    re.IGNORECASE,
)

from ..database import get_db, engine
from ..models import AppSetting, User
from ..auth import decode_token, verify_password

router = APIRouter(prefix="/api/dev", tags=["dev"])
_security = HTTPBearer(auto_error=False)


def _require_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(401, "Not authenticated")
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(401, "Invalid token")
    user = db.get(User, int(payload.get("sub", 0)))
    if not user or user.role != "admin":
        raise HTTPException(403, "Admin role required")
    return user


@router.post("/verify-password")
def verify_dev_password(body: dict,
                         db: Session = Depends(get_db),
                         user: User = Depends(_require_admin)):
    if not verify_password(body.get("password", ""), user.password_hash):
        raise HTTPException(401, "Incorrect password")
    return {"ok": True}


@router.get("/db-stats")
def db_stats(db: Session = Depends(get_db), user: User = Depends(_require_admin)):
    tables = sa_inspect(engine).get_table_names()
    counts = {}
    for t in tables:
        try:
            counts[t] = db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        except Exception:
            counts[t] = -1
    db_url = os.getenv("DATABASE_URL", "sqlite:////opt/makerspace-erp/data/makerspace.db")
    db_file = db_url.replace("sqlite:///", "")
    size = Path(db_file).stat().st_size if Path(db_file).exists() else 0
    return {"tables": counts, "size_bytes": size}


@router.post("/query")
def run_query(body: dict, db: Session = Depends(get_db),
              user: User = Depends(_require_admin)):
    sql = body.get("sql", "").strip()
    if not sql:
        raise HTTPException(400, "No SQL provided")
    # Strip comments before validation so they can't hide dangerous keywords
    sql_clean = _STRIP_COMMENTS.sub('', sql).strip()
    tokens = sql_clean.split()
    if not tokens or tokens[0].upper() != "SELECT":
        raise HTTPException(400, "Only SELECT statements are allowed (no CTEs or subqueries that mutate data)")
    if _DANGEROUS_KW.search(sql_clean):
        raise HTTPException(400, "Query contains disallowed keywords")
    if ";" in sql_clean:
        raise HTTPException(400, "Multiple statements are not allowed")
    try:
        result = db.execute(text(sql))
        cols = list(result.keys())
        rows = [list(r) for r in result.fetchmany(200)]
        return {"columns": cols, "rows": rows}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/app-settings")
def get_all_settings(db: Session = Depends(get_db),
                     user: User = Depends(_require_admin)):
    # Keys whose entire value is sensitive — always replaced with ***
    MASK_KEYS = {"_jwt_secret"}
    # Keys whose nested fields are sensitive
    MASK_FIELDS = {"mqtt": ["password"], "ha": ["token"]}
    rows = db.query(AppSetting).order_by(AppSetting.key).all()
    result = {}
    for row in rows:
        try:
            v = json.loads(row.value)
        except Exception:
            v = row.value
        if row.key in MASK_KEYS:
            v = "***"
        elif isinstance(v, dict) and row.key in MASK_FIELDS:
            for f in MASK_FIELDS[row.key]:
                if v.get(f):
                    v[f] = "***"
        result[row.key] = v
    return result


@router.post("/app-settings/{key}")
def set_app_setting(key: str, body: dict, db: Session = Depends(get_db),
                    user: User = Depends(_require_admin)):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    val = json.dumps(body.get("value"))
    if row:
        row.value = val
    else:
        db.add(AppSetting(key=key, value=val))
    db.commit()
    return {"ok": True, "key": key}


@router.post("/mqtt-publish")
def mqtt_publish(body: dict, user: User = Depends(_require_admin)):
    from .. import mqtt_service
    topic   = body.get("topic", "").strip()
    payload = str(body.get("payload", ""))
    retain  = bool(body.get("retain", False))
    if not topic:
        raise HTTPException(400, "Topic required")
    if not mqtt_service._connected or not mqtt_service._client:
        raise HTTPException(400, "MQTT not connected")
    try:
        mqtt_service._client.publish(topic, payload, retain=retain)
        return {"ok": True, "topic": topic, "payload": payload}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/seed")
def seed_data(body: dict, db: Session = Depends(get_db),
              user: User = Depends(_require_admin)):
    import random
    from ..models import Item, Category
    count  = min(int(body.get("count", 10)), 50)
    prefix = body.get("prefix", "TEST_")
    cat = db.query(Category).filter(Category.name == "__dev_test__").first()
    if not cat:
        cat = Category(name="__dev_test__", icon="🧪")
        db.add(cat); db.flush()
    ids = []
    for _ in range(count):
        item = Item(
            name=f"{prefix}Item_{random.randint(1000,9999)}",
            quantity=round(random.uniform(0, 100), 2),
            unit_name=random.choice(["pcs","g","m","ml","kg"]),
            category_id=cat.id,
            min_quantity=round(random.uniform(0, 10), 2),
            price=round(random.uniform(0.10, 50.0), 2),
        )
        db.add(item); db.flush(); ids.append(item.id)
    db.commit()
    return {"created": len(ids), "item_ids": ids}


@router.delete("/seed")
def delete_seed_data(db: Session = Depends(get_db),
                     user: User = Depends(_require_admin)):
    from ..models import Item, Category
    cat = db.query(Category).filter(Category.name == "__dev_test__").first()
    if not cat:
        return {"deleted": 0}
    n = db.query(Item).filter(Item.category_id == cat.id).count()
    db.query(Item).filter(Item.category_id == cat.id).delete()
    db.delete(cat); db.commit()
    return {"deleted": n}
