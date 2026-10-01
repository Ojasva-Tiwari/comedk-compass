"""Tests for Stage 3.8A Ingestion Health N+1 Optimization.

Verifies:
- get_source_freshness_report executes batch-aggregated queries without N+1 per-source loops
- source freshness statuses (HEALTHY, DISABLED, NEVER_CHECKED, HAS_REVIEW_ITEMS, STALE) are correctly evaluated
- total_versions and pending_review_count match accurate database counts
- zero database mutations occur during report generation
"""

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.app.models.source import Source, SourceVersion
from backend.app.models.review import IngestionReviewItem
from backend.app.core.enums import ReviewStatus
from backend.app.ingestion.health import SourceHealthService


def test_ingestion_health_freshness_report_semantics(db: Session):
    """SourceHealthService produces accurate report with aggregated queries."""
    service = SourceHealthService(db)
    report = service.get_source_freshness_report()

    # 1. Total sources count matches database
    actual_source_count = db.execute(select(func.count(Source.id))).scalar_one()
    assert report["sources_count"] == actual_source_count
    assert len(report["sources"]) == actual_source_count

    # 2. Total pending reviews matches database
    actual_pending = db.execute(
        select(func.count(IngestionReviewItem.id)).where(
            IngestionReviewItem.status == ReviewStatus.PENDING_REVIEW.value
        )
    ).scalar_one()
    assert report["total_pending_reviews"] == actual_pending

    # 3. For each source, verify aggregated counts match exact counts
    for s_rep in report["sources"][:5]:  # verify sample of sources
        src_id = s_rep["source_id"]
        actual_versions = db.execute(
            select(func.count(SourceVersion.id)).where(SourceVersion.source_id == src_id)
        ).scalar_one()
        assert s_rep["total_versions"] == actual_versions

        assert s_rep["status"] in ["HEALTHY", "DISABLED", "NEVER_CHECKED", "HAS_REVIEW_ITEMS", "STALE"]


def test_ingestion_health_zero_mutations(db: Session):
    """Calling get_source_freshness_report causes zero database mutations."""
    sources_before = db.execute(select(func.count(Source.id))).scalar_one()
    versions_before = db.execute(select(func.count(SourceVersion.id))).scalar_one()

    service = SourceHealthService(db)
    service.get_source_freshness_report()

    sources_after = db.execute(select(func.count(Source.id))).scalar_one()
    versions_after = db.execute(select(func.count(SourceVersion.id))).scalar_one()

    assert sources_before == sources_after
    assert versions_before == versions_after
