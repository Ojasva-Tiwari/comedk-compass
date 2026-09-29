from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_

from backend.app.database import get_db
from backend.app.models.branch import Branch
from backend.app.schemas.branch import BranchRead
from backend.app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/branches", tags=["Branches"])

@router.get("", response_model=PaginatedResponse[BranchRead])
def list_branches(
    query: Optional[str] = Query(None, description="Search by branch code or name"),
    program_type: Optional[str] = Query(
        "ENGINEERING",
        description="Filter by program type: ENGINEERING, ARCHITECTURE, DESIGN, OTHER, or ALL"
    ),
    is_canonical: Optional[bool] = Query(
        True,
        description="Filter canonical branches (default True, pass None for all)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    stmt = select(Branch)

    if program_type and program_type.upper() != "ALL":
        stmt = stmt.where(Branch.program_type == program_type.upper())

    if is_canonical is not None:
        stmt = stmt.where(Branch.is_canonical == is_canonical)

    if query:
        term = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                Branch.code.ilike(term),
                Branch.name.ilike(term),
                Branch.original_name.ilike(term)
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    items = db.execute(
        stmt.order_by(Branch.code.asc()).limit(limit).offset(offset)
    ).scalars().all()

    return PaginatedResponse(
        items=[BranchRead.model_validate(b) for b in items],
        total=total,
        limit=limit,
        offset=offset
    )
