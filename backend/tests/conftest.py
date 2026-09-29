import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database import SessionLocal
from backend.app.main import app

@pytest.fixture(scope="session")
def db():
    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
