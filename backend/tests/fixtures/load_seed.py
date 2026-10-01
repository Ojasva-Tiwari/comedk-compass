"""Seed loader utility for CI and isolated test databases.

Restores the baseline COMEDK test fixture (colleges, branches, cutoffs, seats, fees)
into an already-migrated empty PostgreSQL database.
"""
import gzip
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

FIXTURE_PATH = Path(__file__).resolve().parent / "baseline_seed.sql.gz"

def load_seed(target_url: str) -> None:
    if "comedk_compass" in target_url and "docker" not in target_url and "test" not in target_url:
        print("ERROR: Refusing to seed database that looks like production/primary 'comedk_compass'!", file=sys.stderr)
        print("Target URL:", target_url, file=sys.stderr)
        sys.exit(1)

    if not FIXTURE_PATH.exists():
        print(f"ERROR: Fixture not found at {FIXTURE_PATH}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to target database: {target_url.split('@')[-1] if '@' in target_url else target_url}")
    engine = create_engine(target_url)

    print(f"Reading fixture from {FIXTURE_PATH}...")
    with gzip.open(FIXTURE_PATH, "rt", encoding="utf-8") as f:
        sql_content = f.read()

    print("Executing SQL seed statements...")
    # Execute with raw connection for fast bulk execution
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            cur.execute(sql_content)
        raw_conn.commit()
        print("Seed data successfully loaded!")
    finally:
        raw_conn.close()

if __name__ == "__main__":
    db_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if len(sys.argv) > 1:
        db_url = sys.argv[1]

    if not db_url:
        print("Usage: python -m backend.tests.fixtures.load_seed <DATABASE_URL>", file=sys.stderr)
        print("Or set TEST_DATABASE_URL or DATABASE_URL in environment.", file=sys.stderr)
        sys.exit(1)

    load_seed(db_url)
