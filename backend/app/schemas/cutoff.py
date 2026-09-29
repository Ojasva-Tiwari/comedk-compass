import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class CutoffRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    college_id: uuid.UUID
    branch_id: uuid.UUID
    category_id: uuid.UUID
    round_id: uuid.UUID
    source_version_id: uuid.UUID
    academic_year: int
    opening_rank: Optional[int] = None
    closing_rank: int
    page_number: Optional[int] = None
    row_identifier: Optional[str] = None
    status: str
    created_at: datetime
