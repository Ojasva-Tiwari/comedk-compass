import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class BranchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    original_name: str
    program_type: str = "ENGINEERING"
    is_canonical: bool = True
    canonical_branch_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
