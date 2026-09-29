import uuid
from typing import Optional
from sqlalchemy import String, Integer, Boolean, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.app.core.enums import ProgramType

class Branch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "branches"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    program_type: Mapped[str] = mapped_column(
        String(50),
        default=ProgramType.ENGINEERING.value,
        nullable=False,
        index=True
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    canonical_branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    canonical_branch = relationship("Branch", remote_side="Branch.id", backref="aliases")
    college_branches = relationship("CollegeBranch", back_populates="branch", cascade="all, delete-orphan")
    cutoff_records = relationship("CutoffRecord", back_populates="branch")
    seat_records = relationship("SeatRecord", back_populates="branch")
    fee_records = relationship("FeeRecord", back_populates="branch")

    __table_args__ = (
        CheckConstraint(
            "program_type IN ('ENGINEERING', 'ARCHITECTURE', 'DESIGN', 'OTHER')",
            name="chk_branches_program_type"
        ),
        Index("idx_branches_program_canonical", "program_type", "is_canonical"),
    )

class CollegeBranch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "college_branches"

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
    source_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_versions.id", ondelete="SET NULL"),
        nullable=True
    )
    course_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    college = relationship("College", back_populates="college_branches")
    branch = relationship("Branch", back_populates="college_branches")
    source_version = relationship("SourceVersion")

    __table_args__ = (
        Index("idx_college_branch_year", "college_id", "branch_id", "academic_year", unique=True),
    )
