from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    environment: str
    database: str

class IngestionRunSummary(BaseModel):
    id: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    source_count: int
    published_count: int
    rejected_count: int
    validation_error_count: int
    anomaly_count: int

class DataHealthResponse(BaseModel):
    college_count: int
    branch_count: int
    cutoff_record_count: int
    seat_record_count: int
    fee_record_count: int
    source_count: int
    source_version_count: int
    latest_successful_ingestion: Optional[datetime] = None
    current_ingestion_status: Optional[str] = None
    pending_validation_records: int
    rejected_records: int
    warnings_anomalies_count: int
    colleges_by_institution_type: Dict[str, int] = {}
    institution_type_counts: Dict[str, int] = {}
    engineering_college_count: int = 0
    architecture_college_count: int = 0
    medical_college_count: int = 0
    dental_college_count: int = 0
    canonical_engineering_branch_count: int = 0
    branches_by_program_type: Dict[str, int] = {}
    recent_runs: List[IngestionRunSummary] = []
