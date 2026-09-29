import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func, desc

from backend.app.models.review import IngestionReviewItem
from backend.app.core.enums import ReviewStatus, FailureReason

class ReviewQueueService:
    """
    Manages failed, anomalous, or uncertain ingestion items.
    Enforces that bad or unverified data is held in review and never published automatically.
    """

    def __init__(self, db: Session):
        self.db = db

    def add_review_item(
        self,
        source_id: uuid.UUID,
        document_type: str,
        document_url: str,
        failure_reason: str,
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        source_version_id: Optional[uuid.UUID] = None,
        ingestion_run_id: Optional[uuid.UUID] = None,
        parser_version: str = "v1.0.0",
        review_notes: Optional[str] = None
    ) -> IngestionReviewItem:
        valid_run_id = None
        if ingestion_run_id:
            from backend.app.models.ingestion import IngestionRun
            if self.db.get(IngestionRun, ingestion_run_id):
                valid_run_id = ingestion_run_id

        # Check if an identical pending review item already exists for this document
        existing = self.db.execute(
            select(IngestionReviewItem).where(
                IngestionReviewItem.source_id == source_id,
                IngestionReviewItem.document_url == document_url,
                IngestionReviewItem.status == ReviewStatus.PENDING_REVIEW.value
            )
        ).scalars().first()

        if existing:
            existing.failure_reason = failure_reason
            existing.validation_errors = validation_errors or []
            existing.source_version_id = source_version_id
            existing.ingestion_run_id = valid_run_id
            existing.parser_version = parser_version
            if review_notes:
                existing.review_notes = review_notes
            self.db.commit()
            return existing

        item = IngestionReviewItem(
            source_id=source_id,
            source_version_id=source_version_id,
            ingestion_run_id=valid_run_id,
            document_type=document_type,
            document_url=document_url,
            parser_version=parser_version,
            failure_reason=failure_reason,
            validation_errors=validation_errors or [],
            status=ReviewStatus.PENDING_REVIEW.value,
            review_notes=review_notes
        )
        self.db.add(item)
        self.db.commit()
        return item

    def get_pending_items(self, limit: int = 50) -> List[IngestionReviewItem]:
        return self.db.execute(
            select(IngestionReviewItem)
            .where(IngestionReviewItem.status == ReviewStatus.PENDING_REVIEW.value)
            .order_by(desc(IngestionReviewItem.created_at))
            .limit(limit)
        ).scalars().all()

    def update_item_status(
        self,
        item_id: uuid.UUID,
        new_status: str,
        reviewed_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[IngestionReviewItem]:
        item = self.db.get(IngestionReviewItem, item_id)
        if not item:
            return None

        item.status = new_status
        if reviewed_by:
            item.reviewed_by = reviewed_by
        if notes:
            item.review_notes = f"{item.review_notes or ''} | {notes}".strip(" |")

        self.db.commit()
        return item

    def count_by_status(self) -> Dict[str, int]:
        results = self.db.execute(
            select(IngestionReviewItem.status, func.count(IngestionReviewItem.id))
            .group_by(IngestionReviewItem.status)
        ).all()
        return {r[0]: r[1] for r in results}
