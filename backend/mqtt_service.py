"""
MQTT Service — runs paho-mqtt in a background thread.

Topics (base = cfg['base_topic'], default 'makerspace'):
  Publish:  {base}/items/{id}/state          → quantity (float as string)
            {base}/items/{id}/attributes      → JSON {name, unit, category}
  Subscribe:{base}/items/{id}/set            → set quantity
  Discovery:homeassistant/number/makerspace_{id}/config
"""
from __future__ import annotations
import json
import logging
import threading
from typing import Optional

log = logging.getLogger("mqtt_service")

_client = None
_config: dict = {}
_connected = False
_status_msg = "Not configured"
_lock = threading.Lock()

# Scale
_scale_reading: Optional[float] = None
_scale_topic: str = ""        # topic being listened to (either mode)
_scale_mode: str = ""         # 'subscribe' | 'ha_entity'
_scale_unit: str = "g"


# ── Public API ────────────────────────────────────────────────────────────────

def get_status() -> dict:
    return {
        "connected": _connected,
        "message":   _status_msg,
        "broker":    _config.get("broker", ""),
        "port":      _config.get("port", 1883),
        "base_topic":_config.get("base_topic", "makerspace"),
    }


def get_scale_reading() -> Optional[float]:
    """Return the most recent weight reading from the configured scale topic."""
    return _scale_reading


def configure_scale(mode: str = "ha_entity", topic: str = "", unit: str = "g") -> None:
    """Subscribe to the appropriate scale topic based on mode.

    mode='subscribe'  — ERP listens to a user-specified topic (scale publishes there).
    mode='ha_entity'  — ERP creates a writable number entity in HA; HA writes to
                        {base}/scale/set, ERP publishes state to {base}/scale/state.
    """
    global _scale_topic, _scale_mode, _scale_unit
    _scale_mode = mode
    _scale_unit = unit
    base = _config.get("base_topic", "makerspace")

    if mode == "ha_entity":
        _scale_topic = f"{base}/scale/set"
    else:  # subscribe
        _scale_topic = topic

    if _connected and _client and _scale_topic:
        try:
            _client.subscribe(_scale_topic)
            log.info(f"Scale subscribed ({mode}): {_scale_topic}")
            if mode == "ha_entity":
                publish_scale_discovery()
        except Exception as e:
            log.warning(f"Scale subscribe failed: {e}")


def publish_scale_discovery(reset: bool = False) -> bool:
    """Publish HA auto-discovery for the scale.

    ha_entity mode  → writable number entity (HA can set the value).
    subscribe mode  → read-only sensor entity (HA mirrors the scale value).

    reset=True: clears the old entity from HA first (empty payload), then
    republishes. Use this when config has changed (e.g. base_topic changed)
    so HA rebuilds the entity cleanly without requiring a reload.
    Returns True on success.
    """
    import time
    if not _connected or not _client:
        return False
    base = _config.get("base_topic", "makerspace")
    unit = _scale_unit or "g"

    if _scale_mode == "ha_entity":
        config = {
            "name":          "Makerspace Scale",
            "unique_id":     "makerspace_scale_weight",
            "state_topic":   f"{base}/scale/state",
            "command_topic": f"{base}/scale/set",
            "unit_of_measurement": unit,
            "min":    0,
            "max":    99999,
            "step":   0.1,
            "mode":   "box",
            "device": {
                "identifiers": ["makerspace_erp"],
                "name":        "Makerspace ERP",
                "model":       "Inventory Manager",
                "manufacturer":"HomeERP",
            },
        }
        discovery_topic = "homeassistant/number/makerspace_scale/config"
    else:
        # subscribe mode: sensor that mirrors the external scale
        config = {
            "name":          "Makerspace Scale",
            "unique_id":     "makerspace_scale_weight",
            "state_topic":   _scale_topic,
            "unit_of_measurement": unit,
            "device_class":  "weight",
            "state_class":   "measurement",
            "device": {
                "identifiers": ["makerspace_erp"],
                "name":        "Makerspace ERP",
                "model":       "Inventory Manager",
                "manufacturer":"HomeERP",
            },
        }
        discovery_topic = "homeassistant/sensor/makerspace_scale/config"

    try:
        if reset:
            # Clear the old retained entity so HA rebuilds it fresh.
            # Also clear stale topics for the other mode in case mode changed.
            _client.publish("homeassistant/number/makerspace_scale/config", "", retain=True)
            _client.publish("homeassistant/sensor/makerspace_scale/config", "", retain=True)
            time.sleep(0.5)  # give HA time to process removal before re-adding

        _client.publish(discovery_topic, json.dumps(config), retain=True)
        if _scale_mode == "ha_entity":
            # Always publish a retained state so HA entity is not "unavailable"
            state_val = _scale_reading if _scale_reading is not None else 0.0
            _client.publish(f"{base}/scale/state", str(state_val), retain=True)
        log.info(f"Scale HA discovery published ({_scale_mode}, reset={reset})")
        return True
    except Exception as e:
        log.warning(f"Scale discovery failed: {e}")
        return False


