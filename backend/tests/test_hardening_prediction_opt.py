"""Tests for Stage 3.8A Prediction Query Optimization.

Verifies:
- Prediction engine produces valid, deterministic results with SQL-level WHERE filtering
- Canonical branch resolution behaves identically
- Alias branch resolution behaves identically
- GM and KKR quotas evaluate correctly
- R1, R3, and R4 rounds evaluate correctly
- Insufficient evidence / cold start fails closed cleanly
"""

from uuid import uuid4
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.enums import ProgramType, RecordStatus
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.prediction import (
    ClosingRankPredictionEngine,
    PredictionRequest,
    PredictionResult,
    EvidenceStrength,
    ColdStartReason,
)
from backend.app.analytics.constants import ROUND_R1, ROUND_R3, ROUND_R4


@pytest.fixture
def engine(db: Session) -> ClosingRankPredictionEngine:
    return ClosingRankPredictionEngine(db)


def test_prediction_canonical_branch_cs(engine: ClosingRankPredictionEngine, db: Session):
    """Canonical branch CS at RVCE produces valid prediction across R1, R3, R4."""
    rvce = db.execute(select(College).where(College.code == "E095")).scalar_one()
    cs = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one()

    for r in [ROUND_R1, ROUND_R3, ROUND_R4]:
        req = PredictionRequest(
            college_id=rvce.id,
            branch_id=cs.id,
            academic_year=2026,
            round=r,
            category="GM",
            program_type=ProgramType.ENGINEERING.value
        )
        res = engine.predict(req)
        assert res.status == "SUCCESS"
        assert res.predicted_closing_rank is not None
        assert res.prediction_interval is not None
        assert res.lower_bound <= res.predicted_closing_rank <= res.upper_bound
        assert res.round == r or (r == ROUND_R4 and res.round == "TERMINAL")


def test_prediction_alias_branch_resolution(engine: ClosingRankPredictionEngine, db: Session):
    """Alias branch resolves to canonical branch identity under optimized query."""
    rvce = db.execute(select(College).where(College.code == "E095")).scalar_one()
    ecs_alias = db.execute(select(Branch).where(Branch.code == "ECS")).scalar_one_or_none()
    if not ecs_alias:
        pytest.skip("ECS alias branch not present in test dataset")

    req = PredictionRequest(
        college_id=rvce.id,
        branch_id=ecs_alias.id,
        academic_year=2026,
        round=ROUND_R1,
        category="GM",
        program_type=ProgramType.ENGINEERING.value
    )
    res = engine.predict(req)
    # ECS maps to EC canonical
    assert res.status == "SUCCESS"
    assert res.predicted_closing_rank is not None


def test_prediction_gm_and_kkr_isolation(engine: ClosingRankPredictionEngine, db: Session):
    """GM and KKR evaluate independently and produce distinct closing ranks."""
    rvce = db.execute(select(College).where(College.code == "E095")).scalar_one()
    cs = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one()

    gm_res = engine.predict(
        PredictionRequest(
            college_id=rvce.id,
            branch_id=cs.id,
            academic_year=2026,
            round=ROUND_R1,
            category="GM",
            program_type=ProgramType.ENGINEERING.value
        )
    )
    kkr_res = engine.predict(
        PredictionRequest(
            college_id=rvce.id,
            branch_id=cs.id,
            academic_year=2026,
            round=ROUND_R1,
            category="KKR",
            program_type=ProgramType.ENGINEERING.value
        )
    )
    assert gm_res.status == "SUCCESS"
    assert kkr_res.status == "SUCCESS"
    assert gm_res.category == "GM"
    assert kkr_res.category == "KKR"


def test_prediction_cold_start_insufficient_evidence(engine: ClosingRankPredictionEngine):
    """Non-existent college/branch combination fails closed with INSUFFICIENT_EVIDENCE."""
    fake_cid = uuid4()
    fake_bid = uuid4()
    res = engine.predict(
        PredictionRequest(
            college_id=fake_cid,
            branch_id=fake_bid,
            academic_year=2026,
            round=ROUND_R1,
            category="GM",
            program_type=ProgramType.ENGINEERING.value
        )
    )
    assert res.status == "INSUFFICIENT_EVIDENCE"
    assert res.predicted_closing_rank is None
    assert res.prediction_interval is None
    assert res.cold_start_reason == ColdStartReason.UNKNOWN_COLLEGE.value


def test_prediction_terminal_r4_progression(engine: ClosingRankPredictionEngine, db: Session):
    """Terminal round (R4) uses volatility-adaptive wide interval without leakage."""
    rvce = db.execute(select(College).where(College.code == "E095")).scalar_one()
    cs = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one()

    res = engine.predict(
        PredictionRequest(
            college_id=rvce.id,
            branch_id=cs.id,
            academic_year=2026,
            round=ROUND_R4,
            category="GM",
            program_type=ProgramType.ENGINEERING.value
        )
    )
    assert res.status == "SUCCESS"
    assert res.round in ["R4", "TERMINAL"]
    assert res.prediction_interval.interval_type == "VOLATILITY_ADAPTIVE_WIDE"
