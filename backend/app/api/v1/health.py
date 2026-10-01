from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text

from backend.app.database import get_db
from backend.app.config import settings
from backend.app.core.enums import RecordStatus, RunStatus, ValidationSeverity
from backend.app.core.security import verify_admin_key
from backend.app.schemas.health import HealthResponse, DataHealthResponse, IngestionRunSummary
from backend.app.models import (
    College,
    Branch,
    CutoffRecord,
    SeatRecord,
    FeeRecord,
    Source,
    SourceVersion,
    IngestionRun,
    ValidationError
)

router = APIRouter(tags=["Health & Monitoring"])

@router.get("/health/live", summary="Process Liveness Probe")
def get_liveness():
    """Liveness probe: verifies the FastAPI application process is alive.
    MUST NOT query PostgreSQL or any external dependency.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc),
        "environment": settings.APP_ENV,
    }

@router.get("/health/ready", summary="Dependency Readiness Probe")
def get_readiness(db: Session = Depends(get_db)):
    """Readiness probe: verifies the application can serve traffic by checking
    PostgreSQL connectivity via a lightweight SELECT 1.
    """
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc),
            "environment": settings.APP_ENV,
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )

@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)):
    """Legacy compatibility health endpoint."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unhealthy"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable",
        )

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        environment=settings.APP_ENV,
        database=db_status
    )

@router.get("/data-health", response_model=DataHealthResponse)
def get_data_health(
    db: Session = Depends(get_db),
    _: str = Depends(verify_admin_key)
):

    col_count = db.scalar(select(func.count()).select_from(College)) or 0
    br_count = db.scalar(select(func.count()).select_from(Branch)) or 0
    cutoff_count = db.scalar(
        select(func.count()).select_from(CutoffRecord).where(CutoffRecord.status == RecordStatus.PUBLISHED.value)
    ) or 0
    seat_count = db.scalar(
        select(func.count()).select_from(SeatRecord).where(SeatRecord.status == RecordStatus.PUBLISHED.value)
    ) or 0
    fee_count = db.scalar(
        select(func.count()).select_from(FeeRecord).where(FeeRecord.status == RecordStatus.PUBLISHED.value)
    ) or 0
    source_count = db.scalar(select(func.count()).select_from(Source)) or 0
    version_count = db.scalar(select(func.count()).select_from(SourceVersion)) or 0

    pending_count = db.scalar(
        select(func.count()).select_from(SourceVersion).where(
            SourceVersion.processing_status.in_([
                RecordStatus.DISCOVERED.value,
                RecordStatus.DOWNLOADED.value,
                RecordStatus.PARSED.value
            ])
        )
    ) or 0

    rejected_count = db.scalar(
        select(func.count()).select_from(SourceVersion).where(
            SourceVersion.processing_status == RecordStatus.REJECTED.value
        )
    ) or 0

    warnings_anomalies = db.scalar(
        select(func.count()).select_from(ValidationError).where(
            ValidationError.severity.in_([ValidationSeverity.WARNING.value, ValidationSeverity.ERROR.value])
        )
    ) or 0

    latest_success_run = db.execute(
        select(IngestionRun).where(
            IngestionRun.status.in_([RunStatus.SUCCESS.value, RunStatus.PARTIAL_SUCCESS.value])
        ).order_by(IngestionRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    current_run = db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    recent_runs_db = db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(5)
    ).scalars().all()

    runs_summary = [
        IngestionRunSummary(
            id=str(r.id),
            started_at=r.started_at,
            finished_at=r.finished_at,
            status=r.status,
            source_count=r.source_count,
            published_count=r.published_count,
            rejected_count=r.rejected_count,
            validation_error_count=r.validation_error_count,
            anomaly_count=r.anomaly_count
        ) for r in recent_runs_db
    ]

    type_counts = db.execute(
        select(College.institution_type, func.count(College.id))
        .group_by(College.institution_type)
    ).all()
    colleges_by_type = {t: c for t, c in type_counts}

    br_type_counts = db.execute(
        select(Branch.program_type, func.count(Branch.id))
        .where(Branch.is_canonical == True)
        .group_by(Branch.program_type)
    ).all()
    branches_by_type = {t: c for t, c in br_type_counts}

    return DataHealthResponse(
        college_count=col_count,
        branch_count=br_count,
        cutoff_record_count=cutoff_count,
        seat_record_count=seat_count,
        fee_record_count=fee_count,
        source_count=source_count,
        source_version_count=version_count,
        latest_successful_ingestion=latest_success_run.finished_at if latest_success_run else None,
        current_ingestion_status=current_run.status if current_run else "IDLE",
        pending_validation_records=pending_count,
        rejected_records=rejected_count,
        warnings_anomalies_count=warnings_anomalies,
        colleges_by_institution_type=colleges_by_type,
        institution_type_counts=colleges_by_type,
        engineering_college_count=colleges_by_type.get("ENGINEERING", 0),
        architecture_college_count=colleges_by_type.get("ARCHITECTURE", 0),
        medical_college_count=colleges_by_type.get("MEDICAL", 0),
        dental_college_count=colleges_by_type.get("DENTAL", 0),
        canonical_engineering_branch_count=branches_by_type.get("ENGINEERING", 0),
        branches_by_program_type=branches_by_type,
        recent_runs=runs_summary
    )
