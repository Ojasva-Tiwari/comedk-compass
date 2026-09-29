from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from backend.app.models.source import Source, SourceVersion
from backend.app.models.review import IngestionReviewItem
from backend.app.models.ingestion import IngestionRun
from backend.app.core.enums import RecordStatus, ReviewStatus

class SourceHealthService:
    """
    Computes source freshness and ingestion health telemetry across all registered COMEDK sources.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_source_freshness_report(self) -> Dict[str, Any]:
        sources = self.db.execute(select(Source).order_by(Source.source_code)).scalars().all()
        now = datetime.now(timezone.utc)

        source_reports: List[Dict[str, Any]] = []
        for s in sources:
            # Latest source version
            latest_version = self.db.execute(
                select(SourceVersion)
                .where(SourceVersion.source_id == s.id)
                .order_by(desc(SourceVersion.created_at))
            ).scalars().first()

            # Latest published version
            latest_published = self.db.execute(
                select(SourceVersion)
                .where(
                    SourceVersion.source_id == s.id,
                    SourceVersion.processing_status == RecordStatus.PUBLISHED.value
                )
                .order_by(desc(SourceVersion.created_at))
            ).scalars().first()

            # Pending reviews for this source
            pending_reviews = self.db.execute(
                select(func.count(IngestionReviewItem.id)).where(
                    IngestionReviewItem.source_id == s.id,
                    IngestionReviewItem.status == ReviewStatus.PENDING_REVIEW.value
                )
            ).scalar_one()

            # Total version count
            total_versions = self.db.execute(
                select(func.count(SourceVersion.id)).where(SourceVersion.source_id == s.id)
            ).scalar_one()

            # Evaluate health status
            status = "HEALTHY"
            if not s.is_enabled:
                status = "DISABLED"
            elif not s.last_checked_at:
                status = "NEVER_CHECKED"
            elif pending_reviews > 0:
                status = "HAS_REVIEW_ITEMS"
            elif s.last_checked_at and (now - s.last_checked_at).total_seconds() > (s.check_frequency_hours * 3600 * 2):
                status = "STALE"

            source_reports.append({
                "source_id": str(s.id),
                "source_code": s.source_code or s.title,
                "source_name": s.title,
                "url": s.url,
                "authority_level": s.authority_level,
                "is_enabled": s.is_enabled,
                "status": status,
                "check_frequency_hours": s.check_frequency_hours,
                "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
                "last_success_at": s.last_success_at.isoformat() if s.last_success_at else None,
                "last_seen_hash": s.last_seen_hash,
                "latest_document_title": latest_version.source_title if latest_version else None,
                "latest_published_at": latest_published.created_at.isoformat() if latest_published else None,
                "total_versions": total_versions,
                "pending_review_count": pending_reviews,
                "parser_version": s.parser_version or "v1.0.0"
            })

        # Overall summary
        latest_run = self.db.execute(
            select(IngestionRun).order_by(desc(IngestionRun.started_at))
        ).scalars().first()

        total_pending_reviews = self.db.execute(
            select(func.count(IngestionReviewItem.id)).where(
                IngestionReviewItem.status == ReviewStatus.PENDING_REVIEW.value
            )
        ).scalar_one()

        return {
            "sources_count": len(sources),
            "sources": source_reports,
            "total_pending_reviews": total_pending_reviews,
            "latest_run": {
                "id": str(latest_run.id) if latest_run else None,
                "started_at": latest_run.started_at.isoformat() if latest_run else None,
                "status": latest_run.status if latest_run else None,
                "published_count": latest_run.published_count if latest_run else 0,
                "needs_review_count": latest_run.needs_review_count if latest_run else 0,
            } if latest_run else None,
            "evaluated_at": now.isoformat()
        }
