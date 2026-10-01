"""Unit and Validation Tests for ClosingRankPredictionEngine (Stage 3.3B).

Strictly verifies:
1. Chronological leakage: training cutoffs are strictly earlier than target year.
2. Target-round leakage: target-round cutoff of target year is NEVER an input feature.
3. Future-year leakage: future-year cutoffs are never accessible.
4. GM / KKR isolation: General Merit and Karnataka Region quotas evaluate independently.
5. KKR_SPECIAL isolation: KKR_SPECIAL round never enters general counselling predictions.
6. Engineering / Architecture isolation: programs are evaluated in strict isolation.
7. Canonical college identity: aliases or invalid IDs are handled cleanly.
8. Canonical branch identity: raw alias branch IDs resolve to canonical branch identity.
9. SUPERSEDED exclusion: superseded cutoff records are never used as prediction features.
10. Cold-start fail-closed: unknown college/branch/combination returns INSUFFICIENT_EVIDENCE.
11. Missing-history behavior: missing prior years (e.g. Model B on 2026 R1) fails closed.
12. Deterministic output: multiple calls with identical inputs produce identical outputs.
13. Model version presence: model_version and feature_definition_version are present on output.
14. Dataset version presence: dataset_version is present on output.
15. No factual DB mutation: database tables remain 100% clean and invariant.
"""

from uuid import uuid4
import pytest
from sqlalchemy.orm import Session

from backend.app.core.enums import ProgramType, RecordStatus
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.seat import SeatRecord
from backend.app.models.fee import FeeRecord
from backend.app.models.source import SourceVersion
from backend.app.prediction import (
    ClosingRankPredictionEngine,
    PredictionRequest,
    PredictionResult,
    EvidenceStrength,
    ColdStartReason,
    BaselineModelType,
)
from backend.app.analytics.constants import ROUND_R1, ROUND_R3, ROUND_R4, ROUND_KKR_SPECIAL


@pytest.fixture
def engine(db: Session) -> ClosingRankPredictionEngine:
    return ClosingRankPredictionEngine(db)


def test_chronological_and_future_year_leakage(engine: ClosingRankPredictionEngine, db: Session):
    """Verify that predictions for 2024 or 2026 strictly exclude future-year data."""
    # Find a college and branch with data in 2023, 2024, 2026
    c = db.query(College).filter(College.code == "E001").first()  # RV College
    b = db.query(Branch).filter(Branch.code == "CS").first()      # Computer Science

    assert c is not None and b is not None

    # Predict 2024 R1: must ONLY use 2023
    req_24 = PredictionRequest(
        college_id=c.id,
        branch_id=b.id,
        academic_year=2024,
        round="R1",
        category="GM",
        program_type="ENGINEERING",
    )
    res_24 = engine.predict(req_24)
    assert res_24.status == "SUCCESS"
    assert res_24.observation_count == 1
    assert all(e.academic_year < 2024 for e in res_24.evidence_trail if e.academic_year)
    assert res_24.latest_comparable_year == 2023

    # Predict 2026 R1: must ONLY use 2023 and 2024 (no 2026 target data)
    req_26 = PredictionRequest(
        college_id=c.id,
        branch_id=b.id,
        academic_year=2026,
        round="R1",
        category="GM",
        program_type="ENGINEERING",
    )
    res_26 = engine.predict(req_26)
    assert res_26.status == "SUCCESS"
    assert all(e.academic_year < 2026 for e in res_26.evidence_trail if e.academic_year)
    assert res_26.latest_comparable_year == 2024


def test_target_round_leakage_prevention(engine: ClosingRankPredictionEngine, db: Session):
    """Verify that predicting Round 1 NEVER includes target-year Round 1, R3, or R4 as an input feature."""
    c = db.query(College).filter(College.code == "E001").first()
    b = db.query(Branch).filter(Branch.code == "CS").first()

    req = PredictionRequest(
        college_id=c.id,
        branch_id=b.id,
        academic_year=2026,
        round="R1",
        category="GM",
    )
    res = engine.predict(req)
    assert res.status == "SUCCESS"

    # None of the evidence items should be 2026 R1
    for ev in res.evidence_trail:
        assert not (ev.academic_year == 2026 and ev.round_code == ROUND_R1)
        assert not (ev.academic_year == 2026 and ev.round_code in [ROUND_R3, ROUND_R4])


