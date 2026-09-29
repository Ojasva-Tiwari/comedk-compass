from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func

from backend.app.database import get_db
from backend.app.models.source import Source
from backend.app.schemas.source import SourceRead
from backend.app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/sources", tags=["Sources & Provenance"])

@router.get("", response_model=PaginatedResponse[SourceRead])
def list_sources(
    academic_year: Optional[int] = Query(None, description="Filter by academic year"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    stmt = select(Source).options(joinedload(Source.versions))

    if academic_year:
        stmt = stmt.where(Source.academic_year == academic_year)
    if document_type:
        stmt = stmt.where(Source.document_type == document_type)

    count_stmt = select(func.count(Source.id)).select_from(Source)
    if academic_year:
        count_stmt = count_stmt.where(Source.academic_year == academic_year)
    if document_type:
        count_stmt = count_stmt.where(Source.document_type == document_type)

    total = db.scalar(count_stmt) or 0

    items = db.execute(
        stmt.order_by(Source.created_at.desc()).limit(limit).offset(offset)
    ).unique().scalars().all()

    return PaginatedResponse(
        items=[SourceRead.model_validate(s) for s in items],
        total=total,
        limit=limit,
        offset=offset
    )
