import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.app.database import get_db
from backend.app.models.seat import SeatRecord
from backend.app.models.college import College
from backend.app.models.round import CounsellingRound
from backend.app.schemas.seat import SeatRead
from backend.app.schemas.common import PaginatedResponse
from backend.app.core.enums import RecordStatus, InstitutionType

router = APIRouter(prefix="/seat-records", tags=["Seats"])

@router.get("", response_model=PaginatedResponse[SeatRead])
def list_seat_records(
    college_id: Optional[uuid.UUID] = Query(None, description="Filter by college ID"),
    branch_id: Optional[uuid.UUID] = Query(None, description="Filter by branch ID"),
    academic_year: Optional[int] = Query(None, description="Filter by academic year"),
    round_code: Optional[str] = Query(None, description="Filter by round code (e.g. R1, R3, R4, KKR_SPECIAL)"),
    institution_type: Optional[str] = Query(
        InstitutionType.ENGINEERING.value,
        description="Filter by institution type: ENGINEERING, ARCHITECTURE, or ALL"
    ),
    include_special_rounds: bool = Query(
        False,
        description="Include specialized quota rounds such as KKR_SPECIAL (default False)"
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    stmt = select(SeatRecord).where(SeatRecord.status == RecordStatus.PUBLISHED.value)

    if institution_type and institution_type.upper() != "ALL":
        stmt = stmt.join(College, SeatRecord.college_id == College.id).where(
            College.institution_type == institution_type.upper()
        )

    if college_id:
        stmt = stmt.where(SeatRecord.college_id == college_id)
    if branch_id:
        stmt = stmt.where(SeatRecord.branch_id == branch_id)
    if academic_year:
        stmt = stmt.where(SeatRecord.academic_year == academic_year)

    if round_code:
        stmt = stmt.join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id).where(
            CounsellingRound.code == round_code.upper()
        )
    elif not include_special_rounds:
        stmt = stmt.outerjoin(CounsellingRound, SeatRecord.round_id == CounsellingRound.id).where(
            (SeatRecord.round_id.is_(None)) | (CounsellingRound.is_general_round.is_(True))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    items = db.execute(
        stmt.order_by(SeatRecord.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()

    return PaginatedResponse(
        items=[SeatRead.model_validate(s) for s in items],
        total=total,
        limit=limit,
        offset=offset
    )
