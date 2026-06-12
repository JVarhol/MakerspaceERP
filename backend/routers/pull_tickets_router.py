"""
Router: Pull Tickets — pick/pull requests for items
  GET    /api/pull-tickets
  POST   /api/pull-tickets
  GET    /api/pull-tickets/{id}
  PATCH  /api/pull-tickets/{id}
  DELETE /api/pull-tickets/{id}
  POST   /api/pull-tickets/{id}/lines
  PATCH  /api/pull-tickets/{id}/lines/{lid}
  DELETE /api/pull-tickets/{id}/lines/{lid}
  POST   /api/pull-tickets/{id}/lines/{lid}/pull   (pull one line)
  POST   /api/pull-tickets/{id}/putback            (return all pulled items)
"""
from __future__ import annotations
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PullTicket, PullTicketLine, Item, ItemLocation, Transaction, ProjectItem
from ..schemas import (PullTicketCreate, PullTicketUpdate, PullTicketOut,
                       PullTicketLineCreate, PullTicketLineOut, PullLineAction)
from ..auth import get_current_user, require_permission

router = APIRouter(tags=["pull-tickets"], dependencies=[Depends(get_current_user)])
_W = Depends(require_permission('items', 'write'))


def _line_out(line: PullTicketLine) -> PullTicketLineOut:
    return PullTicketLineOut(
        id=line.id, ticket_id=line.ticket_id, item_id=line.item_id,
        quantity_needed=line.quantity_needed, quantity_pulled=line.quantity_pulled,
        from_location_id=line.from_location_id, status=line.status, notes=line.notes,
        item_name=line.item.name if line.item else None,
        item_unit=line.item.unit_name if line.item else None,
        from_location_name=line.from_location.name if line.from_location else None,
    )


def _ticket_out(t: PullTicket) -> PullTicketOut:
    return PullTicketOut(
        id=t.id, ticket_number=t.ticket_number, status=t.status,
        pull_type=t.pull_type, to_location_id=t.to_location_id,
        project_id=t.project_id, notes=t.notes, created_by=t.created_by,
        created_at=t.created_at, completed_at=t.completed_at,
        to_location_name=t.to_location.name if t.to_location else None,
        project_name=t.project.name if t.project else None,
        lines=[_line_out(l) for l in t.lines],
    )


def _auto_ticket_number(db: Session) -> str:
    count = db.query(PullTicket).count()
    return f"PT-{count + 1:04d}"


@router.get("/api/pull-tickets", response_model=List[PullTicketOut])
def list_pull_tickets(db: Session = Depends(get_db)):
    tickets = db.query(PullTicket).order_by(PullTicket.created_at.desc()).all()
    return [_ticket_out(t) for t in tickets]


@router.post("/api/pull-tickets", response_model=PullTicketOut, status_code=201)
def create_pull_ticket(body: PullTicketCreate, _w=_W, db: Session = Depends(get_db),
                       current_user=Depends(get_current_user)):
    t = PullTicket(
        pull_type=body.pull_type,
        to_location_id=body.to_location_id,
        project_id=body.project_id,
        notes=body.notes,
        created_by=current_user.username,
        status="open",
    )
    t.ticket_number = body.ticket_number or _auto_ticket_number(db)
    db.add(t)
    db.commit()
    db.refresh(t)
    return _ticket_out(t)


