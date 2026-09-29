import io
import sys
import re
from pathlib import Path
from decimal import Decimal
from sqlalchemy import text
from fastapi.testclient import TestClient

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from backend.app.database import engine
from backend.app.main import app

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def run_audit_part2():
    with engine.connect() as conn:
        print("==================================================")
        print("7. SOURCE AUDIT (88 DISCOVERED vs 29 ARCHIVED)")
        print("==================================================")
        # Query all sources in database
        db_sources = conn.execute(text("""
            SELECT s.id, s.url, s.title, s.document_type, s.academic_year, count(sv.id) as version_count
            FROM sources s
            LEFT JOIN source_versions sv ON s.id = sv.source_id
            GROUP BY s.id, s.url, s.title, s.document_type, s.academic_year
            ORDER BY s.document_type, s.title;
        """)).fetchall()
        print(f"Total Sources in Database: {len(db_sources)}")
        for s in db_sources:
            print(f"  [{s[3]}] {s[2][:50]} -> {s[1][:60]} (Versions: {s[5]})")

        print("\n==================================================")
        print("8. PROVENANCE AUDIT (20 RANDOM RECORDS)")
        print("==================================================")
        # 4 colleges
        colleges = conn.execute(text("""
            SELECT c.id, c.code, c.name, s.url, sv.content_hash, sv.local_path
            FROM colleges c
            JOIN college_aliases ca ON ca.college_id = c.id
            CROSS JOIN (SELECT url, id FROM sources WHERE document_type = 'MEMBER_INSTITUTIONS_HTML' LIMIT 1) s
            JOIN source_versions sv ON sv.source_id = s.id
            ORDER BY random() LIMIT 4;
        """)).fetchall()
        print("Colleges Provenance Sample:")
        for r in colleges:
            print(f"  College: {r[1]} - {r[2][:30]} | Source: {r[3]} | Hash: {r[4][:12]} | Path: {r[5]}")

        # 4 branches
        branches = conn.execute(text("""
            SELECT b.id, b.code, b.name, s.url, sv.content_hash, sv.local_path
            FROM branches b
            CROSS JOIN (SELECT url, id FROM sources WHERE document_type = 'CUTOFF_PDF' LIMIT 1) s
            JOIN source_versions sv ON sv.source_id = s.id
            ORDER BY random() LIMIT 4;
        """)).fetchall()
        print("\nBranches Provenance Sample:")
        for r in branches:
            print(f"  Branch: {r[1]} - {r[2][:30]} | Source: {r[3]} | Hash: {r[4][:12]} | Path: {r[5]}")

        # 4 cutoffs
        cutoffs = conn.execute(text("""
            SELECT c.code, b.code, cr.closing_rank, cr.page_number, cr.row_identifier, s.url, sv.content_hash, sv.local_path
            FROM cutoff_records cr
            JOIN colleges c ON cr.college_id = c.id
            JOIN branches b ON cr.branch_id = b.id
            JOIN source_versions sv ON cr.source_version_id = sv.id
            JOIN sources s ON sv.source_id = s.id
            ORDER BY random() LIMIT 4;
        """)).fetchall()
        print("\nCutoffs Provenance Sample:")
        for r in cutoffs:
            print(f"  Cutoff: {r[0]} | {r[1]} | Rank: {r[2]} | Page: {r[3]} | RowId: {r[4]} | Hash: {r[6][:12]} | Source: {r[5]}")

        # 4 seats
        seats = conn.execute(text("""
            SELECT c.code, b.code, sr.total_seats, sr.vacant_seats, s.url, sv.content_hash, sv.local_path
            FROM seat_records sr
            JOIN colleges c ON sr.college_id = c.id
            JOIN branches b ON sr.branch_id = b.id
            JOIN source_versions sv ON sr.source_version_id = sv.id
            JOIN sources s ON sv.source_id = s.id
            ORDER BY random() LIMIT 4;
        """)).fetchall()
        print("\nSeats Provenance Sample:")
        for r in seats:
            print(f"  Seat: {r[0]} | {r[1]} | Total: {r[2]} | Vacant: {r[3]} | Hash: {r[5][:12]} | Source: {r[4]}")

        # 4 fees
        fees = conn.execute(text("""
            SELECT c.code, b.code, fr.total_fee, fr.tuition_fee, s.url, sv.content_hash, sv.local_path
            FROM fee_records fr
            JOIN colleges c ON fr.college_id = c.id
            LEFT JOIN branches b ON fr.branch_id = b.id
            JOIN source_versions sv ON fr.source_version_id = sv.id
            JOIN sources s ON sv.source_id = s.id
            ORDER BY random() LIMIT 4;
        """)).fetchall()
        print("\nFees Provenance Sample:")
        for r in fees:
            print(f"  Fee: {r[0]} | {str(r[1])} | Total: ₹{r[2]:,.0f} | Tuit: ₹{r[3] or 0:,.0f} | Hash: {r[5][:12]} | Source: {r[4]}")

        print("\n==================================================")
        print("9. PLACEHOLDER / FABRICATION CHECK")
        print("==================================================")
        placeholder_regex = "^(COLLEGECODE|COLLEGE|BRANCH|COURSE|CODE|UNKNOWN|TEST|SAMPLE|DUMMY)"
        
        ph_colleges = conn.execute(text(f"SELECT code, name FROM colleges WHERE code ~* '{placeholder_regex}' OR name ~* '{placeholder_regex}';")).fetchall()
        ph_branches = conn.execute(text(f"SELECT code, name FROM branches WHERE code ~* '{placeholder_regex}' OR name ~* '{placeholder_regex}';")).fetchall()
        ph_aliases = conn.execute(text(f"SELECT alias FROM college_aliases WHERE alias ~* '{placeholder_regex}';")).fetchall()
        
        print(f"Colleges matching placeholder pattern: {len(ph_colleges)}")
        for r in ph_colleges:
            print(f"  {r}")
        print(f"Branches matching placeholder pattern: {len(ph_branches)}")
        for r in ph_branches:
            print(f"  {r}")
        print(f"Aliases matching placeholder pattern: {len(ph_aliases)}")
        for r in ph_aliases:
            print(f"  {r}")

        print("\n==================================================")
        print("10. IDEMPOTENCY COMPARISON")
        print("==================================================")
        runs = conn.execute(text("SELECT id, started_at, finished_at, status, published_count, validation_error_count, summary FROM ingestion_runs ORDER BY started_at ASC;")).fetchall()
        for i, r in enumerate(runs, 1):
            print(f"Run {i} ({r[0]}):")
            print(f"  Status: {r[3]}, Started: {r[1]}, Finished: {r[2]}")
            print(f"  Published: {r[4]}, Errors: {r[5]}")
            print(f"  Summary: {r[6]}")

        print("\n==================================================")
        print("11. API VS DATABASE TOTALS")
        print("==================================================")
        client = TestClient(app)
        
        db_colleges = conn.execute(text("SELECT count(*) FROM colleges;")).scalar()
        api_colleges = client.get("/api/v1/colleges?limit=1").json()["total"]
        print(f"Colleges: DB = {db_colleges} | API = {api_colleges} -> {'MATCH' if db_colleges == api_colleges else 'MISMATCH'}")

        db_branches = conn.execute(text("SELECT count(*) FROM branches;")).scalar()
        api_branches = client.get("/api/v1/branches?limit=1").json()["total"]
        print(f"Branches: DB = {db_branches} | API = {api_branches} -> {'MATCH' if db_branches == api_branches else 'MISMATCH'}")

        db_cutoffs = conn.execute(text("SELECT count(*) FROM cutoff_records WHERE status = 'PUBLISHED';")).scalar()
        api_cutoffs = client.get("/api/v1/cutoffs?limit=1").json()["total"]
        print(f"Cutoffs (Published): DB = {db_cutoffs} | API = {api_cutoffs} -> {'MATCH' if db_cutoffs == api_cutoffs else 'MISMATCH'}")

        db_seats = conn.execute(text("SELECT count(*) FROM seat_records WHERE status = 'PUBLISHED';")).scalar()
        api_seats = client.get("/api/v1/seat-records?limit=1").json()["total"]
        print(f"Seats (Published): DB = {db_seats} | API = {api_seats} -> {'MATCH' if db_seats == api_seats else 'MISMATCH'}")

        db_fees = conn.execute(text("SELECT count(*) FROM fee_records WHERE status = 'PUBLISHED';")).scalar()
        api_fees = client.get("/api/v1/fees?limit=1").json()["total"]
        print(f"Fees (Published): DB = {db_fees} | API = {api_fees} -> {'MATCH' if db_fees == api_fees else 'MISMATCH'}")

        db_sources_count = conn.execute(text("SELECT count(*) FROM sources;")).scalar()
        api_sources = client.get("/api/v1/sources?limit=1").json()["total"]
        print(f"Sources: DB = {db_sources_count} | API = {api_sources} -> {'MATCH' if db_sources_count == api_sources else 'MISMATCH'}")

if __name__ == "__main__":
    run_audit_part2()
