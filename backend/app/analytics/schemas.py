"""Pydantic schemas and typed data structures for COMEDK Compass Historical Analytics.

All models represent factual historical measurements and aggregations.
No predictive, scoring, or recommendation fields are permitted.
"""

import uuid
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, ConfigDict, Field
from backend.app.analytics.constants import (
    RankDirection,
    ComparabilityStatus,
    VolatilityDataQuality,
    AnomalyType,
)


class ExcludedRecordDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cutoff_id: uuid.UUID
    academic_year: int
    college_code: str
    college_name: str
    branch_code: str
    program_type: str
    category: str
    round_code: str
    status: str
    closing_rank: int
    source_version_id: uuid.UUID
    exclusion_reason: str


class CoverageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    years_available: List[int]
    total_records: int
    published_records: int
    superseded_records: int
    records_per_year: Dict[int, int]
    total_records_per_year: Dict[int, int]
    superseded_records_per_year: Dict[int, int]
    records_per_round: Dict[int, Dict[str, int]]
    records_per_category: Dict[str, int]
    records_per_program_type: Dict[str, int]
    colleges_per_year: Dict[int, int]
    branches_per_year: Dict[int, int]
    observation_depth_counts: Dict[int, int]
    observation_depth_by_program: Dict[str, Dict[int, int]]
    years_observed_patterns: Dict[str, int]
    excluded_records: List[ExcludedRecordDetail] = Field(default_factory=list)


class YearMovementItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    college_id: uuid.UUID
    college_code: str
    college_name: str
    branch_id: uuid.UUID
    branch_code: str
    branch_name: str
    program_type: str
    category: str
    previous_year: int
    previous_round: str
    previous_closing_rank: int
    current_year: int
    current_round: str
    current_closing_rank: int
    absolute_movement: int
    relative_movement: float
    direction: RankDirection
    comparability: ComparabilityStatus
    transition: str


class YearMovementAggregate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transition: str
    from_round: str
    to_round: str
    program_type: str
    category: str
    comparability: ComparabilityStatus
    matched_pairs: int
    median_absolute_movement: float
    mean_absolute_movement: float
    median_relative_movement: float
    mean_relative_movement: float
    earlier_numerically_count: int
    later_numerically_count: int
    unchanged_count: int


class VolatilityMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    college_id: uuid.UUID
    college_code: str
    college_name: str
    branch_id: uuid.UUID
    branch_code: str
    branch_name: str
    program_type: str
    category: str
    round_scope: str
    observation_count: int
    years_observed: List[int]
    missing_years: List[int]
    mean: Optional[float] = None
    median: Optional[float] = None
    standard_deviation: Optional[float] = None
    coefficient_of_variation: Optional[float] = None
    mad: Optional[float] = None
    min_rank: int
    max_rank: int
    rank_range: int
    sequential_absolute_movements: List[int] = Field(default_factory=list)
    sequential_relative_movements: List[float] = Field(default_factory=list)
    volatility_data_quality: VolatilityDataQuality


class VolatilitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    observation_count: int
    combination_count: int
    median_cv: Optional[float] = None
    mean_cv: Optional[float] = None
    min_cv: Optional[float] = None
    max_cv: Optional[float] = None
    median_absolute_movement: Optional[float] = None
    median_relative_movement: Optional[float] = None
    volatility_data_quality: VolatilityDataQuality


class RoundProgressionMetric(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    academic_year: int
    from_round: str
    to_round: str
    program_type: str
    category: str
    matched_pairs: int
    median_absolute_movement: float
    mean_absolute_movement: float
    median_relative_movement: float
    mean_relative_movement: float
    earlier_numerically_count: int
    later_numerically_count: int
    unchanged_count: int


class RecencyComparison(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anchor_year: int
    comparison_round: str
    program_type: str
    category: str
    evaluated_triples: int
    recent_year: int
    older_year: int
    recent_closer_count: int
    older_closer_count: int
    equal_distance_count: int
    recent_closer_percentage: float
    recent_median_absolute_distance: float
    older_median_absolute_distance: float
    recent_median_relative_distance: float
    older_median_relative_distance: float


class SparsityMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    college_id: uuid.UUID
    college_code: str
    branch_id: uuid.UUID
    branch_code: str
    program_type: str
    category: str
    observation_count: int
    years_observed: List[int]
    missing_years: List[int]
    consecutive_transition_count: int
    latest_observation_year: int
    is_sparse: bool


class HistoricalAnomaly(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anomaly_type: AnomalyType
    academic_year: Optional[int] = None
    college_code: Optional[str] = None
    branch_code: Optional[str] = None
    program_type: Optional[str] = None
    category: Optional[str] = None
    from_round: Optional[str] = None
    to_round: Optional[str] = None
    from_rank: Optional[int] = None
    to_rank: Optional[int] = None
    rank_delta: Optional[int] = None
    direction: Optional[RankDirection] = None
    cause: str = "NOT_DETERMINABLE_FROM_AVAILABLE_DATA"
    description: str = "Observed closing rank decreased numerically between rounds."
    details: str


class AnalyticsReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    coverage: CoverageSummary
    volatility_by_n: Dict[int, VolatilitySummary]
    round_progressions: List[RoundProgressionMetric]
    yoy_movements: List[YearMovementAggregate]
    recency_evidence: List[RecencyComparison]
    anomaly_summary: Dict[str, int]
