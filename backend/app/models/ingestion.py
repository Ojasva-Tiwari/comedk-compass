from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, utc_now
from backend.app.core.enums import RunStatus

class IngestionRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ingestion_runs"

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default=RunStatus.RUNNING.value, nullable=False, index=True)
    
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    downloaded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parsed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    published_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    needs_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation_error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    source_versions = relationship("SourceVersion", back_populates="ingestion_run")
    validation_errors = relationship("ValidationError", back_populates="ingestion_run")
