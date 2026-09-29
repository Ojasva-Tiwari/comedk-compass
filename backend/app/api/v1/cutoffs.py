import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.app.database import get_db
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.category import Category
from backend.app.models.round import CounsellingRound
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.schemas.cutoff import CutoffRead
from backend.app.schemas.common import PaginatedResponse
from backend.app.core.enums import RecordStatus, InstitutionType, ProgramType

router = APIRouter(prefix="/cutoffs", tags=["Cutoffs"])

@router.get("", response_model=PaginatedResponse[CutoffRead])
def list_cutoffs(
    college_id: Optional[uuid.UUID] = Query(None, description="Filter by college ID"),
    branch_id: Optional[uuid.UUID] = Query(None, description="Filter by branch ID"),
    category_code: Optional[str] = Query(None, description="Filter by category code (e.g. GM, KKR)"),
    round_code: Optional[str] = Query(None, description="Filter by round code (e.g. R1, R3, R4, KKR_SPECIAL)"),
    academic_year: Optional[int] = Query(None, description="Filter by academic year"),
    institution_type: Optional[str] = Query(
        InstitutionType.ENGINEERING.value,
        description="Filter by institution type: ENGINEERING, ARCHITECTURE, or ALL"
    ),
    program_type: Optional[str] = Query(
        ProgramType.ENGINEERING.value,
        description="Filter by program type: ENGINEERING, ARCHITECTURE, DESIGN, or ALL"
    ),
    include_special_rounds: bool = Query(
        False,
        description="Include non-general specialized rounds such as KKR_SPECIAL (default False)"
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    stmt = select(CutoffRecord).where(CutoffRecord.status == RecordStatus.PUBLISHED.value)

    if institution_type and institution_type.upper() != "ALL":
        stmt = stmt.join(College, CutoffRecord.college_id == College.id).where(
            College.institution_type == institution_type.upper()
        )

    if program_type and program_type.upper() != "ALL":
        stmt = stmt.join(Branch, CutoffRecord.branch_id == Branch.id).where(
            Branch.program_type == program_type.upper()
        )

    if college_id:
        stmt = stmt.where(CutoffRecord.college_id == college_id)
    if branch_id:
        stmt = stmt.where(CutoffRecord.branch_id == branch_id)
    if academic_year:
        stmt = stmt.where(CutoffRecord.academic_year == academic_year)
    if category_code:
        stmt = stmt.join(Category).where(Category.code == category_code.upper())

    # Round filtering: by default exclude specialized rounds (KKR_SPECIAL) from general pathway
    if round_code:
        stmt = stmt.join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id).where(
            CounsellingRound.code == round_code.upper()
        )
    elif not include_special_rounds:
        stmt = stmt.join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id).where(
            CounsellingRound.is_general_round.is_(True)
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    items = db.execute(
        stmt.order_by(CutoffRecord.closing_rank.asc()).limit(limit).offset(offset)
    ).scalars().all()

    return PaginatedResponse(
        items=[CutoffRead.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset
    )
