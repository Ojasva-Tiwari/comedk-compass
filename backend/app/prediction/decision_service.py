"""Candidate Decision Service for COMEDK Compass (Stage 3.7).

Provides an evidence-grounded, neutral candidate rank decision layer:
- Compares candidate rank against validated prediction closing-rank intervals.
- Semantics: Lower numerical rank = better competitive position in COMEDK.
- Neutral evidence states:
  * NUMERICALLY_BELOW_LOWER_BOUND: candidate_rank < lower_bound
  * WITHIN_LOWER_HALF: lower_bound <= candidate_rank <= predicted_closing_rank
  * WITHIN_UPPER_HALF: predicted_closing_rank < candidate_rank <= upper_bound
  * NUMERICALLY_ABOVE_UPPER_BOUND: candidate_rank > upper_bound
  * INSUFFICIENT_EVIDENCE: cold start or unsupported program type (e.g. Architecture)
- Zero admission probability or chance percentages.
- Zero Safe / Target / Reach labels.
- Zero database mutations.
"""

from typing import List, Optional
from uuid import uuid4
from sqlalchemy.orm import Session

from backend.app.core.enums import ProgramType
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.prediction.service import (
    PredictionService,
    PredictionNotFoundError,
    PredictionValidationError,
)
from backend.app.prediction.schemas import (
    CandidateEvidenceState,
    CandidateDecisionRequest,
    CandidateDecisionResponse,
    PredictionRequest,
    PredictionResult,
    ColdStartReason,
    EvidenceStrength,
)


