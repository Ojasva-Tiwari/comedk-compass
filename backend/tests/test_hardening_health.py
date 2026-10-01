"""Tests for Stage 3.8A Liveness / Readiness Health Probes.

Verifies:
- GET /api/v1/health/live returns 200 without requiring database
- GET /api/v1/health/ready returns 200 when database is available
- GET /api/v1/health/ready returns 503 when database is unavailable
- Backward compatibility of GET /api/v1/health
- Request IDs are attached to all health probe responses
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from backend.app.database import get_db
from backend.app.main import app


def test_health_live_endpoint(client: TestClient):
    """Liveness probe succeeds immediately without database dependency."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "environment" in data
    assert response.headers.get("x-request-id") is not None


def test_health_ready_endpoint_success(client: TestClient):
    """Readiness probe succeeds with HTTP 200 when database is reachable."""
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert response.headers.get("x-request-id") is not None


def test_health_ready_endpoint_db_failure(client: TestClient):
    """Readiness probe returns HTTP 503 when database execution fails."""
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Simulated DB connection failure")

    def override_broken_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_broken_db
    try:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "service unavailable" in data["detail"].lower()
        # Must not leak raw exception text to the caller
        assert "Simulated DB connection failure" not in str(data)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_backward_compatibility(client: TestClient):
    """Existing /api/v1/health endpoint remains functional for existing clients."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
