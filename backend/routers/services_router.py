"""
Router: Services — billable services (fees, touch labor, etc.)
  GET    /api/services
  POST   /api/services
  GET    /api/services/{id}
  PATCH  /api/services/{id}
  DELETE /api/services/{id}
"""
from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Service
from ..schemas import ServiceCreate, ServiceUpdate, ServiceOut
from ..auth import get_current_user, require_permission

router = APIRouter(prefix="/api/services", tags=["services"],
                   dependencies=[Depends(get_current_user)])
_W = Depends(require_permission('items', 'write'))


@router.get("", response_model=List[ServiceOut])
def list_services(db: Session = Depends(get_db)):
    return db.query(Service).order_by(Service.category, Service.name).all()


@router.post("", response_model=ServiceOut, status_code=201)
def create_service(body: ServiceCreate, _w=_W, db: Session = Depends(get_db)):
    svc = Service(**body.model_dump())
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@router.get("/{svc_id}", response_model=ServiceOut)
def get_service(svc_id: int, db: Session = Depends(get_db)):
    svc = db.get(Service, svc_id)
    if not svc:
        raise HTTPException(404, "Service not found")
    return svc


@router.patch("/{svc_id}", response_model=ServiceOut)
def update_service(svc_id: int, body: ServiceUpdate, _w=_W, db: Session = Depends(get_db)):
    svc = db.get(Service, svc_id)
    if not svc:
        raise HTTPException(404, "Service not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(svc, k, v)
    db.commit()
    db.refresh(svc)
    return svc


@router.delete("/{svc_id}", status_code=204)
def delete_service(svc_id: int, _w=_W, db: Session = Depends(get_db)):
    svc = db.get(Service, svc_id)
    if not svc:
        raise HTTPException(404, "Service not found")
    db.delete(svc)
    db.commit()