@router.get("/api/pull-tickets/{ticket_id}", response_model=PullTicketOut)
def get_pull_ticket(ticket_id: int, db: Session = Depends(get_db)):
    t = db.get(PullTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Pull ticket not found")
    return _ticket_out(t)


@router.patch("/api/pull-tickets/{ticket_id}", response_model=PullTicketOut)
def update_pull_ticket(ticket_id: int, body: PullTicketUpdate, _w=_W, db: Session = Depends(get_db)):
    t = db.get(PullTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Pull ticket not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _ticket_out(t)


@router.delete("/api/pull-tickets/{ticket_id}", status_code=204)
def delete_pull_ticket(ticket_id: int, _w=_W, db: Session = Depends(get_db)):
    t = db.get(PullTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Pull ticket not found")
    db.delete(t)
    db.commit()


@router.post("/api/pull-tickets/{ticket_id}/lines", response_model=PullTicketLineOut, status_code=201)
def add_line(ticket_id: int, body: PullTicketLineCreate, _w=_W, db: Session = Depends(get_db)):
    t = db.get(PullTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Pull ticket not found")
    item = db.get(Item, body.item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    line = PullTicketLine(
        ticket_id=ticket_id, item_id=body.item_id,
        quantity_needed=body.quantity_needed,
        from_location_id=body.from_location_id,
        notes=body.notes, status="open",
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return _line_out(line)


@router.patch("/api/pull-tickets/{ticket_id}/lines/{line_id}", response_model=PullTicketLineOut)
def update_line(ticket_id: int, line_id: int, body: dict, _w=_W, db: Session = Depends(get_db)):
    line = db.query(PullTicketLine).filter(
        PullTicketLine.id == line_id, PullTicketLine.ticket_id == ticket_id
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    for k, v in body.items():
        if hasattr(line, k):
            setattr(line, k, v)
    db.commit()
    db.refresh(line)
    return _line_out(line)


@router.delete("/api/pull-tickets/{ticket_id}/lines/{line_id}", status_code=204)
def delete_line(ticket_id: int, line_id: int, _w=_W, db: Session = Depends(get_db)):
    line = db.query(PullTicketLine).filter(
        PullTicketLine.id == line_id, PullTicketLine.ticket_id == ticket_id
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    db.delete(line)
    db.commit()


@router.post("/api/pull-tickets/{ticket_id}/lines/{line_id}/pull")
def pull_line(ticket_id: int, line_id: int, body: PullLineAction, _w=_W,
              db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Pull (fulfill) one line of a pull ticket — reduces item inventory."""
    t = db.get(PullTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Pull ticket not found")
    line = db.query(PullTicketLine).filter(
        PullTicketLine.id == line_id, PullTicketLine.ticket_id == ticket_id
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    if line.status == "pulled":
        raise HTTPException(400, "Line already pulled")

    item = db.get(Item, line.item_id)
    if not item:
        raise HTTPException(404, "Item not found")

    remaining = line.quantity_needed - line.quantity_pulled
    qty = body.quantity if body.quantity is not None else remaining
    qty = min(qty, remaining)
    if qty <= 0:
        raise HTTPException(400, "Nothing to pull")

    from_loc_id = body.from_location_id or line.from_location_id

    # Deduct from item total
    before = item.quantity
    item.quantity = round(max(0, before - qty), 6)

    # Deduct from per-location quantity if specified
    if from_loc_id:
        il = db.query(ItemLocation).filter(
            ItemLocation.item_id == line.item_id,
            ItemLocation.location_id == from_loc_id,
        ).first()
        if il:
            il.quantity = round(max(0, (il.quantity or 0) - qty), 6)

    # If assigning to project, add to project items
    if t.pull_type == "assign_project" and t.project_id:
        pi = db.query(ProjectItem).filter(
            ProjectItem.project_id == t.project_id,
            ProjectItem.item_id == line.item_id,
        ).first()
        if pi:
            pi.quantity_needed = round(pi.quantity_needed + qty, 6)
        else:
            db.add(ProjectItem(project_id=t.project_id, item_id=line.item_id,
                               quantity_needed=qty))

    # If moving to new location, add to destination location
    if t.pull_type == "move_location" and t.to_location_id:
        dest_il = db.query(ItemLocation).filter(
            ItemLocation.item_id == line.item_id,
            ItemLocation.location_id == t.to_location_id,
        ).first()
        if dest_il:
            dest_il.quantity = round((dest_il.quantity or 0) + qty, 6)
        else:
            db.add(ItemLocation(item_id=line.item_id, location_id=t.to_location_id, quantity=qty))
        # For move: don't reduce global quantity — add back what was moved
        item.quantity = round(before, 6)

    # Record transaction
    tx_notes = f"Pull ticket {t.ticket_number or t.id}: {t.pull_type}"
    db.add(Transaction(
        item_id=item.id,
        transaction_type="remove" if t.pull_type != "move_location" else "move",
        quantity_change=-qty if t.pull_type != "move_location" else 0,
        quantity_before=before,
        quantity_after=item.quantity,
        from_location_id=from_loc_id,
        to_location_id=t.to_location_id if t.pull_type == "move_location" else None,
        notes=tx_notes,
        created_by=current_user.username,
    ))

    line.quantity_pulled = round(line.quantity_pulled + qty, 6)
    line.from_location_id = from_loc_id or line.from_location_id
    line.status = "pulled" if line.quantity_pulled >= line.quantity_needed else "partial"

    db.commit()

    # Update ticket status
    db.refresh(t)
    all_pulled = all(l.status == "pulled" for l in t.lines)
    any_pulled = any(l.status in ("pulled", "partial") for l in t.lines)
    if all_pulled:
        t.status = "completed"
        t.completed_at = datetime.utcnow()
    elif any_pulled:
        t.status = "partial"
    db.commit()
    db.refresh(t)
    return _ticket_out(t)


def _putback_line(t: PullTicket, line: PullTicketLine, db: Session, username: str) -> bool:
    """Reverse a single pulled line. Returns True if anything was returned."""
    if line.quantity_pulled <= 0:
        return False
    item = db.get(Item, line.item_id)
    if not item:
        return False

    qty = line.quantity_pulled

    if t.pull_type == "move_location":
        if t.to_location_id:
            dest_il = db.query(ItemLocation).filter(
                ItemLocation.item_id == line.item_id,
                ItemLocation.location_id == t.to_location_id,
            ).first()
            if dest_il:
                dest_il.quantity = round(max(0, (dest_il.quantity or 0) - qty), 6)
        if line.from_location_id:
            src_il = db.query(ItemLocation).filter(
                ItemLocation.item_id == line.item_id,
                ItemLocation.location_id == line.from_location_id,
            ).first()
            if src_il:
                src_il.quantity = round((src_il.quantity or 0) + qty, 6)
    else:
        before = item.quantity
        item.quantity = round(before + qty, 6)
        if line.from_location_id:
            il = db.query(ItemLocation).filter(
                ItemLocation.item_id == line.item_id,
                ItemLocation.location_id == line.from_location_id,
            ).first()
            if il:
                il.quantity = round((il.quantity or 0) + qty, 6)
        db.add(Transaction(
            item_id=item.id, transaction_type="add",
            quantity_change=qty, quantity_before=before, quantity_after=item.quantity,
            to_location_id=line.from_location_id,
            notes=f"Put-back: ticket {t.ticket_number or t.id}",
            created_by=username,
        ))

    if t.pull_type == "assign_project" and t.project_id:
        pi = db.query(ProjectItem).filter(
            ProjectItem.project_id == t.project_id,
            ProjectItem.item_id == line.item_id,
        ).first()
        if pi:
            pi.quantity_needed = max(0, pi.quantity_needed - qty)
            if pi.quantity_needed <= 0:
                db.delete(pi)

    line.quantity_pulled = 0
    line.status = "open"
    return True


def _sync_ticket_status(t: PullTicket, db: Session):
    """Re-derive ticket status from its lines after a putback."""
    db.refresh(t)
    all_open    = all(l.status == "open"   for l in t.lines)
    all_pulled  = all(l.status == "pulled" for l in t.lines)
    any_pulled  = any(l.status in ("pulled", "partial") for l in t.lines)
    if all_open:
        t.status = "putback"
        t.completed_at = None
    elif all_pulled:
        t.status = "completed"
    elif any_pulled:
        t.status = "partial"
    else:
        t.status = "open"
        t.completed_at = None


@router.post("/api/pull-tickets/{ticket_id}/lines/{line_id}/putback")
def putback_line(ticket_id: int, line_id: int, _w=_W, db: Session = Depends(get_db),
                 current_user=Depends(get_current_user)):
    """Return a single pulled line back to inventory."""
    t = db.get(PullTicket, ticket_id)
    if not t:
        raise HTTPException(404, "Pull ticket not found")
    line = db.query(PullTicketLine).filter(
        PullTicketLine.id == line_id, PullTicketLine.ticket_id == ticket_id
    ).first()
    if not line:
        raise HTTPException(404, "Line not found")
    if line.quantity_pulled <= 0:
        raise HTTPException(400, "Nothing pulled on this line to return")

    _putback_line(t, line, db, current_user.username)
    _sync_ticket_status(t, db)
    db.commit()
    db.refresh(t)
    return _ticket_out(t)


@router.post("/api/pull-tickets/{ticket_id}/putback")
def putback_ticket(ticket_id: int, _w=_W, db: Session = Depends(get_db),
                   current_user=Depends(get_current_user)):
    """Put back all pulled lines on a ticket."""
    ticket = db.get(PullTicket, ticket_id)
    if not ticket: raise HTTPException(404, "Ticket not found")
    for line in ticket.lines:
        if line.quantity_pulled > 0 and line.from_location_id:
            item = db.get(Item, line.item_id)
            if item:
                item.quantity = round(item.quantity + line.quantity_pulled, 6)
                il = db.query(ItemLocation).filter_by(item_id=line.item_id, location_id=line.from_location_id).first()
                if il:
                    il.quantity = round(il.quantity + line.quantity_pulled, 6)
        line.quantity_pulled = 0
        line.status = "putback"
    ticket.status = "putback"
    db.commit()
    return {"ok": True}