def connect(cfg: dict, db=None) -> dict:
    global _client, _config, _connected, _status_msg
    import paho.mqtt.client as mqtt

    disconnect()  # clean up any existing connection

    _config = cfg
    broker   = cfg.get("broker", "")
    port     = int(cfg.get("port", 1883))
    username = cfg.get("username", "")
    password = cfg.get("password", "")
    client_id = cfg.get("client_id", "makerspace-erp")

    def on_connect(client, userdata, flags, rc):
        global _connected, _status_msg
        with _lock:
            if rc == 0:
                _connected = True
                _status_msg = f"Connected to {broker}:{port}"
                log.info(_status_msg)
                _subscribe_all(client, db)
            else:
                _connected = False
                _status_msg = f"Connection failed (rc={rc})"
                log.warning(_status_msg)

    def on_disconnect(client, userdata, rc):
        global _connected, _status_msg
        with _lock:
            _connected = False
            _status_msg = "Disconnected" if rc == 0 else f"Disconnected unexpectedly (rc={rc})"

    def on_message(client, userdata, msg):
        _handle_message(msg)

    c = mqtt.Client(client_id=client_id)
    if username:
        c.username_pw_set(username, password or None)
    # TLS support
    if cfg.get("use_tls"):
        import ssl
        ca_cert = cfg.get("ca_cert_path") or None
        try:
            c.tls_set(ca_certs=ca_cert, cert_reqs=ssl.CERT_REQUIRED if ca_cert else ssl.CERT_NONE)
            if not ca_cert:
                c.tls_insecure_set(True)
        except Exception as e:
            log.warning(f"TLS setup warning: {e}")
    c.on_connect    = on_connect
    c.on_disconnect = on_disconnect
    c.on_message    = on_message

    try:
        c.connect(broker, port, keepalive=60)
        c.loop_start()
        _client = c
        _status_msg = f"Connecting to {broker}:{port}…"
        return {"status": "connecting", "broker": broker, "port": port}
    except Exception as e:
        _status_msg = f"Failed to connect: {e}"
        _connected = False
        return {"status": "error", "message": str(e)}


def disconnect():
    global _client, _connected, _status_msg
    if _client:
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass
        _client = None
    _connected = False
    _status_msg = "Disconnected"


def publish_item_state(item_id: int, name: str, quantity: float, unit: str, category: str = ""):
    """Called after any quantity change on an exposed item."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/items/{item_id}/state", str(quantity), retain=True)
        _client.publish(f"{base}/items/{item_id}/attributes",
                        json.dumps({"name": name, "unit": unit, "category": category}),
                        retain=True)
    except Exception as e:
        log.warning(f"MQTT publish failed: {e}")


def publish_discovery_for_item(item) -> bool:
    """Publish HA auto-discovery config for one item. Returns True on success."""
    if not _connected or not _client:
        return False
    base   = _config.get("base_topic", "makerspace")
    uid    = f"makerspace_{item.id}"
    cat    = item.category.name if item.category else ""
    config = {
        "name":                item.name,
        "unique_id":           uid,
        "state_topic":         f"{base}/items/{item.id}/state",
        "command_topic":       f"{base}/items/{item.id}/set",
        "unit_of_measurement": item.unit_name,
        "min":    0,
        "max":    999999,
        "step":   0.001,
        "mode":   "box",
        "device": {
            "identifiers": ["makerspace_erp"],
            "name":        "Makerspace ERP",
            "model":       "Inventory Manager",
            "manufacturer":"HomeERP",
        },
        "json_attributes_topic": f"{base}/items/{item.id}/attributes",
    }
    try:
        _client.publish(f"homeassistant/number/{uid}/config",
                        json.dumps(config), retain=True)
        # Immediately publish current state
        publish_item_state(item.id, item.name, item.quantity, item.unit_name, cat)
        return True
    except Exception as e:
        log.warning(f"Discovery publish failed for item {item.id}: {e}")
        return False


def remove_discovery_for_item(item_id: int):
    """Remove HA discovery (send empty payload to remove entity)."""
    if not _connected or not _client:
        return
    uid = f"makerspace_{item_id}"
    try:
        _client.publish(f"homeassistant/number/{uid}/config", "", retain=True)
    except Exception as e:
        log.warning(f"Discovery remove failed: {e}")


def publish_all_discovery(items) -> int:
    count = 0
    for item in items:
        if publish_discovery_for_item(item):
            count += 1
    return count



# ── Asset MQTT ────────────────────────────────────────────────────────────────

def publish_asset_state(asset_id: int, name: str, status: str, asset_tag: str = "",
                        location: str = "", checked_out_by: str = ""):
    """Publish asset status and attributes."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/assets/{asset_id}/state", status, retain=True)
        _client.publish(f"{base}/assets/{asset_id}/attributes",
                        json.dumps({
                            "name": name,
                            "asset_tag": asset_tag,
                            "location": location,
                            "checked_out_by": checked_out_by,
                        }), retain=True)
    except Exception as e:
        log.warning(f"MQTT asset publish failed: {e}")


