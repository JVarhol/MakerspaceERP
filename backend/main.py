import os
import time
from pathlib import Path

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .database import engine, get_db
from . import models
from .models import Item, Location, Category, Transaction, Material, Project, ProjectItem, PurchaseOrder, PurchaseOrderItem, Asset, AssetCheckout, ItemLocation, Supplier
from .schemas import (DashboardStats, MaterialCreate, MaterialUpdate, MaterialOut,
                      ProjectCreate, ProjectUpdate, ProjectOut, ProjectItemCreate, ProjectItemOut,
                      PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderReceive, PurchaseOrderOut,
                      POItemCreate, POItemUpdate, POItemReceive, POItemOut,
                      AssetCreate, AssetUpdate, AssetOut, AssetCheckoutCreate, AssetCheckoutOut,
                      SupplierOut)
from typing import List
from sqlalchemy.orm import joinedload
from .routers import items, locations, categories, transactions, barcode
from .routers import category_fields
from .routers import kits
from .routers import settings as settings_router
from .routers import auth_router, users_router
from .auth import get_current_user, require_permission
_Wmat  = Depends(require_permission('materials',       'write'))
_Wpo   = Depends(require_permission('purchase_orders', 'write'))
_Wproj = Depends(require_permission('projects',        'write'))
_Wasset = Depends(require_permission('assets',         'write'))
from .routers import scale_router
from .routers import maintenance_router
from .routers import dev_router
from .routers import suppliers_router

models.Base.metadata.create_all(bind=engine)

UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/opt/makerspace-erp/data/uploads"))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

from contextlib import asynccontextmanager
import logging
log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app_):
    # ── Auto-connect MQTT and HA if previously configured ─────────────────────
    try:
        from .database import SessionLocal
        from .models import AppSetting
        from . import mqtt_service, ha_service
        import json
        db = SessionLocal()
        try:
            def _get_cfg(key):
                row = db.query(AppSetting).filter(AppSetting.key == key).first()
                return json.loads(row.value) if row and row.value else None

            mqtt_cfg = _get_cfg("mqtt")
            if mqtt_cfg and mqtt_cfg.get("broker"):
                log.info("Auto-connecting MQTT...")
                try:
                    mqtt_service.connect(mqtt_cfg, db)
                    log.info("MQTT auto-connected")
                except Exception as exc:
                    log.warning(f"MQTT auto-connect failed: {exc}")

            ha_cfg = _get_cfg("ha")
            if ha_cfg and ha_cfg.get("url") and ha_cfg.get("token"):
                log.info("Auto-configuring Home Assistant...")
                try:
                    ha_service.configure(ha_cfg)
                    log.info("HA auto-configured")
                except Exception as exc:
                    log.warning(f"HA auto-configure failed: {exc}")

            scale_cfg = _get_cfg("scale")
            if scale_cfg and scale_cfg.get("enabled"):
                log.info("Auto-configuring scale...")
                try:
                    mqtt_service.configure_scale(
                        mode  = scale_cfg.get("mode", "ha_entity"),
                        topic = scale_cfg.get("topic", ""),
                        unit  = scale_cfg.get("unit", "g"),
                    )
                    mqtt_service.restore_scale_reading()
                    log.info("Scale auto-configured")
                except Exception as exc:
                    log.warning(f"Scale auto-configure failed: {exc}")
        finally:
            db.close()
    except Exception as exc:
        log.warning(f"Startup auto-connect error: {exc}")

    yield  # app runs here

