"""Comprehensive API and Service Integration Tests for Closing Rank Predictor (Stage 3.4).

Covers all test criteria specified in Section 11:
A. Valid R1 prediction (POST /api/v1/predictor/chances)
B. Valid R3 prediction
C. Valid R4 prediction
D. Unknown college (HTTP 404)
E. Unknown branch (HTTP 404)
F. Invalid category (HTTP 400)
G. Invalid program type (HTTP 400)
H. Unsupported round (HTTP 400, e.g. standard R2)
I. GM/KKR isolation
J. KKR_SPECIAL isolation (HTTP 400)
K. Engineering/Architecture isolation
L. Canonical branch alias resolution (ECS -> EC)
M. Cold-start response (HTTP 200 with INSUFFICIENT_EVIDENCE)
N. Missing historical evidence (HTTP 200 with INSUFFICIENT_EVIDENCE)
O. PredictionResult schema completeness
P. model_version present
Q. dataset_version present
R. feature_definition_version present
S. evidence trail populated
T. deterministic numerical prediction
U. database immutability
V. standard R2 is not fabricated
W. 2026 R1 -> R3 -> R4 progression safety
X. HTTP error semantics (400, 404, 422, 200, and GET endpoint)
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.core.enums import RecordStatus
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.category import Category
from backend.app.models.round import CounsellingRound
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.seat import SeatRecord
from backend.app.models.fee import FeeRecord
from backend.app.models.source import Source, SourceVersion


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


# -----------------------------------------------------------------------------
# A. Valid R1 prediction
# -----------------------------------------------------------------------------
def test_valid_r1_prediction(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["academic_year"] == 2026
    assert data["round"] == "R1"
    assert data["predicted_closing_rank"] is not None
    assert data["predicted_closing_rank"] > 0
    assert data["lower_bound"] is not None
    assert data["upper_bound"] is not None
    assert data["lower_bound"] <= data["predicted_closing_rank"] <= data["upper_bound"]
    assert data["latest_comparable_year"] == 2024
    assert len(data["evidence_trail"]) >= 1


# -----------------------------------------------------------------------------
# B. Valid R3 prediction
# -----------------------------------------------------------------------------
def test_valid_r3_prediction(client: TestClient, rv_college: College, ec_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R3",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["round"] == "R3"
    assert data["predicted_closing_rank"] is not None
    # Check that preceding round evidence is present
    has_preceding = any(e["source_type"] == "PRECEDING_ROUND" and e["round_code"] == "R1" for e in data["evidence_trail"])
    assert has_preceding


# -----------------------------------------------------------------------------
# C. Valid R4 prediction
# -----------------------------------------------------------------------------
def test_valid_r4_prediction(client: TestClient, rv_college: College, ec_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R4",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["round"] == "TERMINAL"
    assert data["predicted_closing_rank"] is not None
    assert data["prediction_interval"]["interval_type"] == "VOLATILITY_ADAPTIVE_WIDE"
    # Wide interval calibration for R4: lower bound stricter, upper bound expanded
    assert data["lower_bound"] <= data["predicted_closing_rank"] <= data["upper_bound"]


# -----------------------------------------------------------------------------
# D. Unknown college (404)
# -----------------------------------------------------------------------------
def test_unknown_college_returns_404(client: TestClient, cs_branch: Branch):
    fake_college_id = str(uuid.uuid4())
    payload = {
        "college_id": fake_college_id,
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 404
    assert "College with ID" in response.json()["detail"]


# -----------------------------------------------------------------------------
# E. Unknown branch (404)
# -----------------------------------------------------------------------------
def test_unknown_branch_returns_404(client: TestClient, rv_college: College):
    fake_branch_id = str(uuid.uuid4())
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": fake_branch_id,
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 404
    assert "Branch with ID" in response.json()["detail"]


# -----------------------------------------------------------------------------
# F. Invalid category (400)
# -----------------------------------------------------------------------------
def test_invalid_category_returns_400(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "INVALID_CAT",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 400
    assert "Unsupported category quota" in response.json()["detail"]


# -----------------------------------------------------------------------------
# G. Invalid program type (400)
# -----------------------------------------------------------------------------
def test_invalid_program_type_returns_400(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "MEDICAL",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 400
    assert "Unsupported program type" in response.json()["detail"]


# -----------------------------------------------------------------------------
# H. Unsupported round (400, e.g. R2)
# -----------------------------------------------------------------------------
def test_unsupported_round_r2_returns_400(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R2",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unsupported counselling round 'R2'" in detail
    assert "Standard R2 is not an official COMEDK general counselling round" in detail


# -----------------------------------------------------------------------------
# I. GM / KKR isolation
# -----------------------------------------------------------------------------
def test_gm_kkr_isolation(client: TestClient, rv_college: College, cs_branch: Branch):
    # Predict for GM
    payload_gm = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_gm = client.post("/api/v1/predictor/chances", json=payload_gm)
    assert res_gm.status_code == 200
    data_gm = res_gm.json()

    # Predict for KKR
    payload_kkr = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "KKR",
        "program_type": "ENGINEERING",
    }
    res_kkr = client.post("/api/v1/predictor/chances", json=payload_kkr)
    assert res_kkr.status_code == 200
    data_kkr = res_kkr.json()

    assert data_gm["category"] == "GM"
    assert data_kkr["category"] == "KKR"
    # Evidence trails must strictly reflect their own category
    for e in data_gm["evidence_trail"]:
        assert "KKR" not in e["description"]


# -----------------------------------------------------------------------------
# J. KKR_SPECIAL isolation (400)
# -----------------------------------------------------------------------------
def test_kkr_special_round_rejected(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "KKR_SPECIAL",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 400
    assert "KKR_SPECIAL is a specialized regional quota round" in response.json()["detail"]


# -----------------------------------------------------------------------------
# K. Engineering / Architecture isolation
# -----------------------------------------------------------------------------
def test_engineering_architecture_isolation(
    client: TestClient, rv_college: College, cs_branch: Branch, arch_branch: Branch
):
    # Requesting Architecture branch with ENGINEERING program_type must fail
    payload_mismatch = {
        "college_id": str(rv_college.id),
        "branch_id": str(arch_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_mismatch = client.post("/api/v1/predictor/chances", json=payload_mismatch)
    assert res_mismatch.status_code == 400
    assert "incompatible with requested program type" in res_mismatch.json()["detail"]

    # Requesting Architecture with R3 (not applicable to Architecture) must fail
    payload_arch_r3 = {
        "college_id": str(rv_college.id),
        "branch_id": str(arch_branch.id),
        "academic_year": 2026,
        "round": "R3",
        "category": "GM",
        "program_type": "ARCHITECTURE",
    }
    res_arch_r3 = client.post("/api/v1/predictor/chances", json=payload_arch_r3)
    assert res_arch_r3.status_code == 400
    assert "not applicable to ARCHITECTURE programs" in res_arch_r3.json()["detail"]


# -----------------------------------------------------------------------------
# L. Canonical branch alias resolution
# -----------------------------------------------------------------------------
def test_canonical_branch_alias_resolution(
    client: TestClient, rv_college: College, ec_branch: Branch, ecs_alias_branch: Branch
):
    """Test that requesting alias branch ECS resolves to canonical branch EC with identical results."""
    # 1. Request with alias branch ECS
    payload_alias = {
        "college_id": str(rv_college.id),
        "branch_id": str(ecs_alias_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_alias = client.post("/api/v1/predictor/chances", json=payload_alias)
    assert res_alias.status_code == 200
    data_alias = res_alias.json()

    # 2. Request with canonical branch EC
    payload_canon = {
        "college_id": str(rv_college.id),
        "branch_id": str(ec_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res_canon = client.post("/api/v1/predictor/chances", json=payload_canon)
    assert res_canon.status_code == 200
    data_canon = res_canon.json()

    # Response must reflect canonical branch_id in both cases
    assert data_alias["branch_id"] == str(ec_branch.id)
    assert data_canon["branch_id"] == str(ec_branch.id)

    # Predictions and bounds must be identical
    assert data_alias["predicted_closing_rank"] == data_canon["predicted_closing_rank"]
    assert data_alias["lower_bound"] == data_canon["lower_bound"]
    assert data_alias["upper_bound"] == data_canon["upper_bound"]
    assert data_alias["observation_count"] == data_canon["observation_count"]


# -----------------------------------------------------------------------------
# M. Cold-start response (200, INSUFFICIENT_EVIDENCE)
# -----------------------------------------------------------------------------
def test_cold_start_response(client: TestClient, db: Session, cs_branch: Branch):
    """A college with 0 historical cutoffs for CS must return 200 with INSUFFICIENT_EVIDENCE."""
    # Find a college that has no cutoff records for CS
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

    assert target_college is not None, "A cold-start college/branch combination must exist"

    payload = {
        "college_id": str(target_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "INSUFFICIENT_EVIDENCE"
    assert data["predicted_closing_rank"] is None
    assert data["lower_bound"] is None
    assert data["upper_bound"] is None
    assert data["cold_start_reason"] == "NO_HISTORICAL_RECORDS"
    assert len(data["explanation"]) >= 1


# -----------------------------------------------------------------------------
# N. Missing historical evidence (e.g. Model B on non-continuous years)
# -----------------------------------------------------------------------------
def test_missing_historical_evidence_fails_closed(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
        "model_type": "MODEL_B_PREVIOUS_YEAR",  # Requires strict T-1 (2025 R1, which does not exist)
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "INSUFFICIENT_EVIDENCE"
    assert data["predicted_closing_rank"] is None
    assert data["cold_start_reason"] == "NO_HISTORICAL_RECORDS"


# -----------------------------------------------------------------------------
# O. PredictionResult schema completeness (all 25 fields)
# -----------------------------------------------------------------------------
def test_prediction_result_schema_completeness(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()

    required_fields = [
        "prediction_id",
        "academic_year",
        "college_id",
        "branch_id",
        "category",
        "round",
        "program_type",
        "status",
        "predicted_closing_rank",
        "prediction_interval",
        "lower_bound",
        "upper_bound",
        "evidence_strength",
        "observation_count",
        "latest_comparable_year",
        "cold_start_reason",
        "model_name",
        "model_version",
        "dataset_version",
        "feature_definition_version",
        "generated_at",
        "input_parameters",
        "evidence_trail",
        "explanation",
        "disclaimer",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


# -----------------------------------------------------------------------------
# P, Q, R. Versioning presence (model_version, dataset_version, feature_version)
# -----------------------------------------------------------------------------
def test_versioning_presence(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "v1.0-research"
    assert data["dataset_version"] == "2023-2026-v1"
    assert data["feature_definition_version"] == "v1.0"


# -----------------------------------------------------------------------------
# S. Evidence trail populated with factual records
# -----------------------------------------------------------------------------
def test_evidence_trail_populated(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    response = client.post("/api/v1/predictor/chances", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["evidence_trail"]) >= 1
    for ev in data["evidence_trail"]:
        assert "source_type" in ev
        assert "closing_rank" in ev
        assert ev["closing_rank"] > 0
        assert "description" in ev


# -----------------------------------------------------------------------------
# T. Deterministic numerical prediction
# -----------------------------------------------------------------------------
def test_deterministic_numerical_prediction(client: TestClient, rv_college: College, cs_branch: Branch):
    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    res1 = client.post("/api/v1/predictor/chances", json=payload).json()
    res2 = client.post("/api/v1/predictor/chances", json=payload).json()

    assert res1["predicted_closing_rank"] == res2["predicted_closing_rank"]
    assert res1["lower_bound"] == res2["lower_bound"]
    assert res1["upper_bound"] == res2["upper_bound"]
    assert res1["model_name"] == res2["model_name"]


# -----------------------------------------------------------------------------
# U. Database immutability (before and after record counts match exactly)
# -----------------------------------------------------------------------------
def test_database_immutability_through_api(client: TestClient, db: Session, rv_college: College, cs_branch: Branch):
    count_cutoffs_before = db.query(CutoffRecord).count()
    count_seats_before = db.query(SeatRecord).count()
    count_fees_before = db.query(FeeRecord).count()

    payload = {
        "college_id": str(rv_college.id),
        "branch_id": str(cs_branch.id),
        "academic_year": 2026,
        "round": "R1",
        "category": "GM",
        "program_type": "ENGINEERING",
    }
    client.post("/api/v1/predictor/chances", json=payload)
    client.get(f"/api/v1/predictor/chances?college_id={rv_college.id}&branch_id={cs_branch.id}&academic_year=2026&round=R1")

    assert db.query(CutoffRecord).count() == count_cutoffs_before
    assert db.query(SeatRecord).count() == count_seats_before
    assert db.query(FeeRecord).count() == count_fees_before


# -----------------------------------------------------------------------------
# V. Standard R2 is not fabricated in any year
# -----------------------------------------------------------------------------
def test_standard_r2_is_never_fabricated(client: TestClient, rv_college: College, cs_branch: Branch):
    for year in [2023, 2024, 2025, 2026, 2027]:
        payload = {
            "college_id": str(rv_college.id),
            "branch_id": str(cs_branch.id),
            "academic_year": year,
            "round": "R2",
            "category": "GM",
            "program_type": "ENGINEERING",
        }
        res = client.post("/api/v1/predictor/chances", json=payload)
        assert res.status_code == 400
        assert "Unsupported counselling round 'R2'" in res.json()["detail"]


# -----------------------------------------------------------------------------
# W. 2026 R1 -> R3 -> R4 progression safety
# -----------------------------------------------------------------------------
def test_2026_progression_safety(client: TestClient, rv_college: College, cs_branch: Branch):
    # Valid general rounds in 2026: R1, R3, R4
    for rd in ["R1", "R3", "R4"]:
        payload = {
            "college_id": str(rv_college.id),
            "branch_id": str(cs_branch.id),
            "academic_year": 2026,
            "round": rd,
            "category": "GM",
            "program_type": "ENGINEERING",
        }
        res = client.post("/api/v1/predictor/chances", json=payload)
        assert res.status_code == 200
        assert res.json()["status"] == "SUCCESS"


# -----------------------------------------------------------------------------
# X. HTTP error semantics and GET alternative
# -----------------------------------------------------------------------------
def test_http_error_semantics_and_get_alternative(client: TestClient, rv_college: College, cs_branch: Branch):
    # 422: Malformed UUID
    res_422 = client.post("/api/v1/predictor/chances", json={"college_id": "not-a-uuid", "branch_id": "also-not"})
    assert res_422.status_code == 422

    # GET alternative endpoint
    url = f"/api/v1/predictor/chances?college_id={rv_college.id}&branch_id={cs_branch.id}&academic_year=2026&round=R1&category=GM&program_type=ENGINEERING"
    res_get = client.get(url)
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert data_get["status"] == "SUCCESS"
    assert data_get["round"] == "R1"
    assert data_get["predicted_closing_rank"] is not None