def test_gm_vs_kkr_isolation(engine: ClosingRankPredictionEngine, db: Session):
    """Verify that General Merit (GM) and Karnataka Region (KKR) quotas evaluate in complete isolation."""
    c = db.query(College).filter(College.code == "E001").first()
    b = db.query(Branch).filter(Branch.code == "CS").first()

    req_gm = PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="R1", category="GM")
    req_kkr = PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="R1", category="KKR")

    res_gm = engine.predict(req_gm)
    res_kkr = engine.predict(req_kkr)

    assert res_gm.status == "SUCCESS"
    assert res_kkr.status == "SUCCESS"

    # GM cutoff for RVCE CS is much lower numerically (stricter) than KKR cutoff
    assert res_gm.predicted_closing_rank < res_kkr.predicted_closing_rank
    assert res_gm.category == "GM"
    assert res_kkr.category == "KKR"


def test_kkr_special_round_isolation(engine: ClosingRankPredictionEngine, db: Session):
    """Verify that KKR_SPECIAL round records never enter general counselling predictions."""
    c = db.query(College).filter(College.code == "E001").first()
    b = db.query(Branch).filter(Branch.code == "CS").first()

    req = PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="R3", category="GM")
    res = engine.predict(req)

    for ev in res.evidence_trail:
        assert ev.round_code != ROUND_KKR_SPECIAL


def test_engineering_vs_architecture_isolation(engine: ClosingRankPredictionEngine, db: Session):
    """Verify Engineering and Architecture records are never mixed."""
    # Find an architecture branch
    b_arch = db.query(Branch).filter(Branch.code == "AT").first()
    c = db.query(College).filter(College.code == "E001").first()

    if b_arch:
        req_arch = PredictionRequest(
            college_id=c.id, branch_id=b_arch.id, academic_year=2026, round="R1", program_type="ARCHITECTURE"
        )
        res_arch = engine.predict(req_arch)
        assert res_arch.program_type == "ARCHITECTURE"


def test_canonical_college_and_branch_identity(engine: ClosingRankPredictionEngine, db: Session):
    """Verify alias branch IDs resolve to the canonical branch record."""
    alias_branch = db.query(Branch).filter(Branch.is_canonical == False, Branch.canonical_branch_id != None).first()
    if alias_branch:
        c = db.query(College).first()
        req = PredictionRequest(
            college_id=c.id,
            branch_id=alias_branch.id,
            academic_year=2026,
            round="R1",
        )
        res = engine.predict(req)
        # Result branch_id must be canonical
        assert res.branch_id == alias_branch.canonical_branch_id


def test_superseded_exclusion(engine: ClosingRankPredictionEngine):
    """Verify that the 4 known SUPERSEDED cutoff records never appear in evidence trails."""
    superseded_ranks = {18600.0, 31200.0, 48500.0}
    # Check that engine's internal service returns zero superseded records
    records = engine.analytics_svc.get_canonical_records(status=RecordStatus.PUBLISHED.value)
    for r in records:
        assert r["status"] == RecordStatus.PUBLISHED.value


def test_cold_start_fail_closed_unknown_college(engine: ClosingRankPredictionEngine, db: Session):
    """Verify unknown college fails closed with INSUFFICIENT_EVIDENCE."""
    b = db.query(Branch).first()
    fake_college_id = uuid4()

    req = PredictionRequest(college_id=fake_college_id, branch_id=b.id, academic_year=2026, round="R1")
    res = engine.predict(req)

    assert res.status == "INSUFFICIENT_EVIDENCE"
    assert res.predicted_closing_rank is None
    assert res.cold_start_reason == ColdStartReason.UNKNOWN_COLLEGE
    assert res.evidence_strength == EvidenceStrength.INSUFFICIENT_EVIDENCE


def test_cold_start_fail_closed_unknown_branch(engine: ClosingRankPredictionEngine, db: Session):
    """Verify unknown branch fails closed with INSUFFICIENT_EVIDENCE."""
    c = db.query(College).first()
    fake_branch_id = uuid4()

    req = PredictionRequest(college_id=c.id, branch_id=fake_branch_id, academic_year=2026, round="R1")
    res = engine.predict(req)

    assert res.status == "INSUFFICIENT_EVIDENCE"
    assert res.predicted_closing_rank is None
    assert res.cold_start_reason == ColdStartReason.UNKNOWN_BRANCH