app = FastAPI(title="Makerspace ERP", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.include_router(items.router)
app.include_router(locations.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(barcode.router)
app.include_router(category_fields.router)
app.include_router(kits.router)
app.include_router(settings_router.router)
app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(scale_router.router)
app.include_router(maintenance_router.router)
app.include_router(dev_router.router)
app.include_router(suppliers_router.router)

# ── Module integration helpers ────────────────────────────────────────────────
def _add_to_item_location(db: Session, item_id: int, qty: float, location_id: int | None):
    """Add qty to an ItemLocation row. If location_id is None, auto-selects the only location (if exactly one)."""
    locs = db.query(ItemLocation).filter(ItemLocation.item_id == item_id).all()
    if location_id is None:
        if len(locs) == 1:
            location_id = locs[0].location_id
        else:
            return  # 0 or multiple locations with no choice — skip location update
    existing = next((l for l in locs if l.location_id == location_id), None)
    if existing:
        existing.quantity = (existing.quantity or 0) + qty
    else:
        db.add(ItemLocation(item_id=item_id, location_id=location_id, quantity=qty))


def _publish_project(db, p):
    try:
        from . import mqtt_service, ha_service
        count = len(p.items) if hasattr(p, 'items') else 0
        if mqtt_service._is_module_mqtt_enabled(db, 'projects'):
            mqtt_service.publish_project_discovery(p.id, p.name)
            mqtt_service.publish_project_state(p.id, p.name, p.status, count)
        if ha_service._is_module_ha_enabled(db, 'projects'):
            ha_service.push_project_state(p.id, p.name, p.status, count)
    except Exception:
        pass

def _publish_po(db, po):
    try:
        from . import mqtt_service, ha_service
        lc = len(po.line_items) if hasattr(po, 'line_items') else 0
        if mqtt_service._is_module_mqtt_enabled(db, 'purchase_orders'):
            mqtt_service.publish_po_discovery(po.id, po.po_number or f'PO #{po.id}')
            mqtt_service.publish_po_state(po.id, po.status or 'pending', po.po_number or '', po.supplier_name or '', lc)
        if ha_service._is_module_ha_enabled(db, 'purchase_orders'):
            ha_service.push_po_state(po.id, po.status or 'pending', po.po_number or '', po.supplier_name or '', lc)
    except Exception:
        pass

def _publish_transaction(db, item, tx):
    try:
        from . import mqtt_service
        if mqtt_service._is_module_mqtt_enabled(db, 'transactions'):
            mqtt_service.publish_transaction_event(item.id, item.name, tx.transaction_type, tx.quantity_change, tx.created_by or '')
    except Exception:
        pass



# ── Materials CRUD ────────────────────────────────────────────────────────────
@app.get("/api/materials", response_model=List[MaterialOut], tags=["materials"])
def list_materials(_cu=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Material).order_by(Material.name).all()

@app.get("/api/materials/{mid}", response_model=MaterialOut, tags=["materials"])
def get_material(mid: int, _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    m = db.get(Material, mid)
    if not m: raise HTTPException(404, "Not found")
    return m

@app.post("/api/materials", response_model=MaterialOut, status_code=201, tags=["materials"])
def create_material(data: MaterialCreate, _cu=Depends(get_current_user), _w=_Wmat, db: Session = Depends(get_db)):
    m = Material(**data.model_dump())
    db.add(m); db.commit(); db.refresh(m); return m

@app.patch("/api/materials/{mid}", response_model=MaterialOut, tags=["materials"])
def update_material(mid: int, data: MaterialUpdate, _cu=Depends(get_current_user), _w=_Wmat, db: Session = Depends(get_db)):
    m = db.get(Material, mid)
    if not m: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(m, k, v)
    db.commit(); db.refresh(m); return m

@app.delete("/api/materials/{mid}", status_code=204, tags=["materials"])
def delete_material(mid: int, _cu=Depends(get_current_user), _w=_Wmat, db: Session = Depends(get_db)):
    m = db.get(Material, mid)
    if not m: raise HTTPException(404, "Not found")
    db.delete(m); db.commit()

# ── Purchase Orders ────────────────────────────────────────────────────────────
def _load_po(po_id: int, db: Session):
    return (db.query(PurchaseOrder)
            .options(
                joinedload(PurchaseOrder.supplier),
                joinedload(PurchaseOrder.item).joinedload(Item.category),
                joinedload(PurchaseOrder.line_items).joinedload(PurchaseOrderItem.item).joinedload(Item.category),
                joinedload(PurchaseOrder.line_items).joinedload(PurchaseOrderItem.item)
                    .joinedload(Item.locations).joinedload(ItemLocation.location),
            )
            .filter(PurchaseOrder.id == po_id).first())

def _po_number(po_id: int, db: Session) -> str:
    existing = db.query(PurchaseOrder).count()
    return f"PO-{po_id:04d}"

def _sync_po_status(po: PurchaseOrder):
    if not po.line_items:
        return
    statuses = [li.status for li in po.line_items]
    if all(s == "cancelled" for s in statuses):
        po.status = "cancelled"
    elif all(s == "received" for s in statuses):
        po.status = "received"
    elif any(s in ("received", "partial") for s in statuses):
        po.status = "partial"
    else:
        po.status = "pending"

@app.get("/api/purchase-orders", response_model=List[PurchaseOrderOut], tags=["purchase-orders"])
def list_purchase_orders(item_id: int = None, status: str = None, _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    q = (db.query(PurchaseOrder)
         .options(
             joinedload(PurchaseOrder.supplier),
             joinedload(PurchaseOrder.item).joinedload(Item.category),
             joinedload(PurchaseOrder.line_items).joinedload(PurchaseOrderItem.item).joinedload(Item.category),
             joinedload(PurchaseOrder.line_items).joinedload(PurchaseOrderItem.item)
                 .joinedload(Item.locations).joinedload(ItemLocation.location),
         ))
    if status: q = q.filter(PurchaseOrder.status == status)
    if item_id:
        from sqlalchemy import exists
        q = q.filter(exists().where(
            (PurchaseOrderItem.po_id == PurchaseOrder.id) &
            (PurchaseOrderItem.item_id == item_id)
        ))
    return q.order_by(PurchaseOrder.created_at.desc()).all()

@app.post("/api/purchase-orders", response_model=PurchaseOrderOut, status_code=201, tags=["purchase-orders"])
def create_purchase_order(data: PurchaseOrderCreate, _cu=Depends(get_current_user), _w=_Wpo, db: Session = Depends(get_db)):
    # If supplier_id given and no supplier_name, pull name from suppliers table
    sup_name = data.supplier_name
    if data.supplier_id and not sup_name:
        sup = db.get(Supplier, data.supplier_id)
        if sup:
            sup_name = sup.name
    po = PurchaseOrder(
        supplier_id=data.supplier_id,
        supplier_name=sup_name,
        expected_date=data.expected_date,
        notes=data.notes,
        status="pending",
    )
    db.add(po); db.flush()  # get ID before commit
    po.po_number = _po_number(po.id, db)
    # Handle items list (new multi-item style)
    items_to_add = list(data.items) if data.items else []
    # Handle legacy single-item style
    if data.item_id and data.quantity_ordered:
        if not db.get(Item, data.item_id):
            raise HTTPException(404, "Item not found")
        items_to_add.append(POItemCreate(item_id=data.item_id, quantity_ordered=data.quantity_ordered))
    for li in items_to_add:
        if not db.get(Item, li.item_id):
            raise HTTPException(404, f"Item {li.item_id} not found")
        db.add(PurchaseOrderItem(
            po_id=po.id, item_id=li.item_id,
            quantity_ordered=li.quantity_ordered,
            notes=li.notes, status="pending",
        ))
    db.commit()
    loaded = _load_po(po.id, db)
    _publish_po(db, db.get(PurchaseOrder, po.id))
    return loaded

@app.get("/api/purchase-orders/{po_id}", response_model=PurchaseOrderOut, tags=["purchase-orders"])
def get_purchase_order(po_id: int, _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    po = _load_po(po_id, db)
    if not po: raise HTTPException(404, "Not found")
    return po

@app.patch("/api/purchase-orders/{po_id}", response_model=PurchaseOrderOut, tags=["purchase-orders"])
def update_purchase_order(po_id: int, data: PurchaseOrderUpdate, _cu=Depends(get_current_user), _w=_Wpo, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po: raise HTTPException(404, "Not found")
    updates = data.model_dump(exclude_none=True)
    # If supplier_id is changing and no explicit supplier_name, sync name
    if 'supplier_id' in updates and 'supplier_name' not in updates:
        sup = db.get(Supplier, updates['supplier_id']) if updates['supplier_id'] else None
        updates['supplier_name'] = sup.name if sup else None
    for k, v in updates.items():
        setattr(po, k, v)
    db.commit()
    loaded = _load_po(po_id, db)
    _publish_po(db, po)
    return loaded

# ── PO line-item endpoints ─────────────────────────────────────────────────────
@app.post("/api/purchase-orders/{po_id}/items", response_model=PurchaseOrderOut, status_code=201, tags=["purchase-orders"])
def add_po_item(po_id: int, data: POItemCreate, _cu=Depends(get_current_user), _w=_Wpo, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po: raise HTTPException(404, "PO not found")
    if not db.get(Item, data.item_id): raise HTTPException(404, "Item not found")
    db.add(PurchaseOrderItem(po_id=po_id, item_id=data.item_id,
                              quantity_ordered=data.quantity_ordered, notes=data.notes))
    db.commit()
    return _load_po(po_id, db)

@app.patch("/api/purchase-orders/{po_id}/items/{line_id}", response_model=PurchaseOrderOut, tags=["purchase-orders"])
def update_po_item(po_id: int, line_id: int, data: POItemUpdate, _cu=Depends(get_current_user), _w=_Wpo, db: Session = Depends(get_db)):
    li = db.get(PurchaseOrderItem, line_id)
    if not li or li.po_id != po_id: raise HTTPException(404, "Line item not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(li, k, v)
    db.commit()
    return _load_po(po_id, db)

@app.delete("/api/purchase-orders/{po_id}/items/{line_id}", response_model=PurchaseOrderOut, tags=["purchase-orders"])
def delete_po_item(po_id: int, line_id: int, _cu=Depends(get_current_user), _w=_Wpo, db: Session = Depends(get_db)):
    li = db.get(PurchaseOrderItem, line_id)
    if not li or li.po_id != po_id: raise HTTPException(404, "Line item not found")
    db.delete(li); db.commit()
    return _load_po(po_id, db)

@app.post("/api/purchase-orders/{po_id}/items/{line_id}/receive", response_model=PurchaseOrderOut, tags=["purchase-orders"])
def receive_po_item(po_id: int, line_id: int, data: POItemReceive, _cu=Depends(get_current_user), _w=_Wpo, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po: raise HTTPException(404, "PO not found")
    li = db.get(PurchaseOrderItem, line_id)
    if not li or li.po_id != po_id: raise HTTPException(404, "Line item not found")
    if li.status in ("received", "cancelled"):
        raise HTTPException(400, f"Line item already {li.status}")
    item = db.get(Item, li.item_id)
    if not item: raise HTTPException(404, "Item not found")
    qty = data.quantity_received
    if qty <= 0: raise HTTPException(400, "Quantity must be > 0")
    tx = Transaction(
        item_id=item.id, transaction_type="add",
        quantity_change=qty, quantity_before=item.quantity, quantity_after=item.quantity + qty,
        notes=data.notes or f"Received from {po.po_number or 'PO #'+str(po_id)}" + (f" — {po.supplier_name}" if po.supplier_name else ""),
        created_by="Purchase Order",
    )
    item.quantity += qty
    if li.unit_price is not None:
        item.price = li.unit_price
    _add_to_item_location(db, item.id, qty, getattr(data, 'location_id', None))
    li.quantity_received = (li.quantity_received or 0) + qty
    li.status = "received" if li.quantity_received >= li.quantity_ordered else "partial"
    _sync_po_status(po)
    db.add(tx); db.commit()
    _publish_po(db, po)
    _publish_transaction(db, item, tx)
    return _load_po(po_id, db)

# Legacy receive endpoint (kept for backward compat)
@app.post("/api/purchase-orders/{po_id}/receive", response_model=PurchaseOrderOut, tags=["purchase-orders"])
def receive_purchase_order(po_id: int, data: PurchaseOrderReceive, _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    po = _load_po(po_id, db)
    if not po: raise HTTPException(404, "Not found")
    # Receive all pending line items
    for li in po.line_items:
        if li.status not in ("received", "cancelled"):
            item = db.get(Item, li.item_id)
            if item:
                qty = data.quantity_received or (li.quantity_ordered - li.quantity_received)
                tx = Transaction(
                    item_id=item.id, transaction_type="add", quantity_change=qty,
                    quantity_before=item.quantity, quantity_after=item.quantity + qty,
                    notes=data.notes or f"Received from {po.po_number}", created_by="Purchase Order",
                )
                item.quantity += qty
                _add_to_item_location(db, item.id, qty, None)
                li.quantity_received = (li.quantity_received or 0) + qty
                li.status = "received" if li.quantity_received >= li.quantity_ordered else "partial"
                db.add(tx)
    _sync_po_status(po)
    db.commit()
    return _load_po(po_id, db)

@app.delete("/api/purchase-orders/{po_id}", status_code=204, tags=["purchase-orders"])
def delete_purchase_order(po_id: int, _cu=Depends(get_current_user), _w=_Wpo, db: Session = Depends(get_db)):
    po = db.get(PurchaseOrder, po_id)
    if not po: raise HTTPException(404, "Not found")
    try:
        from . import mqtt_service
        mqtt_service.remove_po_discovery(po_id)
    except Exception:
        pass
    db.delete(po); db.commit()

# ── Projects CRUD ─────────────────────────────────────────────────────────────
@app.get("/api/projects", response_model=List[ProjectOut], tags=["projects"])
def list_projects(_cu=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Project).options(
        joinedload(Project.items).joinedload(ProjectItem.item).joinedload(Item.category)
    ).order_by(Project.created_at.desc()).all()

@app.post("/api/projects", response_model=ProjectOut, status_code=201, tags=["projects"])
def create_project(data: ProjectCreate, _cu=Depends(get_current_user), _w=_Wproj, db: Session = Depends(get_db)):
    p = Project(**data.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    _publish_project(db, p)
    return p

@app.get("/api/projects/{pid}", response_model=ProjectOut, tags=["projects"])
def get_project(pid: int, _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.query(Project).options(
        joinedload(Project.items).joinedload(ProjectItem.item).joinedload(Item.category)
    ).filter(Project.id == pid).first()
    if not p: raise HTTPException(404, "Not found")
    return p

@app.patch("/api/projects/{pid}", response_model=ProjectOut, tags=["projects"])
def update_project(pid: int, data: ProjectUpdate, _cu=Depends(get_current_user), _w=_Wproj, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    db.commit()
    result = get_project(pid, db)
    _publish_project(db, p)
    return result

@app.delete("/api/projects/{pid}", status_code=204, tags=["projects"])
def delete_project(pid: int, _cu=Depends(get_current_user), _w=_Wproj, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p: raise HTTPException(404, "Not found")
    try:
        from . import mqtt_service
        mqtt_service.remove_project_discovery(pid)
    except Exception:
        pass
    db.delete(p); db.commit()

@app.post("/api/projects/{pid}/items", response_model=ProjectItemOut, status_code=201, tags=["projects"])
def add_project_item(pid: int, data: ProjectItemCreate, _cu=Depends(get_current_user), _w=_Wproj, db: Session = Depends(get_db)):
    if not db.get(Project, pid): raise HTTPException(404, "Project not found")
    pi = ProjectItem(project_id=pid, **data.model_dump())
    db.add(pi); db.commit(); db.refresh(pi)
    pi.item = db.query(Item).options(joinedload(Item.category)).get(pi.item_id)
    return pi

@app.patch("/api/projects/{pid}/items/{iid}", response_model=ProjectItemOut, tags=["projects"])
def update_project_item(pid: int, iid: int, data: ProjectItemCreate, _cu=Depends(get_current_user), _w=_Wproj, db: Session = Depends(get_db)):
    pi = db.query(ProjectItem).filter(ProjectItem.project_id == pid, ProjectItem.id == iid).first()
    if not pi: raise HTTPException(404, "Not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(pi, k, v)
    db.commit(); db.refresh(pi)
    pi.item = db.query(Item).options(joinedload(Item.category)).get(pi.item_id)
    return pi

@app.delete("/api/projects/{pid}/items/{iid}", status_code=204, tags=["projects"])
def remove_project_item(pid: int, iid: int, _cu=Depends(get_current_user), _w=_Wproj, db: Session = Depends(get_db)):
    pi = db.query(ProjectItem).filter(ProjectItem.project_id == pid, ProjectItem.id == iid).first()
    if not pi: raise HTTPException(404, "Not found")
    db.delete(pi); db.commit()



# ── Assets CRUD ───────────────────────────────────────────────────────────────
def _load_asset(aid: int, db: Session):
    """Load an asset with location + checkouts; sets current_checkout. No FastAPI deps."""
    from sqlalchemy.orm import joinedload as jl
    a = db.query(Asset).options(jl(Asset.location), jl(Asset.checkouts)).filter(Asset.id == aid).first()
    if not a:
        raise HTTPException(404, "Asset not found")
    a.current_checkout = next((c for c in a.checkouts if c.returned_at is None), None)
    return a

@app.get("/api/assets", response_model=List[AssetOut], tags=["assets"])
def list_assets(q: str = None, limit: int = 1000, _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload as jl
    query = db.query(Asset).options(
        jl(Asset.location),
        jl(Asset.checkouts)
    )
    if q:
        query = query.filter(Asset.name.ilike(f"%{q}%"))
    assets = query.order_by(Asset.name).limit(limit).all()
    for a in assets:
        active = next((c for c in a.checkouts if c.returned_at is None), None)
        a.current_checkout = active
    return assets

@app.get("/api/assets/{aid}", response_model=AssetOut, tags=["assets"])
def get_asset(aid: int, _cu=Depends(get_current_user), db: Session = Depends(get_db)):
    return _load_asset(aid, db)

@app.post("/api/assets", response_model=AssetOut, status_code=201, tags=["assets"])
def create_asset(data: AssetCreate, _cu=Depends(get_current_user), _w=_Wasset, db: Session = Depends(get_db)):
    a = Asset(**data.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    a.checkouts = []; a.current_checkout = None
    return a

@app.patch("/api/assets/{aid}", response_model=AssetOut, tags=["assets"])
def update_asset(aid: int, data: AssetUpdate, _cu=Depends(get_current_user), _w=_Wasset, db: Session = Depends(get_db)):
    a = db.get(Asset, aid)
    if not a: raise HTTPException(404, "Asset not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    return _load_asset(aid, db)

@app.delete("/api/assets/{aid}", status_code=204, tags=["assets"])
def delete_asset(aid: int, _cu=Depends(get_current_user), _w=_Wasset, db: Session = Depends(get_db)):
    a = db.get(Asset, aid)
    if not a: raise HTTPException(404, "Asset not found")
    db.delete(a); db.commit()

@app.post("/api/assets/{aid}/checkout", response_model=AssetOut, tags=["assets"])
def checkout_asset(aid: int, data: AssetCheckoutCreate, _cu=Depends(get_current_user), _w=_Wasset, db: Session = Depends(get_db)):
    a = db.get(Asset, aid)
    if not a: raise HTTPException(404, "Asset not found")
    if a.status == "checked_out": raise HTTPException(400, "Asset is already checked out")
    co = AssetCheckout(asset_id=aid, **data.model_dump())
    a.status = "checked_out"
    db.add(co); db.commit()
    return _load_asset(aid, db)

@app.post("/api/assets/{aid}/return", response_model=AssetOut, tags=["assets"])
def return_asset(aid: int, _cu=Depends(get_current_user), _w=_Wasset, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    a = db.get(Asset, aid)
    if not a: raise HTTPException(404, "Asset not found")
    active = db.query(AssetCheckout).filter(
        AssetCheckout.asset_id == aid,
        AssetCheckout.returned_at == None
    ).first()
    if active:
        active.returned_at = datetime.now(timezone.utc)
    a.status = "available"
    db.commit()
    return _load_asset(aid, db)

# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/api/dashboard", response_model=DashboardStats, tags=["dashboard"])
def dashboard_stats(_cu=Depends(get_current_user), db: Session = Depends(get_db)):
    total_items = db.query(Item).count()
    low_stock = db.query(Item).filter(
        Item.quantity > 0,
        Item.min_quantity > 0,
        Item.quantity <= Item.min_quantity
    ).count()
    total_locations = db.query(Location).count()
    total_categories = db.query(Category).count()
    recent_tx = db.query(Transaction).order_by(
        Transaction.created_at.desc()
    ).limit(10).all()
    return DashboardStats(
        total_items=total_items,
        low_stock_items=low_stock,
        total_locations=total_locations,
        total_categories=total_categories,
        recent_transactions=recent_tx,
    )


# ── Serve frontend SPA ────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str = ""):
        index = FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"detail": "Frontend not found"}
