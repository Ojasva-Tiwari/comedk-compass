import uuid
from typing import Optional
from sqlalchemy import Integer, String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.app.core.enums import RecordStatus

class SeatRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "seat_records"

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
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    round_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counselling_rounds.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    total_seats: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vacant_seats: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default=RecordStatus.VALIDATED.value,
        nullable=False,
        index=True
    )

    source_version = relationship("SourceVersion", back_populates="seat_records")
    college = relationship("College", back_populates="seat_records")
    branch = relationship("Branch", back_populates="seat_records")
    category = relationship("Category", back_populates="seat_records")
    round = relationship("CounsellingRound", back_populates="seat_records")

    __table_args__ = (
        Index("idx_seat_records_lookup", "academic_year", "college_id", "branch_id", "status"),
    )