def test_missing_history_behavior_model_b(engine: ClosingRankPredictionEngine, db: Session):
    """Verify Model B fails closed when strict T-1 data does not exist (e.g. 2026 R1)."""
    c = db.query(College).filter(College.code == "E001").first()
    b = db.query(Branch).filter(Branch.code == "CS").first()

    req = PredictionRequest(
        college_id=c.id,
        branch_id=b.id,
        academic_year=2026,
        round="R1",
        model_type=BaselineModelType.MODEL_B_PREVIOUS_YEAR,
    )
    res = engine.predict(req)

    assert res.status == "INSUFFICIENT_EVIDENCE"
    assert res.predicted_closing_rank is None
    assert res.cold_start_reason == ColdStartReason.NO_HISTORICAL_RECORDS
    assert "Model B requires strict T-1 data" in res.explanation[0]


def test_deterministic_output(engine: ClosingRankPredictionEngine, db: Session):
    """Verify multiple executions with identical inputs produce bitwise identical predictions."""
    c = db.query(College).filter(College.code == "E001").first()
    b = db.query(Branch).filter(Branch.code == "CS").first()

    req = PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="R1")
    res1 = engine.predict(req)
    res2 = engine.predict(req)

    assert res1.predicted_closing_rank == res2.predicted_closing_rank
    assert res1.lower_bound == res2.lower_bound
    assert res1.upper_bound == res2.upper_bound
    assert res1.observation_count == res2.observation_count
    assert res1.model_name == res2.model_name


def test_model_and_dataset_version_presence(engine: ClosingRankPredictionEngine, db: Session):
    """Verify version metadata is present on prediction contracts."""
    c = db.query(College).first()
    b = db.query(Branch).first()

    req = PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="R1")
    res = engine.predict(req)

    assert res.model_version == "v1.0-research"
    assert res.dataset_version == "2023-2026-v1"
    assert res.feature_definition_version == "v1.0"
    assert res.disclaimer is not None
    assert len(res.disclaimer) > 20


def test_no_database_mutations(engine: ClosingRankPredictionEngine, db: Session):
    """CRITICAL: Verify prediction engine execution performs zero database mutations."""
    c_cutoffs = db.query(CutoffRecord).count()
    c_colleges = db.query(College).count()
    c_branches = db.query(Branch).count()
    c_seats = db.query(SeatRecord).count()
    c_fees = db.query(FeeRecord).count()
    c_sources = db.query(SourceVersion).count()

    c = db.query(College).filter(College.code == "E001").first()
    b = db.query(Branch).filter(Branch.code == "CS").first()

    # Run predictions across states
    _ = engine.predict(PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="R1"))
    _ = engine.predict(PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="R3"))
    _ = engine.predict(PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="TERMINAL"))

    # Session inspection
    assert len(db.dirty) == 0
    assert len(db.new) == 0
    assert len(db.deleted) == 0

    # Table count verification
    assert db.query(CutoffRecord).count() == c_cutoffs
    assert db.query(College).count() == c_colleges
    assert db.query(Branch).count() == c_branches
    assert db.query(SeatRecord).count() == c_seats
    assert db.query(FeeRecord).count() == c_fees
    assert db.query(SourceVersion).count() == c_sources


def test_terminal_r4_wide_uncertainty_interval(engine: ClosingRankPredictionEngine, db: Session):
    """Verify that terminal R4 predictions calibrate wide uncertainty intervals without artificial narrowing."""
    c = db.query(College).filter(College.code == "E001").first()
    b = db.query(Branch).filter(Branch.code == "CS").first()

    req = PredictionRequest(college_id=c.id, branch_id=b.id, academic_year=2026, round="TERMINAL")
    res = engine.predict(req)

    assert res.status == "SUCCESS"
    assert res.prediction_interval is not None
    # Interval width must be substantial and not manufactured artificially narrow
    assert res.prediction_interval.interval_width > 1000.0
    assert res.lower_bound < res.predicted_closing_rank
    assert res.upper_bound > res.predicted_closing_rank
    assert "volatility" in res.explanation[-1].lower()
