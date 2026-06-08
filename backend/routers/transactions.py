from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import Transaction
from ..schemas import TransactionOut

from ..auth import get_current_user
router = APIRouter(prefix="/api/transactions", tags=["transactions"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=List[TransactionOut])
def list_transactions(
    limit: int = Query(100, le=500),
    skip: int = 0,
    db: Session = Depends(get_db),
):
    return (
        db.query(Transaction)
        .order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
