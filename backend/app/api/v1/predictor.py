"""API Endpoints for COMEDK Compass Closing Rank Prediction Engine (Stage 3.4).

Exposes validated closing-rank predictions derived strictly from official historical COMEDK allotment records:
- Predicts CLOSING RANK, not admission probability.
- Candidate eligibility semantics: candidate_rank <= predicted_closing_rank.
- Zero data leakage: chronological walk-forward boundaries.
- Strictly read-only: zero database mutations.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.prediction.service import (
    PredictionService,
    PredictionNotFoundError,
    PredictionValidationError,
)
from backend.app.prediction.schemas import (
    PredictionRequest,
    PredictionResult,
    BaselineModelType,
)

router = APIRouter(prefix="/predictor", tags=["Closing Rank Predictor"])

PREDICTION_RESPONSES = {
    200: {
        "description": "Prediction result generated successfully (either SUCCESS or INSUFFICIENT_EVIDENCE).",
        "content": {
            "application/json": {
                "examples": {
                    "success_prediction": {
                        "summary": "Successful Prediction with Calibrated Interval",
                        "value": {
                            "prediction_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "academic_year": 2026,
                            "college_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "branch_id": "7fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "category": "GM",
                            "round": "R1",
                            "program_type": "ENGINEERING",
                            "status": "SUCCESS",
                            "predicted_closing_rank": 14500.0,
                            "prediction_interval": {
                                "lower_bound": 12325.0,
                                "upper_bound": 22475.0,
                                "interval_type": "ASYMMETRIC_RELATIVE_EMPIRICAL",
                                "target_coverage": 0.70,
                                "interval_width": 10150.0,
                                "relative_width": 0.70,
                            },
                            "lower_bound": 12325.0,
                            "upper_bound": 22475.0,
                            "evidence_strength": "STRONG",
                            "observation_count": 2,
                            "latest_comparable_year": 2024,
                            "cold_start_reason": "NONE",
                            "model_name": "Model A (Latest Historical R1 - 2024)",
                            "model_version": "v1.0-research",
                            "dataset_version": "2023-2026-v1",
                            "feature_definition_version": "v1.0",
                            "generated_at": "2026-10-01T10:00:00Z",
                            "input_parameters": {
                                "college_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "branch_id": "7fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "academic_year": 2026,
                                "round": "R1",
                                "category": "GM",
                                "program_type": "ENGINEERING",
                            },
                            "evidence_trail": [
                                {
                                    "source_type": "HISTORICAL_CUTOFF",
                                    "academic_year": 2024,
                                    "round_code": "R1",
                                    "closing_rank": 14500.0,
                                    "weight": None,
                                    "description": "2024 Round 1 official closing rank: 14,500",
                                }
                            ],
                            "explanation": [
                                "Round 1 prediction generated via Model A (Latest Historical R1 - 2024).",
                                "Grounded by 2 prior historical Round 1 observation(s) from years: 2023, 2024.",
                            ],
                            "disclaimer": (
                                "This closing rank estimate is a research-grounded statistical projection based on official historical "
                                "COMEDK allotment records. It is NOT an official COMEDK cutoff, does not guarantee seat allotment, and "
                                "must be used for informational planning purposes only."
                            ),
                        },
                    },
                    "insufficient_evidence": {
                        "summary": "Fail-Closed Response (Insufficient Evidence)",
                        "value": {
                            "prediction_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                            "academic_year": 2026,
                            "college_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "branch_id": "7fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "category": "GM",
                            "round": "R1",
                            "program_type": "ENGINEERING",
                            "status": "INSUFFICIENT_EVIDENCE",
                            "predicted_closing_rank": None,
                            "prediction_interval": None,
                            "lower_bound": None,
                            "upper_bound": None,
                            "evidence_strength": "INSUFFICIENT_EVIDENCE",
                            "observation_count": 0,
                            "latest_comparable_year": None,
                            "cold_start_reason": "NO_HISTORICAL_RECORDS",
                            "model_name": "FAIL_CLOSED_HANDLER",
                            "model_version": "v1.0-research",
                            "dataset_version": "2023-2026-v1",
                            "feature_definition_version": "v1.0",
                            "generated_at": "2026-10-01T10:00:00Z",
                            "input_parameters": {
                                "college_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "branch_id": "7fa85f64-5717-4562-b3fc-2c963f66afa6",
                                "academic_year": 2026,
                                "round": "R1",
                                "category": "GM",
                                "program_type": "ENGINEERING",
                            },
                            "evidence_trail": [],
                            "explanation": [
                                "No prior published Round 1 cutoffs found for this college and branch combination."
                            ],
                            "disclaimer": (
                                "This closing rank estimate is a research-grounded statistical projection based on official historical "
                                "COMEDK allotment records. It is NOT an official COMEDK cutoff, does not guarantee seat allotment, and "
                                "must be used for informational planning purposes only."
                            ),
                        },
                    },
                }
            }
        },
    },
    400: {
        "description": "Malformed request, unsupported counselling round (e.g. standard R2), or incompatible parameters."
    },
    404: {
        "description": "Requested college or branch entity does not exist in the database."
    },
    422: {
        "description": "Validation error (e.g. malformed UUID, missing required fields)."
    },
}


@router.post(
    "/chances",
    response_model=PredictionResult,
    status_code=status.HTTP_200_OK,
    summary="Predict COMEDK Closing Rank",
    description=(
        "Generates an evidence-grounded closing rank estimate for a specific college, branch, round, "
        "and category quota conditioned on historical COMEDK counselling progression.\n\n"
        "**Candidate Eligibility Semantics**: `candidate_rank <= predicted_closing_rank` indicates "
        "the candidate rank is numerically within the predicted closing-rank boundary.\n\n"
        "**Strict Data Isolation**:\n"
        "- Engineering vs. Architecture programs are evaluated in strict isolation.\n"
        "- GM vs. KKR quotas are strictly partitioned.\n"
        "- 2026 general progression is `R1 -> R3 -> R4`. Standard R2 is never fabricated.\n"
        "- Zero future-year or target-round data leakage.\n"
        "- Cold-start scenarios fail closed deterministically (`status: INSUFFICIENT_EVIDENCE`).\n\n"
        "**Disclaimer**: This is an estimated closing rank derived from historical COMEDK data. "
        "It is not an official COMEDK cutoff or allotment guarantee."
    ),
    responses=PREDICTION_RESPONSES,
)
def predict_closing_rank(
    request: PredictionRequest,
    db: Session = Depends(get_db),
) -> PredictionResult:
    """Execute evidence-grounded closing rank prediction via POST request."""
    service = PredictionService(db)
    try:
        return service.predict(request)
    except PredictionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except PredictionValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.get(
    "/chances",
    response_model=PredictionResult,
    status_code=status.HTTP_200_OK,
    summary="Predict COMEDK Closing Rank (Query Parameters)",
    description=(
        "GET query-parameter alternative for closing rank prediction.\n\n"
        "Accepts identical parameters to `POST /predictor/chances` via URL query parameters."
    ),
    responses=PREDICTION_RESPONSES,
)
def get_closing_rank_prediction(
    college_id: uuid.UUID = Query(..., description="College UUID"),
    branch_id: uuid.UUID = Query(..., description="Branch UUID (canonical or alias)"),
    academic_year: int = Query(..., description="Target academic year (e.g. 2026 or 2027)"),
    round: str = Query(..., description="Target counselling round: R1, R3, R4, or TERMINAL"),
    category: str = Query("GM", description="Category quota: GM or KKR"),
    program_type: str = Query("ENGINEERING", description="Program type: ENGINEERING or ARCHITECTURE"),
    model_type: Optional[BaselineModelType] = Query(None, description="Optional specific candidate model"),
    db: Session = Depends(get_db),
) -> PredictionResult:
    """Execute evidence-grounded closing rank prediction via GET request."""
    request = PredictionRequest(
        college_id=college_id,
        branch_id=branch_id,
        academic_year=academic_year,
        round=round,
        category=category,
        program_type=program_type,
        model_type=model_type,
    )
    service = PredictionService(db)
    try:
        return service.predict(request)
    except PredictionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except PredictionValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
