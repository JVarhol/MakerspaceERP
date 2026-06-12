"""
Purchase Requests Router
  GET    /api/purchase-requests               → list
  POST   /api/purchase-requests               → create
  GET    /api/purchase-requests/{id}          → get
  PUT    /api/purchase-requests/{id}          → update
  DELETE /api/purchase-requests/{id}          → delete
  POST   /api/purchase-requests/{id}/approve  → approve
  POST   /api/purchase-requests/{id}/reject   → reject
  POST   /api/purchase-requests/{id}/purchase → mark purchased
  POST   /api/purchase-requests/{id}/receive  → mark received
  PUT    /api/purchase-requests/{id}/lines    → replace lines
"""
from __future__ import annotations
import json, re
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import PurchaseRequest, PurchaseRequestLine, Item, Supplier, Notification, User
from ..auth import get_current_user, get_permissions

router = APIRouter(tags=["purchase_requests"], dependencies=[Depends(get_current_user)])


# ── Schemas ───────────────────────────────────────────────────────────────────

class PRLineIn(BaseModel):
    item_id:     Optional[int]   = None
    description: str             = ""
    quantity:    float           = 1.0
    unit_price:  Optional[float] = None
    notes:       Optional[str]   = None

class PRCreate(BaseModel):
    supplier_id:   Optional[int] = None
    supplier_name: Optional[str] = None
    notes:         Optional[str] = None
    urgency:       Optional[str] = "normal"
    lines:         List[PRLineIn] = []

class PRUpdate(BaseModel):
    supplier_id:   Optional[int] = None
    supplier_name: Optional[str] = None
    notes:         Optional[str] = None
    urgency:       Optional[str] = None

class ApproveBody(BaseModel):
    notes: Optional[str] = None

class PurchaseBody(BaseModel):
    notes: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _next_pr_number(db: Session) -> str:
    count = db.query(PurchaseRequest).count()
    return f"PR-{count+1:04d}"


def _line_out(l: PurchaseRequestLine) -> dict:
    return {
        "id":          l.id,
        "request_id":  l.request_id,
        "item_id":     l.item_id,
        "item_name":   l.item.name if l.item else None,
        "description": l.description,
        "quantity":    l.quantity,
        "unit_price":  l.unit_price,
        "notes":       l.notes,
        "line_status": l.line_status,
    }


def _pr_out(r: PurchaseRequest) -> dict:
    return {
        "id":             r.id,
        "request_number": r.request_number,
        "status":         r.status,
        "supplier_id":    r.supplier_id,
        "supplier_name":  r.supplier_name or (r.supplier.name if r.supplier else None),
        "requested_by":   r.requested_by,
        "approved_by":    r.approved_by,
        "purchased_by":   r.purchased_by,
        "approved_at":    r.approved_at.isoformat() if r.approved_at else None,
        "purchased_at":   r.purchased_at.isoformat() if r.purchased_at else None,
        "notes":          r.notes,
        "urgency":        r.urgency,
        "created_at":     r.created_at.isoformat() if r.created_at else None,
        "updated_at":     r.updated_at.isoformat() if r.updated_at else None,
        "lines":          [_line_out(l) for l in r.lines],
    }


def _notify_role(db: Session, role_flag: str, title: str, body: str,
                 source_type: str, source_id: int):
    """Create a notification for every user that has a given role flag in their permissions JSON."""
    users = db.query(User).filter(User.is_active == True).all()
    for u in users:
        try:
            perms = json.loads(u.permissions or "{}")
        except Exception:
            perms = {}
        if u.role == "admin" or perms.get(role_flag):
            n = Notification(
                user_id=u.id,
                title=title,
                body=body,
                level="info",
                source_type=source_type,
                source_id=source_id,
            )
            db.add(n)



def _require_perm(user, flag: str, label: str):
    """Raise 403 if user lacks the given permission flag (admins always pass)."""
    if user.role == "admin":
        return
    perms = get_permissions(user)
    if not perms.get(flag):
        raise HTTPException(403, f"Permission denied: {label} required")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/api/purchase-requests")
def list_prs(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = (db.query(PurchaseRequest)
           .options(joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.item),
                    joinedload(PurchaseRequest.supplier))
           .order_by(PurchaseRequest.created_at.desc()))
    if status:
        q = q.filter(PurchaseRequest.status == status)
    return [_pr_out(r) for r in q.all()]


@router.post("/api/purchase-requests", status_code=201)
def create_pr(body: PRCreate, db: Session = Depends(get_db),
              current_user=Depends(get_current_user)):
    r = PurchaseRequest(
        request_number=_next_pr_number(db),
        status="pending_approval",
        supplier_id=body.supplier_id,
        supplier_name=body.supplier_name,
        requested_by=current_user.username,
        notes=body.notes,
        urgency=body.urgency or "normal",
    )
    db.add(r); db.flush()
    for ln in body.lines:
        item_name = ""
        if ln.item_id:
            it = db.get(Item, ln.item_id)
            item_name = it.name if it else ""
        l = PurchaseRequestLine(
            request_id=r.id,
            item_id=ln.item_id,
            description=ln.description or item_name,
            quantity=ln.quantity,
            unit_price=ln.unit_price,
            notes=ln.notes,
        )
        db.add(l)
    db.commit(); db.refresh(r)
    # notify approvers
    _notify_role(db, "purchase_approver",
                 f"New purchase request {r.request_number}",
                 f"{current_user.username} submitted {r.request_number} — {len(body.lines)} line(s)",
                 "purchase_request", r.id)
    db.commit()
    return _pr_out(r)