def publish_asset_discovery(asset) -> bool:
    """Publish HA auto-discovery for asset as a select entity."""
    if not _connected or not _client:
        return False
    base = _config.get("base_topic", "makerspace")
    uid  = f"makerspace_asset_{asset.id}"
    loc  = asset.location.name if asset.location else ""
    config = {
        "name":          asset.name,
        "unique_id":     uid,
        "state_topic":   f"{base}/assets/{asset.id}/state",
        "command_topic": f"{base}/assets/{asset.id}/set",
        "options":       ["available", "checked_out", "maintenance", "retired"],
        "device": {
            "identifiers": ["makerspace_erp"],
            "name":        "Makerspace ERP",
            "model":       "Inventory Manager",
            "manufacturer":"HomeERP",
        },
        "json_attributes_topic": f"{base}/assets/{asset.id}/attributes",
    }
    try:
        _client.publish(f"homeassistant/select/{uid}/config",
                        json.dumps(config), retain=True)
        co = next((c for c in asset.checkouts if c.returned_at is None), None)
        publish_asset_state(
            asset.id, asset.name, asset.status,
            asset.asset_tag or "", loc,
            co.checked_out_by if co else "",
        )
        return True
    except Exception as e:
        log.warning(f"Asset discovery failed for {asset.id}: {e}")
        return False


def remove_asset_discovery(asset_id: int):
    if not _connected or not _client:
        return
    uid = f"makerspace_asset_{asset_id}"
    try:
        _client.publish(f"homeassistant/select/{uid}/config", "", retain=True)
    except Exception:
        pass





# ── Dashboard Widget MQTT ─────────────────────────────────────────────────────

def publish_dashboard_widget(widget_id: str, label: str, value, unit: str = ""):
    """Publish a single dashboard widget value as a retained sensor."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    uid = f"makerspace_dash_{widget_id}"
    try:
        _client.publish(f"{base}/dashboard/{widget_id}/state", str(value), retain=True)
        _client.publish(f"{base}/dashboard/{widget_id}/attributes",
                        json.dumps({"label": label, "unit": unit, "widget_id": widget_id}), retain=True)
    except Exception as e:
        log.warning(f"Dashboard widget MQTT publish failed [{widget_id}]: {e}")


def publish_dashboard_widget_discovery(widget_id: str, label: str, unit: str = ""):
    """Publish HA auto-discovery for a dashboard widget sensor."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    uid = f"makerspace_dash_{widget_id}"
    config = {
        "name": label,
        "unique_id": uid,
        "state_topic": f"{base}/dashboard/{widget_id}/state",
        "json_attributes_topic": f"{base}/dashboard/{widget_id}/attributes",
        "icon": "mdi:view-dashboard",
        "device": {"identifiers": ["makerspace_erp"], "name": "Makerspace ERP",
                   "model": "Inventory Manager", "manufacturer": "HomeERP"},
    }
    if unit:
        config["unit_of_measurement"] = unit
        config["state_class"] = "measurement"
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", json.dumps(config), retain=True)
    except Exception as e:
        log.warning(f"Dashboard widget discovery failed [{widget_id}]: {e}")


