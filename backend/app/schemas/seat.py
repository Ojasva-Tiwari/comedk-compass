import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class SeatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    college_id: uuid.UUID
    branch_id: uuid.UUID
    category_id: Optional[uuid.UUID] = None
    round_id: Optional[uuid.UUID] = None
    source_version_id: uuid.UUID
    academic_year: int
    total_seats: Optional[int] = None
    vacant_seats: Optional[int] = None
    status: str
    created_at: datetime
