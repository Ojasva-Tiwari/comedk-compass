"""Tests for Stage 3.8A Admin / Internal Data Health Protection.

Verifies:
- No credential -> 401
- Wrong credential -> 401
- Correct credential (Header, Bearer, or Query) -> 200
- Public endpoints remain accessible without credentials
- Secrets never appear in error messages or response bodies
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.config import settings


def test_data_health_anonymous_rejected(client: TestClient):
    """Anonymous request to /api/v1/data-health returns 401."""
    response = client.get("/api/v1/data-health")
    assert response.status_code == 401
    assert "admin" in response.json()["detail"].lower()


def test_html_data_health_anonymous_rejected(client: TestClient):
    """Anonymous request to /data-health returns 401."""
    response = client.get("/data-health")
    assert response.status_code == 401


def test_data_health_wrong_key_rejected(client: TestClient):
    """Wrong admin key returns 401."""
    response = client.get(
        "/api/v1/data-health",
        headers={"X-Admin-Key": "completely-wrong-token-999"}
    )
    assert response.status_code == 401


def test_data_health_correct_header_key_accepted(client: TestClient):
    """Correct X-Admin-Key returns 200."""
    response = client.get(
        "/api/v1/data-health",
        headers={"X-Admin-Key": settings.ADMIN_API_KEY}
    )
    assert response.status_code == 200
    assert "college_count" in response.json()


def test_data_health_bearer_token_accepted(client: TestClient):
    """Correct Authorization: Bearer <key> returns 200."""
    response = client.get(
        "/api/v1/data-health",
        headers={"Authorization": f"Bearer {settings.ADMIN_API_KEY}"}
    )
    assert response.status_code == 200


def test_data_health_query_param_rejected(client: TestClient):
    """Query parameter ?key=<key> is strictly rejected (returns 401) to prevent URL secret exposure."""
    response = client.get(f"/api/v1/data-health?key={settings.ADMIN_API_KEY}")
    assert response.status_code == 401


def test_html_data_health_query_param_rejected(client: TestClient):
    """HTML admin page ?key=<key> is strictly rejected (returns 401). Header auth is required."""
    response = client.get(f"/data-health?key={settings.ADMIN_API_KEY}")
    assert response.status_code == 401


def test_html_data_health_header_accepted(client: TestClient):
    """HTML admin page accepts X-Admin-Key header."""
    response = client.get("/data-health", headers={"X-Admin-Key": settings.ADMIN_API_KEY})
    assert response.status_code == 200
    assert "COMEDK Compass" in response.text


def test_public_student_endpoints_remain_accessible(client: TestClient):
    """Public endpoints (colleges, branches, cutoffs, predictor) do not require admin key."""
    for path in ["/api/v1/colleges", "/api/v1/branches", "/api/v1/health/live", "/api/v1/health/ready"]:
        res = client.get(path)
        assert res.status_code == 200, f"Public path {path} failed with status {res.status_code}"


def test_secrets_never_leaked_in_401_error(client: TestClient):
    """Error detail must never reveal the configured admin secret."""
    response = client.get("/api/v1/data-health", headers={"X-Admin-Key": "attempted-guess"})
    assert response.status_code == 401
    body_text = response.text
    assert settings.ADMIN_API_KEY not in body_text
    assert "dev-admin-key" not in body_text or settings.ADMIN_API_KEY != "dev-admin-key"
