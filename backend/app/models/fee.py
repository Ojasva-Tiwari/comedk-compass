import uuid
from typing import Optional
from decimal import Decimal
from sqlalchemy import Integer, String, Numeric, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.app.core.enums import RecordStatus

class FeeRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "fee_records"

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
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    total_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tuition_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    other_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=RecordStatus.VALIDATED.value,
        nullable=False,
        index=True
    )

    source_version = relationship("SourceVersion", back_populates="fee_records")
    college = relationship("College", back_populates="fee_records")
    branch = relationship("Branch", back_populates="fee_records")

    __table_args__ = (
        Index("idx_fee_records_lookup", "academic_year", "college_id", "status"),
    )
