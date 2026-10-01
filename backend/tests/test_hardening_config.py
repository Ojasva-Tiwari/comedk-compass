"""Tests for Stage 3.8A Configuration Hardening & Production Database Safeguards.

Verifies:
- Production + missing DATABASE_URL fails configuration validation
- Production + empty DATABASE_URL fails configuration validation
- Production + localhost / 127.0.0.1 DATABASE_URL fails configuration validation
- Production + explicit remote DATABASE_URL passes validation
- Development + missing DATABASE_URL provides safe local development default
- Development + existing local default is valid
"""

import pytest
from backend.app.config import Settings


def test_production_missing_database_url_fails():
    """When APP_ENV=production, missing/None DATABASE_URL must fail validation."""
    with pytest.raises(ValueError, match="DATABASE_URL must be explicitly configured in production"):
        Settings(
            APP_ENV="production",
            DATABASE_URL=None,
            CORS_ORIGINS="https://compass.comedk.org",
            ADMIN_API_KEY="prod-secret-admin-key-999"
        )


def test_production_empty_database_url_fails():
    """When APP_ENV=production, empty string DATABASE_URL must fail validation."""
    with pytest.raises(ValueError, match="DATABASE_URL must be explicitly configured in production"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="   ",
            CORS_ORIGINS="https://compass.comedk.org",
            ADMIN_API_KEY="prod-secret-admin-key-999"
        )


def test_production_localhost_database_url_fails():
    """When APP_ENV=production, localhost / 127.0.0.1 must be rejected to prevent accidental dev DB binding."""
    with pytest.raises(ValueError, match="cannot point to local development host"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+psycopg://postgres:secret@localhost:5432/comedk_prod",
            CORS_ORIGINS="https://compass.comedk.org",
            ADMIN_API_KEY="prod-secret-admin-key-999"
        )

    with pytest.raises(ValueError, match="cannot point to local development host"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+psycopg://postgres:secret@127.0.0.1:5432/comedk_prod",
            CORS_ORIGINS="https://compass.comedk.org",
            ADMIN_API_KEY="prod-secret-admin-key-999"
        )


def test_production_explicit_valid_database_url_passes():
    """When APP_ENV=production, explicit valid remote DATABASE_URL passes validation."""
    cfg = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://admin:strongpassword@db.production.internal:5432/comedk_compass",
        CORS_ORIGINS="https://compass.comedk.org",
        ADMIN_API_KEY="prod-secret-admin-key-999"
    )
    assert cfg.DATABASE_URL == "postgresql+psycopg://admin:strongpassword@db.production.internal:5432/comedk_compass"
    assert cfg.APP_ENV == "production"


def test_development_fallback_to_local_default():
    """When APP_ENV=development, missing DATABASE_URL falls back to local development database default."""
    cfg = Settings(
        APP_ENV="development",
        DATABASE_URL=None,
        CORS_ORIGINS="http://localhost:5173",
        ADMIN_API_KEY="dev-admin-key"
    )
    assert cfg.DATABASE_URL == "postgresql+psycopg://postgres@127.0.0.1:5432/comedk_compass"
    assert cfg.APP_ENV == "development"


def test_development_existing_local_default_valid():
    """When APP_ENV=development, explicit local database URL is valid."""
    cfg = Settings(
        APP_ENV="development",
        DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/comedk_compass",
    )
    assert "127.0.0.1" in cfg.DATABASE_URL
    assert cfg.APP_ENV == "development"
