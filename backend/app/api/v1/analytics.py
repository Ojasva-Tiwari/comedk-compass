"""API Endpoints for COMEDK Compass Historical Cutoff Analytics (2023-2026).

Strictly read-only analytical summaries and empirical metrics.
"""

from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.analytics.service import HistoricalAnalyticsService
from backend.app.analytics.schemas import (
    CoverageSummary,
    YearMovementItem,
    YearMovementAggregate,
    VolatilityMetric,
    VolatilitySummary,
    RoundProgressionMetric,
    RecencyComparison,
    SparsityMetadata,
    HistoricalAnomaly,
    AnalyticsReport,
)

router = APIRouter(prefix="/analytics", tags=["Historical Analytics"])


@router.get("/coverage", response_model=CoverageSummary)
def get_coverage(db: Session = Depends(get_db)):
    """Retrieve historical dataset coverage and observation depth across 2023-2026."""
    service = HistoricalAnalyticsService(db)
    return service.get_coverage_summary()


@router.get("/movement")
def get_movement(
    from_year: int = Query(2024, description="From academic year"),
    to_year: int = Query(2026, description="To academic year"),
    round_scope: str = Query("R1", description="Round scope: R1, TERMINAL, MOCK, etc."),
    program_type: str = Query("ENGINEERING", description="Program type: ENGINEERING, ARCHITECTURE"),
    category: str = Query("GM", description="Category code: GM, KKR"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve year-over-year cutoff movement between two academic years."""
    service = HistoricalAnalyticsService(db)
    items, agg = service.get_yoy_movement(
        from_year=from_year,
        to_year=to_year,
        round_scope=round_scope,
        program_type=program_type,
        category=category,
    )
    paginated_items = items[offset : offset + limit]
    return {
        "aggregate": agg,
        "total_matched": len(items),
        "limit": limit,
        "offset": offset,
        "items": paginated_items,
    }


@router.get("/volatility/summary", response_model=Dict[int, VolatilitySummary])
def get_volatility_summary(
    round_scope: str = Query("TERMINAL", description="Round scope: TERMINAL, R1, etc."),
    program_type: str = Query("ENGINEERING", description="Program type: ENGINEERING, ARCHITECTURE"),
    category: str = Query("GM", description="Category code: GM, KKR"),
    db: Session = Depends(get_db)
):
    """Retrieve empirical historical volatility stratified by observation count (n=2, 3, 4)."""
    service = HistoricalAnalyticsService(db)
    return service.get_volatility_summary_by_n(
        round_scope=round_scope,
        program_type=program_type,
        category=category,
    )


@router.get("/volatility/metrics", response_model=List[VolatilityMetric])
def get_volatility_metrics(
    round_scope: str = Query("R1", description="Round scope: R1, TERMINAL, etc."),
    program_type: str = Query("ENGINEERING", description="Program type: ENGINEERING, ARCHITECTURE"),
    category: str = Query("GM", description="Category code: GM, KKR"),
    min_n: int = Query(2, ge=1, le=4, description="Minimum observation count"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve individual combinations' empirical volatility metrics."""
    service = HistoricalAnalyticsService(db)
    all_metrics = service.get_volatility_metrics(
        round_scope=round_scope,
        program_type=program_type,
        category=category,
        min_n=min_n,
    )
    return all_metrics[offset : offset + limit]


@router.get("/progression", response_model=List[RoundProgressionMetric])
def get_progression(
    academic_year: Optional[int] = Query(None, description="Academic year (optional, default all)"),
    program_type: str = Query("ENGINEERING", description="Program type: ENGINEERING, ARCHITECTURE"),
    category: str = Query("GM", description="Category code: GM, KKR"),
    db: Session = Depends(get_db)
):
    """Retrieve within-year round progression statistics across sequential rounds."""
    service = HistoricalAnalyticsService(db)
    return service.get_round_progression(
        academic_year=academic_year,
        program_type=program_type,
        category=category,
    )


@router.get("/recency", response_model=List[RecencyComparison])
def get_recency(
    anchor_year: int = Query(2026, description="Anchor academic year"),
    round_scope: str = Query("R1", description="Round scope: R1, TERMINAL"),
    program_type: str = Query("ENGINEERING", description="Program type: ENGINEERING, ARCHITECTURE"),
    category: str = Query("GM", description="Category code: GM, KKR"),
    db: Session = Depends(get_db)
):
    """Retrieve recency distance evidence comparing recent vs older years against anchor year."""
    service = HistoricalAnalyticsService(db)
    return service.get_recency_evidence(
        anchor_year=anchor_year,
        round_scope=round_scope,
        program_type=program_type,
        category=category,
    )


@router.get("/sparsity", response_model=List[SparsityMetadata])
def get_sparsity(
    program_type: Optional[str] = Query(None, description="Program type"),
    category: Optional[str] = Query(None, description="Category code"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve observation depth and longitudinal continuity metadata."""
    service = HistoricalAnalyticsService(db)
    all_sparsity = service.get_sparsity_metadata(program_type=program_type, category=category)
    return all_sparsity[offset : offset + limit]


@router.get("/anomalies", response_model=List[HistoricalAnomaly])
def get_anomalies(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve detected factual data anomalies (backward round movement, etc.)."""
    service = HistoricalAnalyticsService(db)
    all_anomalies = service.get_anomalies()
    return all_anomalies[offset : offset + limit]


@router.get("/report", response_model=AnalyticsReport)
def get_report(db: Session = Depends(get_db)):
    """Retrieve complete consolidated historical analytics validation report."""
    service = HistoricalAnalyticsService(db)
    return service.generate_report()