class CandidateDecisionService:
    """Orchestrates candidate rank decision-layer evaluations."""

    def __init__(self, db: Session):
        self.db = db
        self.prediction_service = PredictionService(db)

    def evaluate_decision(self, request: CandidateDecisionRequest) -> CandidateDecisionResponse:
        """Evaluate candidate rank against validated prediction interval in a strictly read-only manner."""
        # 1. Validate candidate rank
        if request.candidate_rank is None or request.candidate_rank <= 0:
            raise PredictionValidationError(
                f"Invalid candidate rank '{request.candidate_rank}'. "
                "Candidate rank must be a strictly positive integer."
            )

        # 2. Check program type safety (Stage 3.7 supports ENGINEERING; ARCHITECTURE fails closed)
        prog = request.program_type.upper()
        if prog not in [ProgramType.ENGINEERING.value, ProgramType.ARCHITECTURE.value]:
            raise PredictionValidationError(
                f"Unsupported program type '{request.program_type}'. Supported program types are: "
                f"{ProgramType.ENGINEERING.value}, {ProgramType.ARCHITECTURE.value}."
            )

        # 3. Normalize round: canonical general counselling rounds are R1, R3, R4.
        # TERMINAL is treated as an alias for the final general round R4.
        raw_round = request.round.strip().upper()
        target_round = "R4" if raw_round == "TERMINAL" else raw_round

        # If Architecture program is requested:
        if prog == ProgramType.ARCHITECTURE.value:
            # Validate college and branch existence first to preserve 404 error semantics
            college = self.db.query(College).filter(College.id == request.college_id).first()
            if not college:
                raise PredictionNotFoundError(
                    f"College with ID '{request.college_id}' does not exist in the database.",
                    entity="college",
                )
            branch = self.db.query(Branch).filter(Branch.id == request.branch_id).first()
            if not branch:
                raise PredictionNotFoundError(
                    f"Branch with ID '{request.branch_id}' does not exist in the database.",
                    entity="branch",
                )
            if branch.program_type != ProgramType.ARCHITECTURE.value:
                raise PredictionValidationError(
                    f"Branch '{branch.code}' ({branch.name}) belongs to program type "
                    f"'{branch.program_type}', which is incompatible with requested program type '{prog}'."
                )

            # Return fail-closed INSUFFICIENT_EVIDENCE response
            return CandidateDecisionResponse(
                decision_id=uuid4(),
                candidate_rank=request.candidate_rank,
                academic_year=request.academic_year,
                college_id=college.id,
                branch_id=branch.id,
                category=request.category.upper(),
                round=target_round,
                program_type=prog,
                prediction_status="INSUFFICIENT_EVIDENCE",
                predicted_closing_rank=None,
                lower_bound=None,
                upper_bound=None,
                prediction_interval=None,
                evidence_state=CandidateEvidenceState.INSUFFICIENT_EVIDENCE,
                explanation=[
                    "The candidate-rank decision layer currently supports ENGINEERING programs only.",
                    "Architecture admissions use separate NATA rank semantics with insufficient historical sample depth to support a calibrated decision boundary.",
                    "No decision classification can be responsibly produced without comparable historical evidence.",
                ],
                evidence_strength=EvidenceStrength.INSUFFICIENT_EVIDENCE,
                observation_count=0,
                latest_comparable_year=None,
                cold_start_reason=ColdStartReason.NO_HISTORICAL_RECORDS,
                model_name="FAIL_CLOSED_HANDLER",
                model_version="v1.0-research",
                dataset_version="2023-2026-v1",
                feature_definition_version="v1.0",
                evidence_trail=[],
            )

        # 4. Build prediction request with normalized round and invoke PredictionService
        # PredictionService handles:
        # - college resolution (404)
        # - branch resolution (404)
        # - branch alias to canonical branch resolution
        # - category validation (400 if invalid)
        # - round safety validation (400 if R2, 400 if KKR_SPECIAL, etc.)
        # - academic year >= 2023
        pred_req = PredictionRequest(
            college_id=request.college_id,
            branch_id=request.branch_id,
            academic_year=request.academic_year,
            round=target_round,
            category=request.category,
            program_type=request.program_type,
            model_type=request.model_type,
        )

        pred_result: PredictionResult = self.prediction_service.predict(pred_req)

        # 5. Handle prediction INSUFFICIENT_EVIDENCE (Cold start or sparse history)
        if pred_result.status == "INSUFFICIENT_EVIDENCE" or pred_result.predicted_closing_rank is None:
            return CandidateDecisionResponse(
                decision_id=uuid4(),
                candidate_rank=request.candidate_rank,
                academic_year=pred_result.academic_year,
                college_id=pred_result.college_id,
                branch_id=pred_result.branch_id,
                category=pred_result.category,
                round=target_round,
                program_type=pred_result.program_type,
                prediction_status="INSUFFICIENT_EVIDENCE",
                predicted_closing_rank=None,
                lower_bound=None,
                upper_bound=None,
                prediction_interval=None,
                evidence_state=CandidateEvidenceState.INSUFFICIENT_EVIDENCE,
                explanation=[
                    "There is not enough comparable historical evidence to produce a responsible decision-layer assessment for this combination.",
                    *pred_result.explanation,
                    "The decision layer fails closed rather than substituting ungrounded approximations.",
                ],
                evidence_strength=pred_result.evidence_strength,
                observation_count=pred_result.observation_count,
                latest_comparable_year=pred_result.latest_comparable_year,
                cold_start_reason=pred_result.cold_start_reason,
                model_name=pred_result.model_name,
                model_version=pred_result.model_version,
                dataset_version=pred_result.dataset_version,
                feature_definition_version=pred_result.feature_definition_version,
                generated_at=pred_result.generated_at,
                evidence_trail=pred_result.evidence_trail,
            )

        # 5. Evaluate candidate rank against prediction interval
        r = request.candidate_rank
        lower = pred_result.lower_bound
        est = pred_result.predicted_closing_rank
        upper = pred_result.upper_bound

        # Guard against malformed bounds if any
        if lower is None or upper is None:
            return CandidateDecisionResponse(
                decision_id=uuid4(),
                candidate_rank=r,
                academic_year=pred_result.academic_year,
                college_id=pred_result.college_id,
                branch_id=pred_result.branch_id,
                category=pred_result.category,
                round=target_round,
                program_type=pred_result.program_type,
                prediction_status="INSUFFICIENT_EVIDENCE",
                predicted_closing_rank=None,
                lower_bound=None,
                upper_bound=None,
                prediction_interval=None,
                evidence_state=CandidateEvidenceState.INSUFFICIENT_EVIDENCE,
                explanation=["Interval bounds are undefined for this prediction."],
                evidence_strength=pred_result.evidence_strength,
                observation_count=pred_result.observation_count,
                latest_comparable_year=pred_result.latest_comparable_year,
                cold_start_reason=pred_result.cold_start_reason,
                model_name=pred_result.model_name,
                model_version=pred_result.model_version,
                dataset_version=pred_result.dataset_version,
                feature_definition_version=pred_result.feature_definition_version,
                generated_at=pred_result.generated_at,
                evidence_trail=pred_result.evidence_trail,
            )

        # Exact boundary evaluation
        # COMEDK rank ordering is inverse: LOWER rank = better competitive position.
        # Boundary inclusivity:
        # A: r < lower -> NUMERICALLY_BELOW_LOWER_BOUND
        # B: lower <= r <= est -> WITHIN_LOWER_HALF
        # C: est < r <= upper -> WITHIN_UPPER_HALF
        # D: r > upper -> NUMERICALLY_ABOVE_UPPER_BOUND
        if r < lower:
            state = CandidateEvidenceState.NUMERICALLY_BELOW_LOWER_BOUND
            explanation = [
                f"Your COMEDK rank ({r:,}) is numerically below the lower bound ({int(round(lower)):,}) of the estimated closing-rank range ({int(round(lower)):,} - {int(round(upper)):,}).",
                "In COMEDK counselling, a lower numerical rank represents a stronger competitive position. In historical observations evaluated by the model, ranks in this position were inside the published closing-rank boundary in the vast majority of cases.",
                f"Based on {pred_result.model_name} with {pred_result.observation_count} historical observation(s).",
                "This is historical evidence based on past allotment trends, not an admission guarantee.",
            ]
        elif r <= est:
            state = CandidateEvidenceState.WITHIN_LOWER_HALF
            explanation = [
                f"Your COMEDK rank ({r:,}) falls between the lower bound ({int(round(lower)):,}) and the estimated closing rank ({int(round(est)):,}).",
                f"This places your rank within the lower (stricter) half of the model's historical uncertainty range ({int(round(lower)):,} - {int(round(upper)):,}).",
                "In historical observations, ranks in this interval were frequently within the eventual closing boundary, though subject to year-over-year round volatility.",
                f"Based on {pred_result.model_name} with {pred_result.observation_count} historical observation(s).",
                "This is historical evidence based on past allotment trends, not an admission guarantee.",
            ]
        elif r <= upper:
            state = CandidateEvidenceState.WITHIN_UPPER_HALF
            explanation = [
                f"Your COMEDK rank ({r:,}) falls between the estimated closing rank ({int(round(est)):,}) and the upper bound ({int(round(upper)):,}).",
                f"This places your rank within the upper (expanded) half of the model's historical uncertainty range ({int(round(lower)):,} - {int(round(upper)):,}), representing higher uncertainty than the lower half.",
                "In historical observations, ranks in this interval required cutoff expansion to fall within the closing boundary.",
                f"Based on {pred_result.model_name} with {pred_result.observation_count} historical observation(s).",
                "This is historical evidence based on past allotment trends, not an admission guarantee.",
            ]
        else:
            state = CandidateEvidenceState.NUMERICALLY_ABOVE_UPPER_BOUND
            explanation = [
                f"Your COMEDK rank ({r:,}) is numerically beyond the upper bound ({int(round(upper)):,}) of the estimated closing-rank range ({int(round(lower)):,} - {int(round(upper)):,}).",
                "In COMEDK counselling, a higher numerical rank represents a weaker competitive position. Historical observations show limited boundary containment for ranks beyond this range.",
                f"Based on {pred_result.model_name} with {pred_result.observation_count} historical observation(s).",
                "This is historical evidence based on past allotment trends, not an admission guarantee.",
            ]

        return CandidateDecisionResponse(
            decision_id=uuid4(),
            candidate_rank=r,
            academic_year=pred_result.academic_year,
            college_id=pred_result.college_id,
            branch_id=pred_result.branch_id,
            category=pred_result.category,
            round=target_round,
            program_type=pred_result.program_type,
            prediction_status=pred_result.status,
            predicted_closing_rank=pred_result.predicted_closing_rank,
            lower_bound=pred_result.lower_bound,
            upper_bound=pred_result.upper_bound,
            prediction_interval=pred_result.prediction_interval,
            evidence_state=state,
            explanation=explanation,
            evidence_strength=pred_result.evidence_strength,
            observation_count=pred_result.observation_count,
            latest_comparable_year=pred_result.latest_comparable_year,
            cold_start_reason=pred_result.cold_start_reason,
            model_name=pred_result.model_name,
            model_version=pred_result.model_version,
            dataset_version=pred_result.dataset_version,
            feature_definition_version=pred_result.feature_definition_version,
            generated_at=pred_result.generated_at,
            evidence_trail=pred_result.evidence_trail,
        )
