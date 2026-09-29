import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

class FeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    college_id: uuid.UUID
    branch_id: Optional[uuid.UUID] = None
    source_version_id: uuid.UUID
    academic_year: int
    total_fee: Decimal
    tuition_fee: Optional[Decimal] = None
    other_fee: Optional[Decimal] = None
    currency: str
    status: str
    created_at: datetime
