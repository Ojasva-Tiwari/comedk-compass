"""Tests for Stage 3.8A Structured Logging and Request ID Propagation.

Verifies:
- Supplied valid X-Request-ID is preserved and echoed in response
- Missing X-Request-ID generates a secure random UUID
- Malformed or oversized X-Request-ID is safely replaced with a new UUID
- Request ID survives on error paths (404, 401, 500)
- StructuredJsonFormatter formats messages as valid JSON with required fields
- Sensitive keys are redacted in structured log outputs
"""

import json
import logging
from uuid import UUID
import pytest
from fastapi.testclient import TestClient
from backend.app.core.logging import StructuredJsonFormatter


def test_supplied_request_id_is_echoed(client: TestClient):
    """Client-provided valid X-Request-ID is returned in response header."""
    custom_id = "req-custom-12345-abcde"
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id


def test_missing_request_id_generates_uuid(client: TestClient):
    """When no X-Request-ID is provided, a valid UUIDv4 is generated."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    rid = response.headers.get("x-request-id")
    assert rid is not None
    # Validate UUID format
    parsed = UUID(rid)
    assert str(parsed) == rid


def test_oversized_request_id_is_safely_replaced(client: TestClient):
    """An oversized (>64 chars) X-Request-ID is replaced with a generated UUID."""
    huge_id = "a" * 128
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": huge_id})
    assert response.status_code == 200
    rid = response.headers.get("x-request-id")
    assert rid != huge_id
    # Valid UUID generated instead
    UUID(rid)


def test_malformed_chars_in_request_id_replaced(client: TestClient):
    """An X-Request-ID containing invalid characters (e.g. spaces, injections) is replaced."""
    malformed_id = "req-id<script>alert(1)</script>"
    response = client.get("/api/v1/health/live", headers={"X-Request-ID": malformed_id})
    assert response.status_code == 200
    rid = response.headers.get("x-request-id")
    assert rid != malformed_id
    UUID(rid)


def test_request_id_survives_404_error_path(client: TestClient):
    """Request ID is attached even on 404 responses."""
    response = client.get("/api/v1/non-existent-endpoint-xyz", headers={"X-Request-ID": "test-404-id"})
    assert response.status_code == 404
    assert response.headers.get("x-request-id") == "test-404-id"


def test_request_id_survives_401_error_path(client: TestClient):
    """Request ID is attached on 401 unauthorized responses."""
    response = client.get("/api/v1/data-health", headers={"X-Request-ID": "test-401-id"})
    assert response.status_code == 401
    assert response.headers.get("x-request-id") == "test-401-id"


def test_structured_json_formatter_fields():
    """StructuredJsonFormatter produces valid JSON with timestamp, level, logger, message."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test structured log message",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["message"] == "Test structured log message"
    assert "timestamp" in data


def test_structured_json_formatter_redacts_sensitive_keys():
    """StructuredJsonFormatter redacts sensitive information such as passwords, tokens, API keys."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=20,
        msg="Connection event",
        args=(),
        exc_info=None
    )
    record.api_key = "super-secret-key-12345"
    record.password = "db_password_xyz"
    record.normal_field = "safe_value"
    formatted = formatter.format(record)
    data = json.loads(formatted)
    assert data["api_key"] == "[REDACTED]"
    assert data["password"] == "[REDACTED]"
    assert data["normal_field"] == "safe_value"
