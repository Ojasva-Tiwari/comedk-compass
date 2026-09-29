from sqlalchemy import text

def test_database_connection(db):
    result = db.execute(text("SELECT 1")).scalar()
    assert result == 1

def test_database_tables_exist(db):
    tables = [
        "colleges", "college_aliases", "branches", "college_branches",
        "categories", "counselling_rounds", "sources", "source_versions",
        "cutoff_records", "seat_records", "fee_records", "ingestion_runs",
        "validation_errors"
    ]
    for tbl in tables:
        count = db.execute(
            text(f"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='{tbl}'")
        ).scalar()
        assert count == 1, f"Table {tbl} does not exist in database"
