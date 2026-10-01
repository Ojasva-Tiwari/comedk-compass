"""Comprehensive Test Suite for Candidate Rank Decision Layer (Stage 3.7).

Strictly tests:
- A. Below lower bound: candidate_rank < lower_bound -> NUMERICALLY_BELOW_LOWER_BOUND
- B. Exactly lower bound: candidate_rank == lower_bound -> WITHIN_LOWER_HALF
- C. Between lower and estimate: lower_bound < candidate_rank < estimate -> WITHIN_LOWER_HALF
- D. Exactly estimate: candidate_rank == estimate -> WITHIN_LOWER_HALF
- E. Between estimate and upper: estimate < candidate_rank < upper_bound -> WITHIN_UPPER_HALF
- F. Exactly upper bound: candidate_rank == upper_bound -> WITHIN_UPPER_HALF
- G. Above upper bound: candidate_rank > upper_bound -> NUMERICALLY_ABOVE_UPPER_BOUND
- H. Lower rank is correctly interpreted as better (inverse rank ordering)
- I. Cold start -> INSUFFICIENT_EVIDENCE
- J. Unknown college -> HTTP 404
- K. Unknown branch -> HTTP 404
- L. Invalid candidate rank -> HTTP 400 / 422
- M. Zero rank rejected -> HTTP 400 / 422
- N. Negative rank rejected -> HTTP 400 / 422
- O. Standard R2 rejected -> HTTP 400
- P. KKR_SPECIAL rejected -> HTTP 400
- Q. GM quota isolation
- R. KKR quota isolation
- S. Architecture isolation (fails closed, does not use Engineering logic)
- T. 2026 R1 uses R1 prediction
- U. 2026 R3 uses R3 prediction
- V. 2026 R4 uses R4 prediction
- W. Prediction provenance preserved
- X. Model version preserved
- Y. Dataset version preserved
- Z. No database mutation (DB record counts identical before and after calls)
- AA. No prediction records created in database
- AB. Deterministic explanation generation
- AC. No probability / chance percentage fields
- AD. No Safe / Target / Reach labels
- AE. No causal vacancy language in outputs
- AF. Canonical branch alias resolution (ECS -> EC)
- AG. Response schema validation against CandidateDecisionResponse
- AH. API endpoint integration test (POST and GET)
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.seat import SeatRecord
from backend.app.models.fee import FeeRecord
from backend.app.models.source import Source, SourceVersion
from backend.app.prediction.schemas import (
    CandidateEvidenceState,
    CandidateDecisionRequest,
    CandidateDecisionResponse,
    PredictionResult,
    PredictionInterval,
    IntervalType,
    EvidenceStrength,
)
from backend.app.prediction.decision_service import CandidateDecisionService


@pytest.fixture
def rv_college(db: Session) -> College:
    col = db.query(College).filter(College.code == "E001").first()
    assert col is not None, "E001 (RV College) must exist in official database"
    return col


@pytest.fixture
def cs_branch(db: Session) -> Branch:
    br = db.query(Branch).filter(Branch.code == "CS").first()
    assert br is not None, "CS (Computer Science) branch must exist in official database"
    return br


@pytest.fixture
def ec_branch(db: Session) -> Branch:
    br = db.query(Branch).filter(Branch.code == "EC").first()
    assert br is not None, "EC (Electronics & Comm) branch must exist in official database"
    return br


@pytest.fixture
def ecs_alias_branch(db: Session) -> Branch:
    br = db.query(Branch).filter(Branch.code == "ECS").first()
    assert br is not None, "ECS alias branch must exist in official database"
    return br


@pytest.fixture
def arch_branch(db: Session) -> Branch:
    br = db.query(Branch).filter(Branch.code == "AT").first()
    assert br is not None, "AT (Architecture) branch must exist in official database"
    return br


@pytest.fixture
def benchmark_prediction(rv_college: College, cs_branch: Branch) -> PredictionResult:
    """Benchmark prediction result with clean round bounds (15000, 21000, 30000) as in Section 3."""
    from backend.app.prediction.schemas import IntervalType, PredictionInterval, EvidenceStrength
    return PredictionResult(
        academic_year=2026,
        college_id=rv_college.id,
        branch_id=cs_branch.id,
        category="GM",
        round="R1",
        program_type="ENGINEERING",
        status="SUCCESS",
        predicted_closing_rank=21000.0,
        lower_bound=15000.0,
        upper_bound=30000.0,
        prediction_interval=PredictionInterval(
            lower_bound=15000.0,
            upper_bound=30000.0,
            interval_type=IntervalType.ASYMMETRIC_RELATIVE_EMPIRICAL,
            target_coverage=0.70,
            interval_width=15000.0,
            relative_width=0.71,
        ),
        evidence_strength=EvidenceStrength.STRONG,
        observation_count=2,
        latest_comparable_year=2024,
        model_name="Model A (Latest Historical R1 - 2024)",
        model_version="v1.0-research",
        dataset_version="2023-2026-v1",
        feature_definition_version="v1.0",
        explanation=[
            "Round 1 prediction generated via Model A (Latest Historical R1 - 2024).",
            "Grounded by 2 prior historical Round 1 observation(s) from years: 2023, 2024.",
        ],
    )


def _get_interval_bounds(client: TestClient, college_id: str, branch_id: str, round_code: str = "R1"):
    res = client.post(
        "/api/v1/predictor/chances",
        json={
            "college_id": college_id,
            "branch_id": branch_id,
            "academic_year": 2026,
            "round": round_code,
            "category": "GM",
            "program_type": "ENGINEERING",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    return data["lower_bound"], data["predicted_closing_rank"], data["upper_bound"]


# -----------------------------------------------------------------------------
# A. Below lower bound: candidate_rank < lower_bound (10000 < 15000)
# -----------------------------------------------------------------------------
def test_a_below_lower_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, rv_college: College, cs_branch: Branch, benchmark_prediction: PredictionResult
):
    from backend.app.prediction.service import PredictionService
    monkeypatch.setattr(PredictionService, "predict", lambda self, req: benchmark_prediction)

    payload = {
        "candidate_rank": 10000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_state"] == CandidateEvidenceState.NUMERICALLY_BELOW_LOWER_BOUND.value
    assert data["candidate_rank"] == 10000
    assert data["lower_bound"] == 15000.0
    assert data["predicted_closing_rank"] == 21000.0
    assert data["upper_bound"] == 30000.0


# -----------------------------------------------------------------------------
# B. Exactly lower bound: candidate_rank == lower_bound (15000 == 15000) -> WITHIN_LOWER_HALF
# -----------------------------------------------------------------------------
def test_b_exactly_lower_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, rv_college: College, cs_branch: Branch, benchmark_prediction: PredictionResult
):
    from backend.app.prediction.service import PredictionService
    monkeypatch.setattr(PredictionService, "predict", lambda self, req: benchmark_prediction)

    payload = {
        "candidate_rank": 15000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_state"] == CandidateEvidenceState.WITHIN_LOWER_HALF.value


# -----------------------------------------------------------------------------
# C. Between lower and estimate: lower < candidate_rank < estimate (18000) -> WITHIN_LOWER_HALF
# -----------------------------------------------------------------------------
def test_c_between_lower_and_estimate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, rv_college: College, cs_branch: Branch, benchmark_prediction: PredictionResult
):
    from backend.app.prediction.service import PredictionService
    monkeypatch.setattr(PredictionService, "predict", lambda self, req: benchmark_prediction)

    payload = {
        "candidate_rank": 18000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_state"] == CandidateEvidenceState.WITHIN_LOWER_HALF.value


# -----------------------------------------------------------------------------
# D. Exactly estimate: candidate_rank == estimate (21000 == 21000) -> WITHIN_LOWER_HALF
# -----------------------------------------------------------------------------
def test_d_exactly_estimate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, rv_college: College, cs_branch: Branch, benchmark_prediction: PredictionResult
):
    from backend.app.prediction.service import PredictionService
    monkeypatch.setattr(PredictionService, "predict", lambda self, req: benchmark_prediction)

    payload = {
        "candidate_rank": 21000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_state"] == CandidateEvidenceState.WITHIN_LOWER_HALF.value


# -----------------------------------------------------------------------------
# E. Between estimate and upper: estimate < candidate_rank < upper (25000) -> WITHIN_UPPER_HALF
# -----------------------------------------------------------------------------
def test_e_between_estimate_and_upper(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, rv_college: College, cs_branch: Branch, benchmark_prediction: PredictionResult
):
    from backend.app.prediction.service import PredictionService
    monkeypatch.setattr(PredictionService, "predict", lambda self, req: benchmark_prediction)

    payload = {
        "candidate_rank": 25000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_state"] == CandidateEvidenceState.WITHIN_UPPER_HALF.value


# -----------------------------------------------------------------------------
# F. Exactly upper bound: candidate_rank == upper (30000 == 30000) -> WITHIN_UPPER_HALF
# -----------------------------------------------------------------------------
def test_f_exactly_upper_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, rv_college: College, cs_branch: Branch, benchmark_prediction: PredictionResult
):
    from backend.app.prediction.service import PredictionService
    monkeypatch.setattr(PredictionService, "predict", lambda self, req: benchmark_prediction)

    payload = {
        "candidate_rank": 30000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_state"] == CandidateEvidenceState.WITHIN_UPPER_HALF.value


# -----------------------------------------------------------------------------
# G. Above upper bound: candidate_rank > upper (35000 > 30000) -> NUMERICALLY_ABOVE_UPPER_BOUND
# -----------------------------------------------------------------------------
def test_g_above_upper_bound(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, rv_college: College, cs_branch: Branch, benchmark_prediction: PredictionResult
):
    from backend.app.prediction.service import PredictionService
    monkeypatch.setattr(PredictionService, "predict", lambda self, req: benchmark_prediction)

    payload = {
        "candidate_rank": 35000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["evidence_state"] == CandidateEvidenceState.NUMERICALLY_ABOVE_UPPER_BOUND.value


# -----------------------------------------------------------------------------
# H. Lower rank is correctly interpreted as better (inverse rank semantics)
# -----------------------------------------------------------------------------
def test_h_lower_rank_is_better_semantics(client: TestClient, rv_college: College, cs_branch: Branch):
    lower, est, upper = _get_interval_bounds(client, str(rv_college.id), str(cs_branch.id))
    rank_better = int(lower) - 50
    rank_worse = int(upper) + 500

    assert rank_better < rank_worse, "Numerically smaller rank must be evaluated as better"

    res_better = client.post(
        "/api/v1/predictor/decision",
        json={
            "candidate_rank": rank_better,
            "college_id": str(rv_college.id),
            "branch_id": str(cs_branch.id),
            "academic_year": 2026,
            "round": "R1",
            "category": "GM",
            "program_type": "ENGINEERING",
        },
    ).json()

    res_worse = client.post(
        "/api/v1/predictor/decision",
        json={
            "candidate_rank": rank_worse,
            "college_id": str(rv_college.id),
            "branch_id": str(cs_branch.id),
            "academic_year": 2026,
            "round": "R1",
            "category": "GM",
            "program_type": "ENGINEERING",
        },
    ).json()

    assert res_better["evidence_state"] == "NUMERICALLY_BELOW_LOWER_BOUND"
    assert res_worse["evidence_state"] == "NUMERICALLY_ABOVE_UPPER_BOUND"
    assert any("lower numerical rank represents a stronger competitive position" in exp for exp in res_better["explanation"])
    assert any("higher numerical rank represents a weaker competitive position" in exp for exp in res_worse["explanation"])


# -----------------------------------------------------------------------------
# I. Cold start -> INSUFFICIENT_EVIDENCE
# -----------------------------------------------------------------------------
def test_i_cold_start_insufficient_evidence(client: TestClient, db: Session, cs_branch: Branch):
    # Find a college with 0 historical cutoffs for CS
    all_colleges = db.query(College).all()
    target_college = None
    for c in all_colleges:
        n_cuts = db.query(CutoffRecord).filter(
            CutoffRecord.college_id == c.id,
            CutoffRecord.branch_id == cs_branch.id,
            CutoffRecord.academic_year < 2026,
        ).count()
        if n_cuts == 0:
            target_college = c
            break

    assert target_college is not None, "A cold-start college/branch must exist"

    payload = {
        "candidate_rank": 5000,
        "college_id": str(target_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["prediction_status"] == "INSUFFICIENT_EVIDENCE"
    assert data["evidence_state"] == "INSUFFICIENT_EVIDENCE"
    assert data["predicted_closing_rank"] is None
    assert data["lower_bound"] is None
    assert data["upper_bound"] is None
    assert data["cold_start_reason"] == "NO_HISTORICAL_RECORDS"


# -----------------------------------------------------------------------------
# J. Unknown college -> HTTP 404
# -----------------------------------------------------------------------------
def test_j_unknown_college_returns_404(client: TestClient, cs_branch: Branch):
    payload = {
        "candidate_rank": 5000,
        "college_id": str(uuid.uuid4()),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 404
    assert "College with ID" in res.json()["detail"]


# -----------------------------------------------------------------------------
# K. Unknown branch -> HTTP 404
# -----------------------------------------------------------------------------
def test_k_unknown_branch_returns_404(client: TestClient, rv_college: College):
    payload = {
        "candidate_rank": 5000,
        "college_id": str(rv_college.id),
        "branch_id": str(uuid.uuid4()),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 404
    assert "Branch with ID" in res.json()["detail"]


# -----------------------------------------------------------------------------
# L. Invalid candidate rank (non-integer, malformed) -> 422
# -----------------------------------------------------------------------------
def test_l_invalid_candidate_rank_returns_422(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": "not-an-integer",
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 422


# -----------------------------------------------------------------------------
# M. Zero rank rejected -> 422 / 400
# -----------------------------------------------------------------------------
def test_m_zero_rank_rejected(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 0,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code in [400, 422]


# -----------------------------------------------------------------------------
# N. Negative rank rejected -> 422 / 400
# -----------------------------------------------------------------------------
def test_n_negative_rank_rejected(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": -1500,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code in [400, 422]


# -----------------------------------------------------------------------------
# O. Standard R2 rejected -> HTTP 400
# -----------------------------------------------------------------------------
def test_o_standard_r2_rejected(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 5000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R2",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 400
    assert "Unsupported counselling round 'R2'" in res.json()["detail"]


# -----------------------------------------------------------------------------
# P. KKR_SPECIAL rejected -> HTTP 400
# -----------------------------------------------------------------------------
def test_p_kkr_special_rejected(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 5000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "KKR_SPECIAL",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 400
    assert "KKR_SPECIAL is a specialized regional quota round" in res.json()["detail"]


# -----------------------------------------------------------------------------
# Q, R. GM / KKR quota isolation
# -----------------------------------------------------------------------------
def test_q_r_gm_kkr_isolation(client: TestClient, rv_college: College, cs_branch: Branch):
    payload_gm = {
        "candidate_rank": 1000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_gm = client.post("/api/v1/predictor/decision", json=payload_gm)
    assert res_gm.status_code == 200
    data_gm = res_gm.json()

    payload_kkr = {
        "candidate_rank": 1000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "KKR",
        "program_type": "ENGINEERING",
    }
    res_kkr = client.post("/api/v1/predictor/decision", json=payload_kkr)
    assert res_kkr.status_code == 200
    data_kkr = res_kkr.json()

    assert data_gm["category"] == "GM"
    assert data_kkr["category"] == "KKR"
    for e in data_gm["evidence_trail"]:
        assert "KKR" not in e["description"]


# -----------------------------------------------------------------------------
# S. Architecture does not use Engineering logic (fails closed)
# -----------------------------------------------------------------------------
def test_s_architecture_fails_closed(client: TestClient, rv_college: College, arch_branch: Branch):
    payload = {
        "candidate_rank": 150,
        "college_id": str(rv_college.id),
        "branch_id": str(arch_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ARCHITECTURE",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["prediction_status"] == "INSUFFICIENT_EVIDENCE"
    assert data["evidence_state"] == "INSUFFICIENT_EVIDENCE"
    assert any("supports ENGINEERING programs only" in line for line in data["explanation"])
    assert any("separate NATA rank semantics" in line for line in data["explanation"])


# -----------------------------------------------------------------------------
# T. 2026 R1 uses R1 prediction
# -----------------------------------------------------------------------------
def test_t_2026_r1_uses_r1_prediction(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 1000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["round"] == "R1"
    assert data["prediction_status"] == "SUCCESS"
    assert "Model A" in data["model_name"]


# -----------------------------------------------------------------------------
# U. 2026 R3 uses R3 prediction
# -----------------------------------------------------------------------------
def test_u_2026_r3_uses_r3_prediction(client: TestClient, rv_college: College, ec_branch: Branch):
    payload = {
        "candidate_rank": 2000,
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R3",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["round"] == "R3"
    assert data["prediction_status"] == "SUCCESS"
    # Grounded by preceding R1
    has_preceding = any(e["source_type"] == "PRECEDING_ROUND" and e["round_code"] == "R1" for e in data["evidence_trail"])
    assert has_preceding


# -----------------------------------------------------------------------------
# V. 2026 R4 uses R4 prediction
# -----------------------------------------------------------------------------
def test_v_2026_r4_uses_r4_prediction(client: TestClient, rv_college: College, ec_branch: Branch):
    payload = {
        "candidate_rank": 3000,
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R4",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["round"] == "R4"
    assert data["prediction_status"] == "SUCCESS"
    assert data["prediction_interval"]["interval_type"] == "VOLATILITY_ADAPTIVE_WIDE"


# -----------------------------------------------------------------------------
# Regression Test: TERMINAL alias normalized to R4
# -----------------------------------------------------------------------------
def test_terminal_alias_normalized_to_r4(client: TestClient, rv_college: College, ec_branch: Branch):
    """TERMINAL is an intentional alias for canonical general round R4 and must normalize to R4."""
    payload_r4 = {
        "candidate_rank": 3000,
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R4",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_r4 = client.post("/api/v1/predictor/decision", json=payload_r4)
    assert res_r4.status_code == 200
    data_r4 = res_r4.json()

    payload_term = {
        "candidate_rank": 3000,
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "TERMINAL",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_term = client.post("/api/v1/predictor/decision", json=payload_term)
    assert res_term.status_code == 200
    data_term = res_term.json()

    # Both must explicitly report canonical general counselling round R4
    assert data_r4["round"] == "R4"
    assert data_term["round"] == "R4"

    # Both must produce identical predictions, bounds, and evidence states
    assert data_r4["predicted_closing_rank"] == data_term["predicted_closing_rank"]
    assert data_r4["lower_bound"] == data_term["lower_bound"]
    assert data_r4["upper_bound"] == data_term["upper_bound"]
    assert data_r4["evidence_state"] == data_term["evidence_state"]


# -----------------------------------------------------------------------------
# W. Prediction provenance preserved
# -----------------------------------------------------------------------------
def test_w_prediction_provenance_preserved(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 1000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["observation_count"] >= 1
    assert data["latest_comparable_year"] in [2023, 2024]
    assert len(data["evidence_trail"]) >= 1


# -----------------------------------------------------------------------------
# X, Y. Model and Dataset version preserved
# -----------------------------------------------------------------------------
def test_x_y_model_and_dataset_version_preserved(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 1000,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res = client.post("/api/v1/predictor/decision", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["model_version"] == "v1.0-research"
    assert data["dataset_version"] == "2023-2026-v1"
    assert data["feature_definition_version"] == "v1.0"


# -----------------------------------------------------------------------------
# Z, AA. No database mutation & no prediction records created
# -----------------------------------------------------------------------------
def test_z_aa_no_database_mutation(client: TestClient, db: Session, rv_college: College, cs_branch: Branch):
    c_cutoffs = db.query(CutoffRecord).count()
    c_seats = db.query(SeatRecord).count()
    c_fees = db.query(FeeRecord).count()
    c_colleges = db.query(College).count()
    c_branches = db.query(Branch).count()
    c_sources = db.query(Source).count()
    c_sv = db.query(SourceVersion).count()

    # Invoke decision endpoint multiple times
    for rk in [500, 1500, 25000]:
        client.post(
            "/api/v1/predictor/decision",
            json={
                "candidate_rank": rk,
                "college_id": str(rv_college.id),
                "branch_id": str(cs_branch.id),
                "academic_year": 2026,
                "round": "R1",
                "category": "GM",
                "program_type": "ENGINEERING",
            },
        )
        client.get(
            f"/api/v1/predictor/decision?candidate_rank={rk}&college_id={rv_college.id}&branch_id={cs_branch.id}&academic_year=2026&round=R1"
        )

    # Invariants must remain 100% identical
    assert db.query(CutoffRecord).count() == c_cutoffs
    assert db.query(SeatRecord).count() == c_seats
    assert db.query(FeeRecord).count() == c_fees
    assert db.query(College).count() == c_colleges
    assert db.query(Branch).count() == c_branches
    assert db.query(Source).count() == c_sources
    assert db.query(SourceVersion).count() == c_sv


# -----------------------------------------------------------------------------
# AB. Deterministic explanation generation
# -----------------------------------------------------------------------------
def test_ab_deterministic_explanation(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 800,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res1 = client.post("/api/v1/predictor/decision", json=payload).json()
    res2 = client.post("/api/v1/predictor/decision", json=payload).json()

    assert res1["evidence_state"] == res2["evidence_state"]
    assert res1["explanation"] == res2["explanation"]


# -----------------------------------------------------------------------------
# AC. No probability / chance percentage fields
# -----------------------------------------------------------------------------
def test_ac_no_probability_fields(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 800,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    data = client.post("/api/v1/predictor/decision", json=payload).json()

    forbidden_fields = ["probability", "admission_probability", "chance", "admission_chance", "percentage", "confidence_percentage"]
    for field in forbidden_fields:
        assert field not in data, f"Forbidden field '{field}' present in decision response!"


# -----------------------------------------------------------------------------
# AD. No Safe / Target / Reach labels
# -----------------------------------------------------------------------------
def test_ad_no_safe_target_reach_labels(client: TestClient, rv_college: College, cs_branch: Branch):
    for rk in [100, 1000, 10000, 50000]:
        payload = {
            "candidate_rank": rk,
            "college_id": str(rv_college.id),
            "branch_id": str(cs_branch.id),
            "academic_year": 2026,
            "round": "R1",
            "category": "GM",
            "program_type": "ENGINEERING",
        }
        data = client.post("/api/v1/predictor/decision", json=payload).json()
        assert data["evidence_state"] not in ["SAFE", "TARGET", "REACH"]
        for exp in data["explanation"]:
            assert "safe" not in exp.lower() or "not an admission guarantee" in exp.lower()
            assert "target" not in exp.lower()
            assert "reach" not in exp.lower()


# -----------------------------------------------------------------------------
# AE. No causal vacancy language in outputs
# -----------------------------------------------------------------------------
def test_ae_no_causal_vacancy_claims(client: TestClient, rv_college: College, ec_branch: Branch):
    payload = {
        "candidate_rank": 3000,
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R4",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    data = client.post("/api/v1/predictor/decision", json=payload).json()
    full_text = " ".join(data["explanation"]) + " " + data["disclaimer"]
    assert "vacancy guarantees" not in full_text.lower()
    assert "vacant seats cause" not in full_text.lower()


# -----------------------------------------------------------------------------
# AF. Canonical branch alias resolution (ECS -> EC)
# -----------------------------------------------------------------------------
def test_af_alias_resolution(
    client: TestClient, rv_college: College, ec_branch: Branch, ecs_alias_branch: Branch
):
    payload_alias = {
        "candidate_rank": 2500,
        "college_id": str(rv_college.id),
        "branch_id": str(ecs_alias_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_alias = client.post("/api/v1/predictor/decision", json=payload_alias)
    assert res_alias.status_code == 200
    data_alias = res_alias.json()

    payload_canon = {
        "candidate_rank": 2500,
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_canon = client.post("/api/v1/predictor/decision", json=payload_canon)
    assert res_canon.status_code == 200
    data_canon = res_canon.json()

    # Canonical branch ID reflected in both
    assert data_alias["branch_id"] == str(ec_branch.id)
    assert data_canon["branch_id"] == str(ec_branch.id)
    assert data_alias["evidence_state"] == data_canon["evidence_state"]
    assert data_alias["predicted_closing_rank"] == data_canon["predicted_closing_rank"]


# -----------------------------------------------------------------------------
# AG. Response schema validation against CandidateDecisionResponse
# -----------------------------------------------------------------------------
def test_ag_response_schema_validation(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "candidate_rank": 800,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    data = client.post("/api/v1/predictor/decision", json=payload).json()
    validated = CandidateDecisionResponse.model_validate(data)
    assert validated.candidate_rank == 800
    assert validated.evidence_state in list(CandidateEvidenceState)


# -----------------------------------------------------------------------------
# AH. API endpoint integration test (POST and GET)
# -----------------------------------------------------------------------------
def test_ah_api_endpoints_post_and_get(client: TestClient, rv_college: College, cs_branch: Branch):
    # Test POST
    payload = {
        "candidate_rank": 1200,
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_post = client.post("/api/v1/predictor/decision", json=payload)
    assert res_post.status_code == 200
    data_post = res_post.json()

    # Test GET
    url = f"/api/v1/predictor/decision?candidate_rank=1200&college_id={rv_college.id}&branch_id={cs_branch.id}&academic_year=2026&round=R1"
    res_get = client.get(url)
    assert res_get.status_code == 200
    data_get = res_get.json()

    assert data_post["evidence_state"] == data_get["evidence_state"]
    assert data_post["predicted_closing_rank"] == data_get["predicted_closing_rank"]
    assert data_post["candidate_rank"] == data_get["candidate_rank"]
