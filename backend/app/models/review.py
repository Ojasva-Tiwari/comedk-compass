import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import String, DateTime, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin, utc_now
from backend.app.core.enums import ReviewStatus, FailureReason

class IngestionReviewItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ingestion_review_items"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    source_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    document_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), default="v1.0.0", nullable=False)
    failure_reason: Mapped[str] = mapped_column(String(100), default=FailureReason.VALIDATION_FAILED.value, nullable=False, index=True)
    validation_errors: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=ReviewStatus.PENDING_REVIEW.value,
        nullable=False,
        index=True
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    source = relationship("Source", back_populates="review_items")
    source_version = relationship("SourceVersion", back_populates="review_items")
    ingestion_run = relationship("IngestionRun", back_populates="review_items")

    __table_args__ = (
        Index("idx_review_items_status_reason", "status", "failure_reason"),
    )
