"""Prediction Service for COMEDK Compass (Stage 3.4).

Provides service-layer orchestration for closing rank predictions:
- Resolves college and branch entities.
- Resolves branch aliases to canonical branch identities.
- Validates category quotas, program types, and counselling rounds.
- Enforces strict round safety (rejecting manufactured R2, isolating KKR_SPECIAL).
- Invokes the evidence-grounded ClosingRankPredictionEngine.
- Strictly read-only execution: zero database mutations.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from backend.app.core.enums import ProgramType
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.prediction.engine import ClosingRankPredictionEngine
from backend.app.prediction.schemas import (
    PredictionRequest,
    PredictionResult,
    ColdStartReason,
)


class PredictionNotFoundError(Exception):
    """Raised when a requested college or branch is not found in the database."""

    def __init__(self, message: str, entity: str = "entity"):
        super().__init__(message)
        self.message = message
        self.entity = entity


class PredictionValidationError(Exception):
    """Raised when prediction parameters are malformed, incompatible, or violate round safety."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PredictionService:
    """Service layer orchestrating validated closing rank predictions."""

    def __init__(self, db: Session):
        self.db = db
        self.engine = ClosingRankPredictionEngine(db)

    def predict(self, request: PredictionRequest) -> PredictionResult:
        """Validate request parameters, resolve canonical identities, and generate prediction."""
        # 1. Resolve college
        college = self.db.query(College).filter(College.id == request.college_id).first()
        if not college:
            raise PredictionNotFoundError(
                f"College with ID '{request.college_id}' does not exist in the database.",
                entity="college",
            )

        # 2. Resolve branch
        branch = self.db.query(Branch).filter(Branch.id == request.branch_id).first()
        if not branch:
            raise PredictionNotFoundError(
                f"Branch with ID '{request.branch_id}' does not exist in the database.",
                entity="branch",
            )

        # 3. Resolve canonical branch identity
        canonical_branch = branch
        if not branch.is_canonical and branch.canonical_branch_id:
            resolved = self.db.query(Branch).filter(Branch.id == branch.canonical_branch_id).first()
            if resolved:
                canonical_branch = resolved

        # 4. Validate program_type
        prog = request.program_type.upper()
        if prog not in [ProgramType.ENGINEERING.value, ProgramType.ARCHITECTURE.value]:
            raise PredictionValidationError(
                f"Unsupported program type '{request.program_type}'. Supported program types are: "
                f"{ProgramType.ENGINEERING.value}, {ProgramType.ARCHITECTURE.value}."
            )

        if canonical_branch.program_type != prog:
            raise PredictionValidationError(
                f"Branch '{canonical_branch.code}' ({canonical_branch.name}) belongs to program type "
                f"'{canonical_branch.program_type}', which is incompatible with requested program type '{prog}'."
            )

        # 5. Validate category quota
        cat = request.category.upper()
        if cat not in ["GM", "KKR"]:
            raise PredictionValidationError(
                f"Unsupported category quota '{request.category}'. Supported category quotas are: GM, KKR."
            )

        # 6. Validate round safety
        target_round = request.round.upper()
        if target_round in ["R2", "ROUND_2", "ROUND 2", "ROUND2"]:
            raise PredictionValidationError(
                "Unsupported counselling round 'R2'. Standard R2 is not an official COMEDK general counselling round "
                "(2026 general progression is R1 -> R3 -> R4; historical R2_PHASE2 is strictly isolated to 2023/2024)."
            )

        if target_round == "KKR_SPECIAL":
            raise PredictionValidationError(
                "KKR_SPECIAL is a specialized regional quota round and cannot be requested as a general counselling round."
            )

        if target_round not in ["R1", "R3", "R4", "TERMINAL"]:
            raise PredictionValidationError(
                f"Unsupported counselling round '{request.round}'. "
                f"Supported prediction rounds are: R1, R3, R4, TERMINAL."
            )

        # Architecture program round compatibility
        if prog == ProgramType.ARCHITECTURE.value and target_round not in ["R1", "TERMINAL"]:
            raise PredictionValidationError(
                f"Counselling round '{target_round}' is not applicable to ARCHITECTURE programs. "
                f"Architecture counselling historically consists of R1 or TERMINAL."
            )

        # 7. Validate academic year
        if request.academic_year < 2023:
            raise PredictionValidationError(
                f"Academic year {request.academic_year} is before the official COMEDK dataset baseline (2023)."
            )

        # 8. Construct canonicalized prediction request
        canonical_request = PredictionRequest(
            college_id=college.id,
            branch_id=canonical_branch.id,
            academic_year=request.academic_year,
            round=target_round,
            category=cat,
            program_type=prog,
            model_type=request.model_type,
        )

        # 9. Invoke prediction engine (strictly read-only)
        result = self.engine.predict(canonical_request)

        # Ensure canonical branch ID is explicitly reflected in result
        result.branch_id = canonical_branch.id

        return result
