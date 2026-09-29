import uuid
from typing import Optional
from sqlalchemy import String, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.app.core.enums import InstitutionType

class College(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "colleges"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    institution_type: Mapped[str] = mapped_column(
        String(50),
        default=InstitutionType.ENGINEERING.value,
        nullable=False,
        index=True
    )

    aliases = relationship("CollegeAlias", back_populates="college", cascade="all, delete-orphan")
    college_branches = relationship("CollegeBranch", back_populates="college", cascade="all, delete-orphan")
    cutoff_records = relationship("CutoffRecord", back_populates="college")
    seat_records = relationship("SeatRecord", back_populates="college")
    fee_records = relationship("FeeRecord", back_populates="college")

    __table_args__ = (
        CheckConstraint(
            "institution_type IN ('ENGINEERING', 'ARCHITECTURE', 'MEDICAL', 'DENTAL')",
            name="chk_colleges_institution_type"
        ),
        Index("idx_colleges_institution_type", "institution_type"),
    )

class CollegeAlias(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "college_aliases"

    college_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("colleges.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    alias: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(255), default="COMEDK", nullable=False)

    college = relationship("College", back_populates="aliases")

    __table_args__ = (
        Index("idx_college_aliases_college_alias", "college_id", "alias", unique=True),
    )