def publish_all_dashboard_widgets(db) -> int:
    """Bulk-publish all dashboard widgets enabled for MQTT. Returns count."""
    if not _connected or not _client:
        return 0
    try:
        from .models import AppSetting
        import json as _j
        row = db.query(AppSetting).filter(AppSetting.key == "dashboard_widget_integration").first()
        if not row or not row.value:
            return 0
        cfg = _j.loads(row.value)
        mqtt_cfg = cfg.get("mqtt", {})
        if not any(mqtt_cfg.values()):
            return 0
        stats = _gather_dashboard_stats(db)
        count = 0
        for wid, (value, label, unit) in stats.items():
            if mqtt_cfg.get(wid):
                publish_dashboard_widget_discovery(wid, label, unit)
                publish_dashboard_widget(wid, label, value, unit)
                count += 1
        return count
    except Exception as e:
        log.warning(f"Dashboard widget bulk publish failed: {e}")
        return 0


def _gather_dashboard_stats(db) -> dict:
    """Query all dashboard widget values. Returns {widget_id: (value, label, unit)}."""
    from datetime import date, datetime, timedelta
    from sqlalchemy import func
    today = date.today()
    stats = {}
    try:
        from .models import (Item, Location, Category, Transaction, Project,
                             Asset, AssetCheckout, PurchaseOrder,
                             AssetMaintenanceSchedule, AssemblyComponent, AppSetting)
        stats["total_items"] = (db.query(Item).count(), "Total Items", "items")
        low = db.query(Item).filter(Item.quantity > 0, Item.min_quantity > 0, Item.quantity <= Item.min_quantity).count()
        stats["low_stock"] = (low, "Low Stock Items", "items")
        stats["low_stock_list"] = stats["low_stock"]
        oos = db.query(Item).filter(Item.quantity <= 0).count()
        stats["out_of_stock"] = (oos, "Out of Stock", "items")
        stats["locations"] = (db.query(Location).count(), "Locations", "")
        stats["categories"] = (db.query(Category).count(), "Categories", "")
        total_val = sum((i.price or 0) * i.quantity for i in db.query(Item).filter(Item.price != None).all())
        stats["inventory_value"] = (round(total_val, 2), "Inventory Value", "USD")
        total_qty = db.query(func.sum(Item.quantity)).scalar() or 0
        stats["total_units"] = (round(float(total_qty), 2), "Total Units", "")
        active_proj = db.query(Project).filter(Project.status.in_(["planning", "in_progress"])).count()
        stats["projects_queue"] = (active_proj, "Active Projects", "")
        stats["projects_status"] = stats["projects_queue"]
        stats["assets_total"] = (db.query(Asset).count(), "Total Assets", "")
        co_count = db.query(Asset).filter(Asset.status == "checked_out").count()
        stats["assets_checked_out"] = (co_count, "Checked Out Assets", "")
        overdue = db.query(AssetCheckout).filter(
            AssetCheckout.returned_at == None,
            AssetCheckout.expected_return != None,
            AssetCheckout.expected_return < today.isoformat()
        ).count()
        stats["overdue_returns_count"] = (overdue, "Overdue Returns", "")
        stats["overdue_returns_list"] = stats["overdue_returns_count"]
        pending_pos = db.query(PurchaseOrder).filter(PurchaseOrder.status == "pending").count()
        stats["pending_pos_count"] = (pending_pos, "Pending POs", "")
        stats["pending_pos_list"] = stats["pending_pos_count"]
        # Buildable assemblies
        assemblies = db.query(Item).filter(Item.is_assembly == True).all()
        buildable = 0
        for asm in assemblies:
            comps = db.query(AssemblyComponent).filter(AssemblyComponent.assembly_id == asm.id).all()
            if not comps:
                continue
            if all((db.get(Item, c.component_id) or type("X",(object,),{"quantity":0})()).quantity >= c.quantity_per_unit for c in comps):
                buildable += 1
        stats["buildable_assemblies"] = (buildable, "Buildable Assemblies", "")
        stats["assembly_readiness"] = stats["buildable_assemblies"]
        # Expiry
        in30 = (today + timedelta(days=30)).isoformat()
        expiring = db.query(Item).filter(Item.expiry_date != None, Item.expiry_date <= in30, Item.expiry_date >= today.isoformat()).count()
        stats["expiry"] = (expiring, "Expiring Items", "items")
        # Recent transactions (last 24h)
        since = datetime.now() - timedelta(hours=24)
        tx_count = db.query(Transaction).filter(Transaction.created_at >= since).count()
        stats["recent_tx"] = (tx_count, "Transactions (24h)", "")
        stats["activity_feed"] = stats["recent_tx"]
        # Maintenance
        warn_row = db.query(AppSetting).filter(AppSetting.key == "maintenance_warn_days").first()
        warn_days = int(warn_row.value) if warn_row and warn_row.value else 14
        due_date = (today + timedelta(days=warn_days)).isoformat()
        maint = db.query(AssetMaintenanceSchedule).filter(
            AssetMaintenanceSchedule.next_due != None,
            AssetMaintenanceSchedule.next_due <= due_date
        ).count()
        stats["maintenance"] = (maint, "Upcoming Maintenance", "")
        stats["stock_by_location"] = stats["locations"]
        stats["recently_added"] = stats["total_items"]
    except Exception as e:
        log.warning(f"Dashboard stat gather failed: {e}")
    return stats

