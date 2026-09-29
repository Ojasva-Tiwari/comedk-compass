import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Date, ForeignKey, Index, BigInteger, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin, utc_now
from backend.app.core.enums import RecordStatus, SourceAuthorityLevel

class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sources"

    source_code: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="OFFICIAL_PORTAL", nullable=False)
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), default="COMEDK", nullable=False)
    authority_level: Mapped[str] = mapped_column(
        String(50),
        default=SourceAuthorityLevel.OFFICIAL_PRIMARY.value,
        nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    check_frequency_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    expected_document_types: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    parser_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parser_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    versions = relationship("SourceVersion", back_populates="source", cascade="all, delete-orphan")
    review_items = relationship("IngestionReviewItem", back_populates="source", cascade="all, delete-orphan")

class SourceVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_versions"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ingestion_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_title: Mapped[str] = mapped_column(String(512), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), default="COMEDK", nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    counselling_round: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    publication_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True) # SHA-256
    local_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="application/pdf", nullable=False)
    
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default=RecordStatus.DISCOVERED.value,
        nullable=False,
        index=True
    )

    source = relationship("Source", back_populates="versions")
    ingestion_run = relationship("IngestionRun", back_populates="source_versions")
    validation_errors = relationship("ValidationError", back_populates="source_version")
    review_items = relationship("IngestionReviewItem", back_populates="source_version")
    
    cutoff_records = relationship("CutoffRecord", back_populates="source_version")
    seat_records = relationship("SeatRecord", back_populates="source_version")
    fee_records = relationship("FeeRecord", back_populates="source_version")

    __table_args__ = (
        Index("idx_source_versions_source_hash", "source_id", "content_hash"),
        Index("idx_source_versions_year_round", "academic_year", "counselling_round"),
    )
