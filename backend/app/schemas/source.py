import uuid
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class SourceVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_url: str
    document_type: str
    academic_year: int
    counselling_round: Optional[str] = None
    publication_date: Optional[date] = None
    retrieved_at: datetime
    content_hash: str
    file_size_bytes: int
    content_type: str
    parser_version: str
    processing_status: str

class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    url: str
    title: str
    publisher: str
    document_type: str
    academic_year: int
    versions: List[SourceVersionRead] = []
    created_at: datetime