# ── Module MQTT ───────────────────────────────────────────────────────────────

def _is_module_mqtt_enabled(db, module: str) -> bool:
    """Check if a module has MQTT publishing enabled."""
    try:
        from .models import AppSetting
        row = db.query(AppSetting).filter(AppSetting.key == "integration_modules").first()
        if not row or not row.value:
            return False
        cfg = json.loads(row.value)
        return bool(cfg.get("mqtt", {}).get(module, False))
    except Exception:
        return False


def publish_project_state(project_id: int, name: str, status: str, item_count: int = 0):
    """Publish project state to MQTT."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/projects/{project_id}/state", status, retain=True)
        _client.publish(f"{base}/projects/{project_id}/attributes",
                        json.dumps({"name": name, "item_count": item_count}), retain=True)
    except Exception as e:
        log.warning(f"MQTT project publish failed: {e}")


def publish_project_discovery(project_id: int, name: str):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    uid = f"makerspace_project_{project_id}"
    config = {
        "name": name, "unique_id": uid,
        "state_topic": f"{base}/projects/{project_id}/state",
        "json_attributes_topic": f"{base}/projects/{project_id}/attributes",
        "icon": "mdi:hammer-screwdriver",
        "device": {"identifiers": ["makerspace_erp"], "name": "Makerspace ERP",
                   "model": "Inventory Manager", "manufacturer": "HomeERP"},
    }
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", json.dumps(config), retain=True)
    except Exception as e:
        log.warning(f"Project discovery failed: {e}")


def remove_project_discovery(project_id: int):
    if not _connected or not _client:
        return
    uid = f"makerspace_project_{project_id}"
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", "", retain=True)
        _client.publish(f"{base}/projects/{project_id}/state", "", retain=True)
    except Exception:
        pass


def publish_location_state(location_id: int, name: str, item_count: int, location_type: str = ""):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/locations/{location_id}/state", str(item_count), retain=True)
        _client.publish(f"{base}/locations/{location_id}/attributes",
                        json.dumps({"name": name, "type": location_type}), retain=True)
    except Exception as e:
        log.warning(f"MQTT location publish failed: {e}")


def publish_location_discovery(location_id: int, name: str):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    uid = f"makerspace_location_{location_id}"
    config = {
        "name": name, "unique_id": uid,
        "state_topic": f"{base}/locations/{location_id}/state",
        "json_attributes_topic": f"{base}/locations/{location_id}/attributes",
        "unit_of_measurement": "items", "state_class": "measurement",
        "icon": "mdi:map-marker",
        "device": {"identifiers": ["makerspace_erp"], "name": "Makerspace ERP",
                   "model": "Inventory Manager", "manufacturer": "HomeERP"},
    }
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", json.dumps(config), retain=True)
    except Exception as e:
        log.warning(f"Location discovery failed: {e}")


def remove_location_discovery(location_id: int):
    if not _connected or not _client:
        return
    uid = f"makerspace_location_{location_id}"
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", "", retain=True)
    except Exception:
        pass


def publish_category_state(category_id: int, name: str, item_count: int):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/categories/{category_id}/state", str(item_count), retain=True)
        _client.publish(f"{base}/categories/{category_id}/attributes",
                        json.dumps({"name": name}), retain=True)
    except Exception as e:
        log.warning(f"MQTT category publish failed: {e}")


def publish_category_discovery(category_id: int, name: str):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    uid = f"makerspace_category_{category_id}"
    config = {
        "name": name, "unique_id": uid,
        "state_topic": f"{base}/categories/{category_id}/state",
        "json_attributes_topic": f"{base}/categories/{category_id}/attributes",
        "unit_of_measurement": "items", "state_class": "measurement",
        "icon": "mdi:tag",
        "device": {"identifiers": ["makerspace_erp"], "name": "Makerspace ERP",
                   "model": "Inventory Manager", "manufacturer": "HomeERP"},
    }
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", json.dumps(config), retain=True)
    except Exception as e:
        log.warning(f"Category discovery failed: {e}")


def remove_category_discovery(category_id: int):
    if not _connected or not _client:
        return
    uid = f"makerspace_category_{category_id}"
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", "", retain=True)
    except Exception:
        pass


def publish_kit_state(kit_id: int, name: str, buildable: int, component_count: int = 0):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/kits/{kit_id}/state", str(buildable), retain=True)
        _client.publish(f"{base}/kits/{kit_id}/attributes",
                        json.dumps({"name": name, "component_count": component_count}), retain=True)
    except Exception as e:
        log.warning(f"MQTT kit publish failed: {e}")


def publish_kit_discovery(kit_id: int, name: str):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    uid = f"makerspace_kit_{kit_id}"
    config = {
        "name": name, "unique_id": uid,
        "state_topic": f"{base}/kits/{kit_id}/state",
        "json_attributes_topic": f"{base}/kits/{kit_id}/attributes",
        "unit_of_measurement": "buildable", "state_class": "measurement",
        "icon": "mdi:toolbox",
        "device": {"identifiers": ["makerspace_erp"], "name": "Makerspace ERP",
                   "model": "Inventory Manager", "manufacturer": "HomeERP"},
    }
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", json.dumps(config), retain=True)
    except Exception as e:
        log.warning(f"Kit discovery failed: {e}")


def remove_kit_discovery(kit_id: int):
    if not _connected or not _client:
        return
    uid = f"makerspace_kit_{kit_id}"
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", "", retain=True)
    except Exception:
        pass


def publish_po_state(po_id: int, status: str, po_number: str = "", supplier: str = "", line_count: int = 0):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/purchase_orders/{po_id}/state", status or "pending", retain=True)
        _client.publish(f"{base}/purchase_orders/{po_id}/attributes",
                        json.dumps({"po_number": po_number, "supplier": supplier, "line_count": line_count}), retain=True)
    except Exception as e:
        log.warning(f"MQTT PO publish failed: {e}")


def publish_po_discovery(po_id: int, name: str):
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    uid = f"makerspace_po_{po_id}"
    config = {
        "name": name, "unique_id": uid,
        "state_topic": f"{base}/purchase_orders/{po_id}/state",
        "json_attributes_topic": f"{base}/purchase_orders/{po_id}/attributes",
        "icon": "mdi:shopping",
        "device": {"identifiers": ["makerspace_erp"], "name": "Makerspace ERP",
                   "model": "Inventory Manager", "manufacturer": "HomeERP"},
    }
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", json.dumps(config), retain=True)
    except Exception as e:
        log.warning(f"PO discovery failed: {e}")


def remove_po_discovery(po_id: int):
    if not _connected or not _client:
        return
    uid = f"makerspace_po_{po_id}"
    try:
        _client.publish(f"homeassistant/sensor/{uid}/config", "", retain=True)
    except Exception:
        pass


def publish_transaction_event(item_id: int, item_name: str, tx_type: str, qty_change: float, created_by: str = ""):
    """Publish last-transaction sensor (no discovery, event-style)."""
    if not _connected or not _client:
        return
    base = _config.get("base_topic", "makerspace")
    try:
        _client.publish(f"{base}/transactions/last", tx_type, retain=True)
        _client.publish(f"{base}/transactions/last_attributes",
                        json.dumps({"item_id": item_id, "item_name": item_name,
                                    "type": tx_type, "quantity_change": qty_change,
                                    "created_by": created_by or ""}), retain=True)
    except Exception as e:
        log.warning(f"MQTT transaction event failed: {e}")


def publish_all_modules(db) -> None:
    """Bulk-publish all enabled modules. Called on MQTT reconnect and on demand."""
    try:
        from .models import AppSetting
        row = db.query(AppSetting).filter(AppSetting.key == "integration_modules").first()
        if not row or not row.value:
            return
        cfg = json.loads(row.value)
        mqtt_cfg = cfg.get("mqtt", {})
        if mqtt_cfg.get("locations"):
            _publish_all_locations(db)
        if mqtt_cfg.get("categories"):
            _publish_all_categories(db)
        if mqtt_cfg.get("kits"):
            _publish_all_kits(db)
        if mqtt_cfg.get("projects"):
            _publish_all_projects(db)
        if mqtt_cfg.get("purchase_orders"):
            _publish_all_pos(db)
    except Exception as e:
        log.warning(f"Bulk module publish failed: {e}")


def _calc_kit_buildable(db, kit) -> int:
    if not kit.kit_items:
        return 0
    from .models import Item
    min_b = None
    for ki in kit.kit_items:
        item = db.get(Item, ki.item_id)
        if not item or ki.quantity <= 0:
            return 0
        b = int(item.quantity // ki.quantity)
        if min_b is None or b < min_b:
            min_b = b
    return min_b or 0


def _publish_all_locations(db):
    from .models import Location, ItemLocation
    from sqlalchemy import func
    for loc in db.query(Location).all():
        count = db.query(func.count(ItemLocation.id)).filter(ItemLocation.location_id == loc.id).scalar() or 0
        publish_location_discovery(loc.id, loc.name)
        publish_location_state(loc.id, loc.name, count, loc.location_type or "")


def _publish_all_categories(db):
    from .models import Category, Item
    from sqlalchemy import func
    for cat in db.query(Category).all():
        count = db.query(func.count(Item.id)).filter(Item.category_id == cat.id).scalar() or 0
        publish_category_discovery(cat.id, cat.name)
        publish_category_state(cat.id, cat.name, count)


def _publish_all_kits(db):
    from .models import Kit
    for kit in db.query(Kit).all():
        buildable = _calc_kit_buildable(db, kit)
        publish_kit_discovery(kit.id, kit.name)
        publish_kit_state(kit.id, kit.name, buildable, len(kit.kit_items))


def _publish_all_projects(db):
    from .models import Project
    for p in db.query(Project).all():
        publish_project_discovery(p.id, p.name)
        publish_project_state(p.id, p.name, p.status, len(p.items))


def _publish_all_pos(db):
    from .models import PurchaseOrder
    for po in db.query(PurchaseOrder).all():
        label = po.po_number or f"PO #{po.id}"
        publish_po_discovery(po.id, label)
        publish_po_state(po.id, po.status or "pending", po.po_number or "",
                         po.supplier_name or "", len(po.line_items))

# ── Internal helpers ──────────────────────────────────────────────────────────

def _subscribe_all(client, db=None):
    base = _config.get("base_topic", "makerspace")
    # Subscribe wildcard for all item set commands
    client.subscribe(f"{base}/items/+/set")
    log.info(f"Subscribed to {base}/items/+/set")
    client.subscribe(f"{base}/assets/+/set")
    log.info(f"Subscribed to {base}/assets/+/set")

    # Subscribe to scale topic if configured
    if _scale_topic:
        client.subscribe(_scale_topic)
        log.info(f"Scale topic subscribed ({_scale_mode}): {_scale_topic}")
        if _scale_mode == 'ha_entity':
            publish_scale_discovery()

    # Publish current state for all exposed items
    if db is not None:
        try:
            from .models import Item
            items = db.query(Item).filter(Item.mqtt_exposed == True).all()
            for item in items:
                cat = item.category.name if item.category else ""
                publish_item_state(item.id, item.name, item.quantity, item.unit_name, cat)
                publish_discovery_for_item(item)
            # Also publish exposed assets
            from .models import Asset
            from sqlalchemy.orm import joinedload
            assets = db.query(Asset).options(
                joinedload(Asset.location), joinedload(Asset.checkouts)
            ).filter(Asset.mqtt_exposed == True).all()
            for asset in assets:
                publish_asset_discovery(asset)
        except Exception as e:
            log.warning(f"Failed to publish initial states: {e}")
        # Publish enabled module states
        try:
            publish_all_modules(db)
        except Exception as e:
            log.warning(f"Failed to publish module states: {e}")
        # Publish dashboard widget states
        try:
            publish_all_dashboard_widgets(db)
        except Exception as e:
            log.warning(f"Failed to publish dashboard widget states: {e}")


def _persist_scale_reading(value: float) -> None:
    """Save scale reading to DB so it survives service restarts."""
    try:
        from .database import SessionLocal
        from .models import AppSetting
        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == "scale_last_reading").first()
            if row:
                row.value = str(value)
            else:
                db.add(AppSetting(key="scale_last_reading", value=str(value)))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        log.debug(f"Could not persist scale reading: {e}")


def restore_scale_reading() -> None:
    """Load the last persisted scale reading from DB on startup."""
    global _scale_reading
    try:
        from .database import SessionLocal
        from .models import AppSetting
        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == "scale_last_reading").first()
            if row and row.value:
                _scale_reading = float(row.value)
                log.info(f"Restored scale reading from DB: {_scale_reading} {_scale_unit}")
        finally:
            db.close()
    except Exception as e:
        log.debug(f"Could not restore scale reading: {e}")


def _handle_message(msg):
    """Handle incoming set command for items and assets."""
    global _scale_reading
    import re
    base = _config.get('base_topic', 'makerspace')
    # Check for scale reading
    if _scale_topic and msg.topic == _scale_topic:
        try:
            _scale_reading = float(msg.payload.decode().strip())
            log.info(f"Scale reading received: {_scale_reading} {_scale_unit}")
            # Persist so reading survives service restarts
            _persist_scale_reading(_scale_reading)
            # Echo back to state topic in ha_entity mode
            if _scale_mode == 'ha_entity' and _client:
                _client.publish(f"{base}/scale/state", str(_scale_reading), retain=True)
        except Exception:
            log.warning(f"Invalid scale payload: {msg.payload}")
        return
    # Check if it's an asset command
    ma = re.match(rf"^{re.escape(base)}/assets/(\d+)/set$", msg.topic)
    if ma:
        _handle_asset_message(int(ma.group(1)), msg.payload.decode())
        return
    m = re.match(rf"^{re.escape(base)}/items/(\d+)/set$", msg.topic)
    if not m:
        return
    item_id = int(m.group(1))
    try:
        new_qty = float(msg.payload.decode())
    except Exception:
        log.warning(f"Invalid MQTT payload for item {item_id}: {msg.payload}")
        return

    # Create a new DB session for this thread
    try:
        from .database import SessionLocal
        from .models import Item, Transaction
        db = SessionLocal()
        try:
            item = db.get(Item, item_id)
            if not item or not item.mqtt_exposed:
                return
            before = item.quantity
            item.quantity = round(new_qty, 6)
            # Keep ItemLocation quantities in sync with the new total
            from .models import ItemLocation
            locs = db.query(ItemLocation).filter(ItemLocation.item_id == item_id).all()
            if len(locs) == 1:
                locs[0].quantity = item.quantity
            elif len(locs) > 1:
                diff = round(new_qty - before, 6)
                locs[0].quantity = max(0, round(locs[0].quantity + diff, 6))
            db.add(Transaction(
                item_id=item_id,
                transaction_type="adjustment",
                quantity_change=round(new_qty - before, 6),
                quantity_before=before,
                quantity_after=item.quantity,
                notes="Set via MQTT / Home Assistant",
                created_by="MQTT",
            ))
            db.commit()
            cat = item.category.name if item.category else ""
            publish_item_state(item_id, item.name, item.quantity, item.unit_name, cat)
            log.info(f"MQTT set item {item_id} qty {before} → {new_qty}")
        finally:
            db.close()
    except Exception as e:
        log.error(f"MQTT message handler error: {e}")


def _handle_asset_message(asset_id: int, payload: str):
    """Handle MQTT set for asset: checkout or status change."""
    VALID = {"available", "checked_out", "maintenance", "retired"}
    new_status = payload.strip().lower()
    if new_status not in VALID:
        log.warning(f"Invalid asset status from MQTT: {payload}")
        return
    try:
        from .database import SessionLocal
        from .models import Asset, AssetCheckout
        from sqlalchemy.orm import joinedload
        from datetime import datetime as dt
        db = SessionLocal()
        try:
            asset = db.query(Asset).options(
                joinedload(Asset.location), joinedload(Asset.checkouts)
            ).filter(Asset.id == asset_id).first()
            if not asset or not asset.mqtt_exposed:
                return
            open_co = next((c for c in asset.checkouts if c.returned_at is None), None)
            if new_status == "checked_out" and asset.status != "checked_out":
                co = AssetCheckout(asset_id=asset_id, checked_out_by="Home Assistant")
                db.add(co)
                asset.status = "checked_out"
                asset.status = new_status
            db.commit()
            db.refresh(asset)
            loc = asset.location.name if asset.location else ""
            new_co = next((c for c in asset.checkouts if c.returned_at is None), None)
            publish_asset_state(asset_id, asset.name, asset.status,
                                asset.asset_tag or "", loc,
                                new_co.checked_out_by if new_co else "")
            log.info(f"MQTT set asset {asset_id} status to {new_status}")
        finally:
            db.close()
    except Exception as e:
        log.error(f"MQTT asset handler error: {e}")
