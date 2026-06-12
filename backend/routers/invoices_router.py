"""
Router: Invoices & Quotes
  GET    /api/invoices
  POST   /api/invoices
  GET    /api/invoices/{id}
  PATCH  /api/invoices/{id}
  DELETE /api/invoices/{id}
  POST   /api/invoices/{id}/lines
  PATCH  /api/invoices/{id}/lines/{lid}
  DELETE /api/invoices/{id}/lines/{lid}
  POST   /api/invoices/{id}/lines/bulk   (replace all lines)
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Invoice, InvoiceLine, Project
from ..schemas import (InvoiceCreate, InvoiceUpdate, InvoiceOut,
                       InvoiceLineCreate, InvoiceLineUpdate, InvoiceLineOut)
from ..auth import get_current_user, require_permission

router = APIRouter(prefix="/api/invoices", tags=["invoices"],
                   dependencies=[Depends(get_current_user)])
_W = Depends(require_permission('items', 'write'))


def _inv_out(inv: Invoice) -> InvoiceOut:
    out = InvoiceOut.model_validate(inv)
    if inv.project:
        out.project_name = inv.project.name
    return out


def _next_number(db: Session, inv_type: str) -> str:
    prefix = "Q" if inv_type == "quote" else "INV"
    count = db.query(Invoice).filter(Invoice.invoice_type == inv_type).count()
    return f"{prefix}-{count + 1:04d}"


@router.get("", response_model=List[InvoiceOut])
def list_invoices(project_id: Optional[int] = None,
                  status: Optional[str] = None,
                  db: Session = Depends(get_db)):
    q = db.query(Invoice).options(joinedload(Invoice.lines), joinedload(Invoice.project))
    if project_id:
        q = q.filter(Invoice.project_id == project_id)
    if status:
        q = q.filter(Invoice.status == status)
    return [_inv_out(i) for i in q.order_by(Invoice.created_at.desc()).all()]


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(body: InvoiceCreate, _w=_W,
                   db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"lines"})
    if not data.get("invoice_number"):
        data["invoice_number"] = _next_number(db, data.get("invoice_type", "invoice"))
    if not data.get("invoice_date"):
        data["invoice_date"] = datetime.utcnow().strftime("%Y-%m-%d")

    inv = Invoice(**data)
    db.add(inv)
    db.flush()  # get inv.id

    for i, line in enumerate(body.lines):
        db.add(InvoiceLine(invoice_id=inv.id, sort_order=i, **line.model_dump(exclude={'sort_order'})))

    db.commit()
    db.refresh(inv)
    return _inv_out(inv)


@router.get("/{inv_id}", response_model=InvoiceOut)
def get_invoice(inv_id: int, db: Session = Depends(get_db)):
    inv = db.query(Invoice).options(joinedload(Invoice.lines), joinedload(Invoice.project)).filter(Invoice.id == inv_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return _inv_out(inv)


@router.patch("/{inv_id}", response_model=InvoiceOut)
def update_invoice(inv_id: int, body: InvoiceUpdate, _w=_W,
                   db: Session = Depends(get_db)):
    inv = db.get(Invoice, inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    updates = body.model_dump(exclude_none=True)
    # Auto-stamp sent_at / paid_at on status changes
    if "status" in updates:
        if updates["status"] == "sent" and not inv.sent_at:
            inv.sent_at = datetime.utcnow()
        if updates["status"] == "paid" and not inv.paid_at:
            inv.paid_at = datetime.utcnow()
    for k, v in updates.items():
        setattr(inv, k, v)
    db.commit()
    db.refresh(inv)
    return _inv_out(inv)


@router.delete("/{inv_id}", status_code=204)
def delete_invoice(inv_id: int, _w=_W, db: Session = Depends(get_db)):
    inv = db.get(Invoice, inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    db.delete(inv)
    db.commit()


# ── Lines ─────────────────────────────────────────────────────────────────────

@router.post("/{inv_id}/lines", response_model=InvoiceLineOut, status_code=201)
def add_line(inv_id: int, body: InvoiceLineCreate, _w=_W,
             db: Session = Depends(get_db)):
    if not db.get(Invoice, inv_id):
        raise HTTPException(404, "Invoice not found")
    # sort_order = next after existing lines
    max_sort = db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv_id).count()
    line = InvoiceLine(invoice_id=inv_id, sort_order=max_sort, **body.model_dump(exclude={'sort_order'}))
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.patch("/{inv_id}/lines/{line_id}", response_model=InvoiceLineOut)
def update_line(inv_id: int, line_id: int, body: InvoiceLineUpdate, _w=_W,
                db: Session = Depends(get_db)):
    line = db.query(InvoiceLine).filter(
        InvoiceLine.id == line_id, InvoiceLine.invoice_id == inv_id
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(line, k, v)
    db.commit()
    db.refresh(line)
    return line


@router.delete("/{inv_id}/lines/{line_id}", status_code=204)
def delete_line(inv_id: int, line_id: int, _w=_W, db: Session = Depends(get_db)):
    line = db.query(InvoiceLine).filter(
        InvoiceLine.id == line_id, InvoiceLine.invoice_id == inv_id
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    db.delete(line)
    db.commit()


@router.put("/{inv_id}/lines", response_model=InvoiceOut)
def replace_lines(inv_id: int, lines: List[InvoiceLineCreate] = Body(...),
                  _w=_W, db: Session = Depends(get_db)):
    """Replace ALL lines on an invoice (used by the invoice editor on save)."""
    inv = db.query(Invoice).options(joinedload(Invoice.lines)).filter(Invoice.id == inv_id).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    # Delete existing
    db.query(InvoiceLine).filter(InvoiceLine.invoice_id == inv_id).delete()
    # Insert new
    for i, line in enumerate(lines):
        db.add(InvoiceLine(invoice_id=inv_id, sort_order=i, **line.model_dump(exclude={'sort_order'})))
    db.commit()
    db.refresh(inv)
    return _inv_out(inv)