@router.get("/api/purchase-requests/{rid}")
def get_pr(rid: int, db: Session = Depends(get_db)):
    r = (db.query(PurchaseRequest)
           .options(joinedload(PurchaseRequest.lines).joinedload(PurchaseRequestLine.item),
                    joinedload(PurchaseRequest.supplier))
           .filter(PurchaseRequest.id == rid).first())
    if not r:
        raise HTTPException(404, "Not found")
    return _pr_out(r)


@router.put("/api/purchase-requests/{rid}")
def update_pr(rid: int, body: PRUpdate, db: Session = Depends(get_db)):
    r = db.get(PurchaseRequest, rid)
    if not r:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(r, k, v)
    db.commit(); db.refresh(r)
    return _pr_out(r)


@router.delete("/api/purchase-requests/{rid}", status_code=204)
def delete_pr(rid: int, db: Session = Depends(get_db)):
    r = db.get(PurchaseRequest, rid)
    if not r:
        raise HTTPException(404, "Not found")
    db.delete(r); db.commit()


@router.post("/api/purchase-requests/{rid}/approve")
def approve_pr(rid: int, body: ApproveBody, db: Session = Depends(get_db),
               current_user=Depends(get_current_user)):
    _require_perm(current_user, "purchase_approver", "Purchase Approver")
    r = db.get(PurchaseRequest, rid)
    if not r:
        raise HTTPException(404, "Not found")
    if r.status != "pending_approval":
        raise HTTPException(400, f"Request is already '{r.status}', cannot approve")
    r.status = "approved"
    r.approved_by = current_user.username
    r.approved_at = datetime.utcnow()
    if body.notes:
        r.notes = (r.notes or "") + f"\n[Approved] {body.notes}"
    db.commit(); db.refresh(r)
    # notify purchasers + requester
    _notify_role(db, "purchase_purchaser",
                 f"Purchase request {r.request_number} approved",
                 f"Approved by {current_user.username}. Ready to order.",
                 "purchase_request", r.id)
    db.commit()
    return _pr_out(r)


@router.post("/api/purchase-requests/{rid}/reject")
def reject_pr(rid: int, body: ApproveBody, db: Session = Depends(get_db),
              current_user=Depends(get_current_user)):
    _require_perm(current_user, "purchase_approver", "Purchase Approver")
    r = db.get(PurchaseRequest, rid)
    if not r:
        raise HTTPException(404, "Not found")
    if r.status != "pending_approval":
        raise HTTPException(400, f"Request is already '{r.status}', cannot reject")
    r.status = "rejected"
    r.approved_by = current_user.username
    r.approved_at = datetime.utcnow()
    if body.notes:
        r.notes = (r.notes or "") + f"\n[Rejected] {body.notes}"
    db.commit(); db.refresh(r)
    return _pr_out(r)


@router.post("/api/purchase-requests/{rid}/purchase")
def mark_purchased(rid: int, body: PurchaseBody, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    _require_perm(current_user, "purchase_purchaser", "Purchase Purchaser")
    r = db.get(PurchaseRequest, rid)
    if not r:
        raise HTTPException(404, "Not found")
    if r.status != "approved":
        raise HTTPException(400, f"Request must be 'approved' before ordering (currently '{r.status}')")
    r.status = "ordered"
    r.purchased_by = current_user.username
    r.purchased_at = datetime.utcnow()
    if body.notes:
        r.notes = (r.notes or "") + f"\n[Ordered] {body.notes}"
    db.commit(); db.refresh(r)
    return _pr_out(r)


@router.post("/api/purchase-requests/{rid}/receive")
def mark_received(rid: int, db: Session = Depends(get_db),
                  current_user=Depends(get_current_user)):
    _require_perm(current_user, "purchase_purchaser", "Purchase Purchaser")
    r = db.get(PurchaseRequest, rid)
    if not r:
        raise HTTPException(404, "Not found")
    r.status = "received"
    db.commit(); db.refresh(r)
    return _pr_out(r)


@router.put("/api/purchase-requests/{rid}/lines")
def replace_lines(rid: int, lines: List[PRLineIn], db: Session = Depends(get_db)):
    r = db.get(PurchaseRequest, rid)
    if not r:
        raise HTTPException(404, "Not found")
    db.query(PurchaseRequestLine).filter(PurchaseRequestLine.request_id == rid).delete()
    for ln in lines:
        item_name = ""
        if ln.item_id:
            it = db.get(Item, ln.item_id)
            item_name = it.name if it else ""
        l = PurchaseRequestLine(
            request_id=rid,
            item_id=ln.item_id,
            description=ln.description or item_name,
            quantity=ln.quantity,
            unit_price=ln.unit_price,
            notes=ln.notes,
        )
        db.add(l)
    db.commit(); db.refresh(r)
    return _pr_out(r)
