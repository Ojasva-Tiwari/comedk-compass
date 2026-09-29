import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, utc_now
from backend.app.core.enums import ValidationSeverity

class ValidationError(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "validation_errors"

    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    source_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    error_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(1024), nullable=False)
    context_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(50),
        default=ValidationSeverity.ERROR.value,
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    ingestion_run = relationship("IngestionRun", back_populates="validation_errors")
    source_version = relationship("SourceVersion", back_populates="validation_errors")

    __table_args__ = (
        Index("idx_validation_errors_run_code", "ingestion_run_id", "error_code"),
    )
