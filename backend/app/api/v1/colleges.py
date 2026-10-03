import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, or_

from backend.app.database import get_db
from backend.app.models.college import College
from backend.app.models.cutoff import CutoffRecord
from backend.app.schemas.college import CollegeRead, CollegeDetailRead
from backend.app.schemas.common import PaginatedResponse
from backend.app.core.enums import InstitutionType

router = APIRouter(prefix="/colleges", tags=["Colleges"])

@router.get("", response_model=PaginatedResponse[CollegeRead])
def list_colleges(
    query: Optional[str] = Query(None, description="Search by name, code or location"),
    location: Optional[str] = Query(None, description="Filter by location city/district"),
    institution_type: Optional[str] = Query(
        InstitutionType.ENGINEERING.value,
        description="Filter by institution type: ENGINEERING, ARCHITECTURE, MEDICAL, DENTAL, or ALL"
    ),
    rank: Optional[int] = Query(None, description="Candidate rank to sort by best attainable cutoff"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    stmt = select(College)

    if institution_type and institution_type.upper() != "ALL":
        stmt = stmt.where(College.institution_type == institution_type.upper())

    if query:
        term = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                College.name.ilike(term),
                College.code.ilike(term),
                College.original_name.ilike(term),
                College.location.ilike(term)
            )
        )

    if location:
        stmt = stmt.where(College.location.ilike(f"%{location.strip()}%"))

    if rank is not None and rank > 0:
        best_attainable = (
            select(
                CutoffRecord.college_id,
                func.min(CutoffRecord.closing_rank).label("best_rank")
            )
            .where(CutoffRecord.closing_rank >= rank)
            .group_by(CutoffRecord.college_id)
            .subquery()
        )
        
        stmt = stmt.outerjoin(best_attainable, College.id == best_attainable.c.college_id)
        
        stmt = stmt.order_by(
            best_attainable.c.best_rank.is_(None),
            best_attainable.c.best_rank.asc(),
            College.code.asc()
        )
    else:
        stmt = stmt.order_by(College.code.asc())

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    items = db.execute(
        stmt.limit(limit).offset(offset)
    ).scalars().all()

    return PaginatedResponse(
        items=[CollegeRead.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset
    )

@router.get("/{college_id}", response_model=CollegeDetailRead)
def get_college(college_id: uuid.UUID, db: Session = Depends(get_db)):
    college = db.execute(
        select(College).options(joinedload(College.aliases)).where(College.id == college_id)
    ).unique().scalar_one_or_none()

    if not college:
        raise HTTPException(status_code=404, detail="College not found")

    return CollegeDetailRead.model_validate(college)
