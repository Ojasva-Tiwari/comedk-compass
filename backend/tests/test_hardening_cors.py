"""Tests for Stage 3.8A CORS Hardening.

Verifies:
A. Configured allowed origin accepted
B. Unconfigured/unknown origin rejected
C. Development configuration works for local dev origins
D. Production configuration fails closed if no explicit allowed origin or if wildcard is used
E. Credentials behavior matches application requirements (disabled)
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import app


def test_configured_allowed_origin_accepted(client: TestClient):
    """Allowed origin in settings receives matching Access-Control-Allow-Origin."""
    response = client.get(
        "/api/v1/health/live",
        headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_unknown_origin_rejected(client: TestClient):
    """Unknown/unconfigured origin does not receive access-control-allow-origin."""
    response = client.get(
        "/api/v1/health/live",
        headers={"Origin": "https://malicious-site.example.com"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") is None


def test_cors_credentials_disabled(client: TestClient):
    """Access-Control-Allow-Credentials must not be True since cookies/auth-sessions are not used."""
    response = client.options(
        "/api/v1/colleges",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.headers.get("access-control-allow-credentials") != "true"


def test_production_fails_closed_on_wildcard_cors():
    """Production settings validation raises error if CORS_ORIGINS contains '*'."""
    with pytest.raises(ValueError, match="cannot contain wildcard"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+psycopg://user:pass@db.internal.prod:5432/comedk_prod",
            CORS_ORIGINS="*",
            ADMIN_API_KEY="a-secure-production-key-12345"
        )


def test_production_fails_closed_on_empty_cors():
    """Production settings validation raises error if CORS_ORIGINS is empty."""
    with pytest.raises(ValueError, match="must be explicitly configured"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+psycopg://user:pass@db.internal.prod:5432/comedk_prod",
            CORS_ORIGINS="",
            ADMIN_API_KEY="a-secure-production-key-12345"
        )


def test_production_accepts_explicit_origin():
    """Production accepts explicit domain without wildcard."""
    cfg = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://user:pass@db.internal.prod:5432/comedk_prod",
        CORS_ORIGINS="https://compass.example.com,https://app.example.com",
        ADMIN_API_KEY="a-secure-production-key-12345"
    )
    assert "https://compass.example.com" in cfg.parsed_cors_origins
    assert "https://app.example.com" in cfg.parsed_cors_origins

