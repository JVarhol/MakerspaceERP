"""
Home Assistant REST API Service
Pushes item quantities and asset statuses directly to HA via its REST API.
Uses a long-lived access token — no broker required.

HA state entities created:
  sensor.makerspace_item_{id}   → state = quantity, attrs = {name, unit, category, low_stock}
  sensor.makerspace_asset_{id}  → state = status,   attrs = {name, asset_tag, location, checked_out_by}

HA can write back to the ERP directly via its REST API:
  PATCH http://{erp_host}:8080/api/items/{id}   {"quantity": x}
  POST  http://{erp_host}:8080/api/assets/{id}/checkout  or /return
"""
from __future__ import annotations
import json
import logging
import threading
from typing import Optional

import httpx

log = logging.getLogger("ha_service")

_config: dict = {}
_lock = threading.Lock()


# ── Public API ────────────────────────────────────────────────────────────────

def configure(cfg: dict):
    global _config
    with _lock:
        _config = cfg


def get_status() -> dict:
    return {
        "configured": bool(_config.get("url") and _config.get("token")),
        "url": _config.get("url", ""),
    }


def test_connection(cfg: dict) -> dict:
    """Test HA connection by hitting /api/ endpoint."""
    try:
        r = httpx.get(
            cfg["url"].rstrip("/") + "/api/",
            headers=_headers(cfg),
            timeout=5,
            verify=cfg.get("verify_ssl", True),
        )
        if r.status_code == 200:
            return {"ok": True, "message": f"Connected — HA version: {r.json().get('version','?')}"}
        return {"ok": False, "message": f"HTTP {r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


def push_item_state(item_id: int, name: str, quantity: float, unit: str,
                    category: str = "", low_stock: bool = False):
    """Push item quantity as a HA sensor state (non-blocking)."""
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(
        target=_set_state,
        args=(cfg, f"sensor.makerspace_item_{item_id}", str(quantity), {
            "friendly_name": f"Makerspace: {name}",
            "unit_of_measurement": unit,
            "category": category,
            "low_stock": low_stock,
            "item_id": item_id,
            "icon": "mdi:package-variant",
        }),
        daemon=True,
    ).start()


def push_asset_state(asset_id: int, name: str, status: str,
                     asset_tag: str = "", location: str = "", checked_out_by: str = ""):
    """Push asset status as a HA sensor state (non-blocking)."""
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(
        target=_set_state,
        args=(cfg, f"sensor.makerspace_asset_{asset_id}", status, {
            "friendly_name": f"Makerspace Asset: {name}",
            "asset_tag": asset_tag,
            "location": location,
            "checked_out_by": checked_out_by,
            "asset_id": asset_id,
            "icon": "mdi:tools",
        }),
        daemon=True,
    ).start()


def push_all_items(items) -> int:
    """Push state for all ha_exposed items. Returns count pushed."""
    cfg = _get_cfg()
    if not cfg:
        return 0
    count = 0
    for item in items:
        cat = item.category.name if item.category else ""
        low = item.quantity <= item.min_quantity and item.min_quantity > 0
        ok = _set_state(cfg, f"sensor.makerspace_item_{item.id}", str(item.quantity), {
            "friendly_name": f"Makerspace: {item.name}",
            "unit_of_measurement": item.unit_name,
            "category": cat,
            "low_stock": low,
            "item_id": item.id,
            "icon": "mdi:package-variant",
        })
        if ok:
            count += 1
    return count


def push_all_assets(assets) -> int:
    """Push state for all ha_exposed assets. Returns count pushed."""
    cfg = _get_cfg()
    if not cfg:
        return 0
    count = 0
    for asset in assets:
        co = next((c for c in asset.checkouts if c.returned_at is None), None)
        loc = asset.location.name if asset.location else ""
        ok = _set_state(cfg, f"sensor.makerspace_asset_{asset.id}", asset.status, {
            "friendly_name": f"Makerspace Asset: {asset.name}",
            "asset_tag": asset.asset_tag or "",
            "location": loc,
            "checked_out_by": co.checked_out_by if co else "",
            "asset_id": asset.id,
            "icon": "mdi:tools",
        })
        if ok:
            count += 1
    return count






# ── Dashboard Widget HA pushes ────────────────────────────────────────────────

def push_dashboard_widget(widget_id: str, label: str, value, unit: str = ""):
    cfg = _get_cfg()
    if not cfg:
        return
    attrs = {"friendly_name": f"Makerspace: {label}", "widget_id": widget_id, "icon": "mdi:view-dashboard"}
    if unit:
        attrs["unit_of_measurement"] = unit
    threading.Thread(target=_set_state,
        args=(cfg, f"sensor.makerspace_dash_{widget_id}", str(value), attrs),
        daemon=True).start()


def push_all_dashboard_widgets(db) -> int:
    """Push all HA-enabled dashboard widgets. Returns count."""
    cfg = _get_cfg()
    if not cfg:
        return 0
    try:
        from .models import AppSetting
        import json as _j
        row = db.query(AppSetting).filter(AppSetting.key == "dashboard_widget_integration").first()
        if not row or not row.value:
            return 0
        cfg2 = _j.loads(row.value)
        ha_cfg = cfg2.get("ha", {})
        if not any(ha_cfg.values()):
            return 0
        from . import mqtt_service
        stats = mqtt_service._gather_dashboard_stats(db)
        count = 0
        for wid, (value, label, unit) in stats.items():
            if ha_cfg.get(wid):
                push_dashboard_widget(wid, label, value, unit)
                count += 1
        return count
    except Exception as e:
        log.warning(f"HA dashboard widget bulk push failed: {e}")
        return 0

# ── Module HA pushes ──────────────────────────────────────────────────────────

def _is_module_ha_enabled(db, module: str) -> bool:
    try:
        from .models import AppSetting
        import json as _json
        row = db.query(AppSetting).filter(AppSetting.key == "integration_modules").first()
        if not row or not row.value:
            return False
        cfg = _json.loads(row.value)
        return bool(cfg.get("ha", {}).get(module, False))
    except Exception:
        return False


def push_project_state(project_id: int, name: str, status: str, item_count: int = 0):
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(target=_set_state, args=(cfg, f"sensor.makerspace_project_{project_id}", status, {
        "friendly_name": f"Makerspace Project: {name}",
        "item_count": item_count, "project_id": project_id, "icon": "mdi:hammer-screwdriver",
    }), daemon=True).start()


def push_location_state(location_id: int, name: str, item_count: int, location_type: str = ""):
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(target=_set_state, args=(cfg, f"sensor.makerspace_location_{location_id}", str(item_count), {
        "friendly_name": f"Makerspace Location: {name}",
        "unit_of_measurement": "items", "location_type": location_type,
        "location_id": location_id, "icon": "mdi:map-marker",
    }), daemon=True).start()


def push_category_state(category_id: int, name: str, item_count: int):
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(target=_set_state, args=(cfg, f"sensor.makerspace_category_{category_id}", str(item_count), {
        "friendly_name": f"Makerspace Category: {name}",
        "unit_of_measurement": "items", "category_id": category_id, "icon": "mdi:tag",
    }), daemon=True).start()


def push_kit_state(kit_id: int, name: str, buildable: int, component_count: int = 0):
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(target=_set_state, args=(cfg, f"sensor.makerspace_kit_{kit_id}", str(buildable), {
        "friendly_name": f"Makerspace Kit: {name}",
        "unit_of_measurement": "buildable", "component_count": component_count,
        "kit_id": kit_id, "icon": "mdi:toolbox",
    }), daemon=True).start()


def push_po_state(po_id: int, status: str, po_number: str = "", supplier: str = "", line_count: int = 0):
    cfg = _get_cfg()
    if not cfg:
        return
    threading.Thread(target=_set_state, args=(cfg, f"sensor.makerspace_po_{po_id}", status or "pending", {
        "friendly_name": f"Makerspace PO: {po_number or po_id}",
        "po_number": po_number, "supplier": supplier,
        "line_count": line_count, "po_id": po_id, "icon": "mdi:shopping",
    }), daemon=True).start()


def push_all_modules(items_db_session) -> dict:
    """Bulk-push all HA-enabled modules. Returns counts."""
    db = items_db_session
    try:
        from .models import AppSetting
        import json as _json
        row = db.query(AppSetting).filter(AppSetting.key == "integration_modules").first()
        if not row or not row.value:
            return {}
        cfg = _json.loads(row.value)
        ha_cfg = cfg.get("ha", {})
        counts = {}
        if ha_cfg.get("locations"):
            counts["locations"] = _ha_push_all_locations(db)
        if ha_cfg.get("categories"):
            counts["categories"] = _ha_push_all_categories(db)
        if ha_cfg.get("kits"):
            counts["kits"] = _ha_push_all_kits(db)
        if ha_cfg.get("projects"):
            counts["projects"] = _ha_push_all_projects(db)
        if ha_cfg.get("purchase_orders"):
            counts["purchase_orders"] = _ha_push_all_pos(db)
        return counts
    except Exception as e:
        log.warning(f"HA bulk module push failed: {e}")
        return {}


def _ha_push_all_locations(db) -> int:
    from .models import Location, ItemLocation
    from sqlalchemy import func
    count = 0
    for loc in db.query(Location).all():
        ic = db.query(func.count(ItemLocation.id)).filter(ItemLocation.location_id == loc.id).scalar() or 0
        push_location_state(loc.id, loc.name, ic, loc.location_type or "")
        count += 1
    return count


def _ha_push_all_categories(db) -> int:
    from .models import Category, Item
    from sqlalchemy import func
    count = 0
    for cat in db.query(Category).all():
        ic = db.query(func.count(Item.id)).filter(Item.category_id == cat.id).scalar() or 0
        push_category_state(cat.id, cat.name, ic)
        count += 1
    return count


def _ha_push_all_kits(db) -> int:
    from .models import Kit, Item as _Item
    count = 0
    for kit in db.query(Kit).all():
        min_b = None
        ok = True
        for ki in kit.kit_items:
            item = db.get(_Item, ki.item_id)
            if not item or ki.quantity <= 0:
                ok = False; break
            b = int(item.quantity // ki.quantity)
            if min_b is None or b < min_b:
                min_b = b
        buildable = (min_b or 0) if ok else 0
        push_kit_state(kit.id, kit.name, buildable, len(kit.kit_items))
        count += 1
    return count


def _ha_push_all_projects(db) -> int:
    from .models import Project
    count = 0
    for p in db.query(Project).all():
        push_project_state(p.id, p.name, p.status, len(p.items))
        count += 1
    return count


def _ha_push_all_pos(db) -> int:
    from .models import PurchaseOrder
    count = 0
    for po in db.query(PurchaseOrder).all():
        push_po_state(po.id, po.status or "pending", po.po_number or "",
                      po.supplier_name or "", len(po.line_items))
        count += 1
    return count

# ── Internal ──────────────────────────────────────────────────────────────────

def _get_cfg() -> Optional[dict]:
    with _lock:
        cfg = dict(_config)
    if not cfg.get("url") or not cfg.get("token"):
        return None
    return cfg


def _headers(cfg: dict) -> dict:
    return {
        "Authorization": f"Bearer {cfg['token']}",
        "Content-Type": "application/json",
    }


def _set_state(cfg: dict, entity_id: str, state: str, attributes: dict) -> bool:
    try:
        url = cfg["url"].rstrip("/") + f"/api/states/{entity_id}"
        r = httpx.post(
            url,
            headers=_headers(cfg),
            json={"state": state, "attributes": attributes},
            timeout=5,
            verify=cfg.get("verify_ssl", True),
        )
        if r.status_code in (200, 201):
            return True
        log.warning(f"HA push failed for {entity_id}: {r.status_code} {r.text[:100]}")
        return False
    except Exception as e:
        log.warning(f"HA push error for {entity_id}: {e}")
        return False
