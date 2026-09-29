import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class CollegeAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    alias: str
    source: str

class CollegeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    original_name: str
    location: Optional[str] = None
    institution_type: str = "ENGINEERING"
    created_at: datetime
    updated_at: datetime

class CollegeDetailRead(CollegeRead):
    aliases: List[CollegeAliasRead] = []
