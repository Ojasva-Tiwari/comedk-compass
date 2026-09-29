import uuid
from typing import Optional
from sqlalchemy import Integer, String, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.app.core.enums import RecordStatus

class CutoffRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cutoff_records"

    source_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    college_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    round_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counselling_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    opening_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    closing_rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    row_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=RecordStatus.VALIDATED.value,
        nullable=False,
        index=True
    )

    source_version = relationship("SourceVersion", back_populates="cutoff_records")
    college = relationship("College", back_populates="cutoff_records")
    branch = relationship("Branch", back_populates="cutoff_records")
    category = relationship("Category", back_populates="cutoff_records")
    round = relationship("CounsellingRound", back_populates="cutoff_records")

    __table_args__ = (
        CheckConstraint("closing_rank > 0", name="chk_cutoff_closing_rank_positive"),
        Index(
            "idx_cutoff_unique_logical_record",
            "college_id",
            "branch_id",
            "category_id",
            "round_id",
            "academic_year",
            "source_version_id",
            unique=True
        ),
        Index("idx_cutoff_filter_lookup", "academic_year", "round_id", "status"),
    )
