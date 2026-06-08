from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Supplier
from ..schemas import SupplierCreate, SupplierUpdate, SupplierOut
from ..auth import get_current_user, require_permission

router = APIRouter(
    prefix="/api/suppliers",
    tags=["suppliers"],
    dependencies=[Depends(get_current_user)],
)
_W = Depends(require_permission('suppliers', 'write'))


@router.get("", response_model=List[SupplierOut])
def list_suppliers(db: Session = Depends(get_db)):
    return db.query(Supplier).order_by(Supplier.name).all()


@router.get("/{sid}", response_model=SupplierOut)
def get_supplier(sid: int, db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if not s:
        raise HTTPException(404, "Supplier not found")
    return s


@router.post("", response_model=SupplierOut, status_code=201)
def create_supplier(data: SupplierCreate, _w=_W, db: Session = Depends(get_db)):
    s = Supplier(**data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.patch("/{sid}", response_model=SupplierOut)
def update_supplier(sid: int, data: SupplierUpdate, _w=_W, db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if not s:
        raise HTTPException(404, "Supplier not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{sid}", status_code=204)
def delete_supplier(sid: int, _w=_W, db: Session = Depends(get_db)):
    s = db.get(Supplier, sid)
    if not s:
        raise HTTPException(404, "Supplier not found")
    db.delete(s)
    db.commit()
