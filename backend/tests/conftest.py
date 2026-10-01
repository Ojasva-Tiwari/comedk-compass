import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings
import backend.app.database as db_module
from backend.app.database import get_db, Base
from backend.app.main import app

# 1. Enforce isolated TEST_DATABASE_URL
test_db_url = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL

if not test_db_url:
    pytest.exit(
        "CONFIGURATION ERROR: TEST_DATABASE_URL is not set.\n"
        "Pytest is prevented from running against the development DATABASE_URL to avoid accidental mutation.\n"
        "Please set TEST_DATABASE_URL in .env or the environment, pointing to a dedicated test database "
        "(e.g., postgresql+psycopg://postgres:postgres@127.0.0.1:5432/comedk_compass_test).\n"
        "See backend/tests/README.md for instructions.",
        returncode=1
    )

if test_db_url == settings.DATABASE_URL:
    pytest.exit(
        "CONFIGURATION ERROR: TEST_DATABASE_URL cannot be identical to development DATABASE_URL.\n"
        "Pytest requires an isolated test database to protect development data integrity.",
        returncode=1
    )

# 2. Build isolated test database engine & sessionmaker
test_engine = create_engine(
    test_db_url,
    echo=False,
    pool_pre_ping=True
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Rebind backend.app.database.engine and SessionLocal to guarantee all modules
# and test scripts use the isolated test database.
db_module.engine = test_engine
db_module.SessionLocal = TestSessionLocal


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database():
    """Verify test database connectivity and ensure schema tables exist."""
    try:
        with test_engine.connect() as conn:
            Base.metadata.create_all(bind=conn)
            conn.commit()
    except Exception as e:
        pytest.exit(
            f"CONFIGURATION ERROR: Failed to connect to or initialize TEST_DATABASE_URL ({test_db_url}): {e}",
            returncode=1
        )


@pytest.fixture(scope="function")
def db() -> Session:
    """Provides a transactional session on the isolated test database that cleans up."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient whose database dependency is bound to the isolated test database."""
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
