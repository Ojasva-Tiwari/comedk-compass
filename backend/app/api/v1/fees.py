import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.app.database import get_db
from backend.app.models.fee import FeeRecord
from backend.app.models.college import College
from backend.app.schemas.fee import FeeRead
from backend.app.schemas.common import PaginatedResponse
from backend.app.core.enums import RecordStatus, InstitutionType

router = APIRouter(prefix="/fees", tags=["Fees"])

@router.get("", response_model=PaginatedResponse[FeeRead])
def list_fees(
    college_id: Optional[uuid.UUID] = Query(None, description="Filter by college ID"),
    branch_id: Optional[uuid.UUID] = Query(None, description="Filter by branch ID"),
    academic_year: Optional[int] = Query(None, description="Filter by academic year"),
    institution_type: Optional[str] = Query(
        InstitutionType.ENGINEERING.value,
        description="Filter by institution type: ENGINEERING, ARCHITECTURE, or ALL"
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    stmt = select(FeeRecord).where(FeeRecord.status == RecordStatus.PUBLISHED.value)

    if institution_type and institution_type.upper() != "ALL":
        stmt = stmt.join(College, FeeRecord.college_id == College.id).where(
            College.institution_type == institution_type.upper()
        )

    if college_id:
        stmt = stmt.where(FeeRecord.college_id == college_id)
    if branch_id:
        stmt = stmt.where(FeeRecord.branch_id == branch_id)
    if academic_year:
        stmt = stmt.where(FeeRecord.academic_year == academic_year)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    items = db.execute(
        stmt.order_by(FeeRecord.total_fee.desc()).limit(limit).offset(offset)
    ).scalars().all()

    return PaginatedResponse(
        items=[FeeRead.model_validate(f) for f in items],
        total=total,
        limit=limit,
        offset=offset
    )
