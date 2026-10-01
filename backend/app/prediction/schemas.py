"""Prediction Engine Schemas and Data Contracts for COMEDK Compass (Stage 3.3B).

Strictly defines:
- Output contracts for closing rank predictions (NOT admission probability).
- Candidate eligibility semantics: candidate_rank <= predicted_closing_rank.
- Cold-start fail-closed classifications.
- Evidence trail and uncertainty interval specifications.
- Model and dataset version tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class PredictionState(str, Enum):
    """Supported prediction states conditioned on counselling progression."""
    R1 = "R1"
    R3 = "R3"
    R4_TERMINAL = "R4_TERMINAL"


class CandidateEvidenceState(str, Enum):
    """Supported neutral candidate evidence states relative to prediction interval."""
    NUMERICALLY_BELOW_LOWER_BOUND = "NUMERICALLY_BELOW_LOWER_BOUND"
    WITHIN_LOWER_HALF = "WITHIN_LOWER_HALF"
    WITHIN_UPPER_HALF = "WITHIN_UPPER_HALF"
    NUMERICALLY_ABOVE_UPPER_BOUND = "NUMERICALLY_ABOVE_UPPER_BOUND"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EvidenceStrength(str, Enum):
    """Categorization of evidence depth supporting a prediction."""
    STRONG = "STRONG"                # n >= 3 observations or verified intra-year preceding round
    MODERATE = "MODERATE"            # n == 2 continuous observations
    SPARSE = "SPARSE"                # n == 1 observation only (higher expected error)
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"  # Cold start or zero comparable records


class ColdStartReason(str, Enum):
    """Explicit reasons why a prediction cannot be made (fail-closed)."""
    UNKNOWN_COLLEGE = "UNKNOWN_COLLEGE"
    UNKNOWN_BRANCH = "UNKNOWN_BRANCH"
    UNKNOWN_COMBINATION = "UNKNOWN_COMBINATION"
    UNKNOWN_CATEGORY = "UNKNOWN_CATEGORY"
    NO_HISTORICAL_RECORDS = "NO_HISTORICAL_RECORDS"
    NONE = "NONE"


class BaselineModelType(str, Enum):
    """Candidate prediction models evaluated under walk-forward validation."""
    MODEL_A_LATEST_HISTORICAL = "MODEL_A_LATEST_HISTORICAL"
    MODEL_B_PREVIOUS_YEAR = "MODEL_B_PREVIOUS_YEAR"
    MODEL_C_HISTORICAL_MEAN = "MODEL_C_HISTORICAL_MEAN"
    MODEL_D_HISTORICAL_MEDIAN = "MODEL_D_HISTORICAL_MEDIAN"
    MODEL_E_RECENT_MEDIAN = "MODEL_E_RECENT_MEDIAN"
    MODEL_F_PRECEDING_ROUND = "MODEL_F_PRECEDING_ROUND"
    MODEL_G1_ADDITIVE_MOVEMENT = "MODEL_G1_ADDITIVE_MOVEMENT"
    MODEL_G2_MULTIPLICATIVE_MOVEMENT = "MODEL_G2_MULTIPLICATIVE_MOVEMENT"
    MODEL_H_HYBRID = "MODEL_H_HYBRID"


class IntervalType(str, Enum):
    """Interval calibration strategy."""
    ASYMMETRIC_RELATIVE_EMPIRICAL = "ASYMMETRIC_RELATIVE_EMPIRICAL"
    SYMMETRIC_RELATIVE = "SYMMETRIC_RELATIVE"
    ADDITIVE_EMPIRICAL = "ADDITIVE_EMPIRICAL"
    VOLATILITY_ADAPTIVE_WIDE = "VOLATILITY_ADAPTIVE_WIDE"


class PredictionInterval(BaseModel):
    """Calibrated prediction interval around the point prediction."""
    lower_bound: float = Field(..., description="Estimated lower bound of closing rank (stricter cutoff).")
    upper_bound: float = Field(..., description="Estimated upper bound of closing rank (expanded cutoff).")
    interval_type: IntervalType = Field(..., description="Interval calibration formulation.")
    target_coverage: float = Field(..., description="Target empirical coverage rate (e.g. 0.65 or 0.80).")
    interval_width: float = Field(..., description="Absolute width in ranks (upper_bound - lower_bound).")
    relative_width: float = Field(..., description="Width relative to point forecast (width / predicted_closing_rank).")


class EvidenceItem(BaseModel):
    """Single factual evidence unit contributing to a prediction."""
    source_type: str = Field(..., description="Type of evidence: HISTORICAL_CUTOFF, PRECEDING_ROUND, HISTORICAL_MOVEMENT.")
    academic_year: Optional[int] = Field(None, description="Academic year of the factual record.")
    round_code: Optional[str] = Field(None, description="Counselling round of the factual record.")
    closing_rank: float = Field(..., description="Closing rank observed in factual data.")
    weight: Optional[float] = Field(None, description="Model weight assigned if part of a linear blend.")
    description: str = Field(..., description="Human-readable description of the evidence item.")


class PredictionRequest(BaseModel):
    """Input request parameters for closing rank prediction."""
    college_id: UUID
    branch_id: UUID
    academic_year: int = Field(..., description="Target academic year (e.g. 2026).")
    round: str = Field(..., description="Target round (R1, R3, R4, or TERMINAL).")
    category: str = Field("GM", description="Category quota (GM or KKR).")
    program_type: str = Field("ENGINEERING", description="ENGINEERING or ARCHITECTURE.")
    model_type: Optional[BaselineModelType] = Field(
        None, description="Specific candidate model to evaluate. If None, state-optimal validated model is used."
    )


class PredictionResult(BaseModel):
    """Standardized output contract for closing rank predictions."""
    prediction_id: UUID = Field(default_factory=uuid4, description="Unique prediction instance identifier.")
    academic_year: int = Field(..., description="Target academic year.")
    college_id: UUID = Field(..., description="Canonical college identifier.")
    branch_id: UUID = Field(..., description="Canonical branch identifier.")
    category: str = Field(..., description="Candidate category quota.")
    round: str = Field(..., description="Target counselling round.")
    program_type: str = Field(..., description="Academic program type.")
    
    # Prediction Status & Values
    status: str = Field(..., description="'SUCCESS' or 'INSUFFICIENT_EVIDENCE'.")
    predicted_closing_rank: Optional[float] = Field(
        None, description="Predicted closing rank. candidate_rank <= predicted_closing_rank indicates within boundary."
    )
    prediction_interval: Optional[PredictionInterval] = Field(
        None, description="Calibrated prediction interval reflecting historical volatility."
    )
    lower_bound: Optional[float] = Field(None, description="Convenience lower bound accessor.")
    upper_bound: Optional[float] = Field(None, description="Convenience upper bound accessor.")
    
    # Evidence & Quality Metrics
    evidence_strength: EvidenceStrength = Field(..., description="Strength of historical grounding.")
    observation_count: int = Field(..., description="Number of historical observations supporting prediction.")
    latest_comparable_year: Optional[int] = Field(None, description="Most recent comparable historical year available.")
    cold_start_reason: ColdStartReason = Field(ColdStartReason.NONE, description="Reason if evidence is insufficient.")
    
    # Model Provenance & Metadata
    model_name: str = Field(..., description="Algorithm or baseline name used.")
    model_version: str = Field(..., description="Prediction model version.")
    dataset_version: str = Field(..., description="Historical dataset version used for training.")
    feature_definition_version: str = Field(..., description="Feature definition version.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of generation."
    )
    
    # Transparency & Explainability
    input_parameters: Dict[str, Any] = Field(default_factory=dict, description="Request parameters provided.")
    evidence_trail: List[EvidenceItem] = Field(default_factory=list, description="List of factual evidence used.")
    explanation: List[str] = Field(default_factory=list, description="Evidence-grounded explanatory bullet points.")
    disclaimer: str = Field(
        default=(
            "This closing rank estimate is a research-grounded statistical projection based on official historical "
            "COMEDK allotment records. It is NOT an official COMEDK cutoff, does not guarantee seat allotment, and "
            "must be used for informational planning purposes only."
        ),
        description="Mandatory disclaimer for all closing-rank predictions."
    )


class CandidateDecisionRequest(BaseModel):
    """Input request for candidate rank decision-layer evaluation."""
    candidate_rank: int = Field(..., gt=0, description="Candidate COMEDK rank (strictly positive integer).")
    college_id: UUID = Field(..., description="Target college identifier.")
    branch_id: UUID = Field(..., description="Target branch identifier (canonical or alias).")
    academic_year: int = Field(..., description="Target academic year (e.g. 2026).")
    round: str = Field(..., description="Target counselling round (R1, R3, R4, or TERMINAL).")
    category: str = Field("GM", description="Category quota (GM or KKR).")
    program_type: str = Field("ENGINEERING", description="ENGINEERING or ARCHITECTURE.")
    model_type: Optional[BaselineModelType] = Field(
        None, description="Optional baseline model override for testing/evaluation."
    )


class CandidateDecisionResponse(BaseModel):
    """Standardized output contract for candidate rank decision-layer evaluation."""
    decision_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the decision evaluation.")
    candidate_rank: int = Field(..., description="Candidate rank evaluated.")
    academic_year: int = Field(..., description="Target academic year.")
    college_id: UUID = Field(..., description="College UUID.")
    branch_id: UUID = Field(..., description="Canonical branch UUID.")
    category: str = Field(..., description="Candidate category quota.")
    round: str = Field(..., description="Target counselling round.")
    program_type: str = Field(..., description="Academic program type.")

    # Prediction Information
    prediction_status: str = Field(..., description="'SUCCESS' or 'INSUFFICIENT_EVIDENCE'.")
    predicted_closing_rank: Optional[float] = Field(None, description="Model point estimate.")
    lower_bound: Optional[float] = Field(None, description="Lower bound of uncertainty interval.")
    upper_bound: Optional[float] = Field(None, description="Upper bound of uncertainty interval.")
    prediction_interval: Optional[PredictionInterval] = Field(None, description="Full prediction interval metadata.")

    # Decision Layer Output
    evidence_state: CandidateEvidenceState = Field(..., description="Neutral interval-relative evidence classification.")
    explanation: List[str] = Field(default_factory=list, description="Deterministic explanatory statements.")

    # Evidence & Provenance
    evidence_strength: EvidenceStrength = Field(..., description="Strength of historical grounding.")
    observation_count: int = Field(..., description="Number of historical observations supporting prediction.")
    latest_comparable_year: Optional[int] = Field(None, description="Most recent comparable historical year.")
    cold_start_reason: ColdStartReason = Field(ColdStartReason.NONE, description="Reason if evidence is insufficient.")
    model_name: str = Field(..., description="Prediction model name.")
    model_version: str = Field(..., description="Prediction model version.")
    dataset_version: str = Field(..., description="Historical dataset version.")
    feature_definition_version: str = Field(..., description="Feature definition version.")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of generation."
    )
    evidence_trail: List[EvidenceItem] = Field(default_factory=list, description="Factual evidence records.")

    # Transparency & Disclaimers
    disclaimer: str = Field(
        default=(
            "This candidate-rank evaluation describes numerical position relative to historical "
            "closing-rank estimates derived from official COMEDK allotment data. It is NOT an "
            "admission probability, does not guarantee seat allotment, and does NOT constitute "
            "a recommendation or counselling decision."
        ),
        description="Mandatory disclaimer for candidate decision evaluations."
    )
