from sqlalchemy import String, Integer, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base
from backend.app.models.base import UUIDPrimaryKeyMixin, TimestampMixin

class CounsellingRound(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "counselling_rounds"

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_general_round: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    cutoff_records = relationship("CutoffRecord", back_populates="round")
    seat_records = relationship("SeatRecord", back_populates="round")

    __table_args__ = (
        Index("idx_counselling_rounds_year_code", "academic_year", "code", unique=True),
    )
