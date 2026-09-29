import io
import sys
from decimal import Decimal
from pathlib import Path
from sqlalchemy import text

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from backend.app.database import engine

# Set stdout to UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def run_audit():
    with engine.connect() as conn:
        print("==================================================")
        print("1. COLLEGE AUDIT")
        print("==================================================")
        total_colleges = conn.execute(text("SELECT count(*) FROM colleges;")).scalar()
        distinct_codes = conn.execute(text("SELECT count(DISTINCT code) FROM colleges;")).scalar()
        print(f"Total colleges: {total_colleges}")
        print(f"Distinct official COMEDK codes: {distinct_codes}")
        print(f"Duplicate codes: {total_colleges - distinct_codes}")

        prefixes = conn.execute(text("""
            SELECT substr(code, 1, 1) AS prefix, count(*)
            FROM colleges
            GROUP BY substr(code, 1, 1)
            ORDER BY count(*) DESC;
        """)).fetchall()
        print("Breakdown by Code Prefix:")
        for p, count in prefixes:
            print(f"  Prefix '{p}': {count}")

        # Check suspicious
        suspicious_colleges = conn.execute(text("""
            SELECT code, name, location FROM colleges 
            WHERE code ~* '^(TEST|COLLEGE|CODE|UNKNOWN|SAMPLE|DUMMY)' 
               OR name ~* '(TEST|SAMPLE|DUMMY|COLLEGE NAME)'
               OR code IS NULL OR name IS NULL OR trim(code) = '' OR trim(name) = '';
        """)).fetchall()
        print(f"Suspicious colleges count: {len(suspicious_colleges)}")
        for sc in suspicious_colleges:
            print(f"  Found suspicious college: {sc}")

        # Non-engineering check: D (Dental), M (Medical), etc.
        non_eng = conn.execute(text("""
            SELECT code, name, location FROM colleges
            WHERE code NOT LIKE 'E%'
            ORDER BY code;
        """)).fetchall()
        print(f"\nNon-Engineering (Non-E prefix) Colleges count: {len(non_eng)}")
        for c in non_eng[:10]:
            print(f"  {c[0]} | {c[1]} | {c[2]}")
        if len(non_eng) > 10:
            print(f"  ... and {len(non_eng) - 10} more")

        # First 20 colleges
        print("\nFirst 20 College records:")
        first_20_c = conn.execute(text("""
            SELECT code, original_name, name, location 
            FROM colleges 
            ORDER BY code ASC 
            LIMIT 20;
        """)).fetchall()
        for r in first_20_c:
            print(f"  {r[0]:<6} | {r[1][:40]:<40} | {r[2][:35]:<35} | {r[3]}")

        print("\n==================================================")
        print("2. BRANCH AUDIT")
        print("==================================================")
        total_branches = conn.execute(text("SELECT count(*) FROM branches;")).scalar()
        distinct_branches = conn.execute(text("SELECT count(DISTINCT code) FROM branches;")).scalar()
        print(f"Total branches: {total_branches}")
        print(f"Distinct official branch codes: {distinct_branches}")
        print(f"Duplicate codes: {total_branches - distinct_branches}")

        # College-branch relationships
        total_cb = conn.execute(text("SELECT count(*) FROM college_branches;")).scalar()
        print(f"Total college_branch relationships: {total_cb}")

        suspicious_branches = conn.execute(text("""
            SELECT code, name, original_name FROM branches 
            WHERE code ~* '^(TEST|BRANCH|COURSE|CODE|UNKNOWN|SAMPLE|DUMMY)' 
               OR name ~* '(TEST|SAMPLE|DUMMY)'
               OR code IS NULL OR name IS NULL OR trim(code) = '' OR trim(name) = '';
        """)).fetchall()
        print(f"Suspicious branches count: {len(suspicious_branches)}")
        for sb in suspicious_branches:
            print(f"  Found suspicious branch: {sb}")

        print("\nAll Branch Codes and Original Names:")
        all_b = conn.execute(text("SELECT code, original_name FROM branches ORDER BY code;")).fetchall()
        for b in all_b:
            print(f"  {b[0]:<6} : {b[1]}")

        print("\n==================================================")
        print("3. CUTOFF AUDIT")
        print("==================================================")
        total_cutoffs = conn.execute(text("SELECT count(*) FROM cutoff_records;")).scalar()
        print(f"Total cutoff records: {total_cutoffs}")

        by_year = conn.execute(text("SELECT academic_year, count(*) FROM cutoff_records GROUP BY academic_year;")).fetchall()
        print(f"By academic year: {by_year}")

        by_round = conn.execute(text("""
            SELECT cr.code, cr.name, count(*) 
            FROM cutoff_records c 
            JOIN counselling_rounds cr ON c.round_id = cr.id 
            GROUP BY cr.code, cr.name;
        """)).fetchall()
        print(f"By round: {by_round}")

        by_cat = conn.execute(text("""
            SELECT cat.code, cat.name, count(*) 
            FROM cutoff_records c 
            JOIN categories cat ON c.category_id = cat.id 
            GROUP BY cat.code, cat.name;
        """)).fetchall()
        print(f"By category: {by_cat}")

        unique_cols_in_cutoffs = conn.execute(text("SELECT count(DISTINCT college_id) FROM cutoff_records;")).scalar()
        unique_brs_in_cutoffs = conn.execute(text("SELECT count(DISTINCT branch_id) FROM cutoff_records;")).scalar()
        unique_cb_combos = conn.execute(text("SELECT count(DISTINCT (college_id, branch_id)) FROM cutoff_records;")).scalar()
        unique_cbcr_combos = conn.execute(text("SELECT count(DISTINCT (college_id, branch_id, category_id, round_id)) FROM cutoff_records;")).scalar()
        print(f"Unique colleges represented in cutoffs: {unique_cols_in_cutoffs}")
        print(f"Unique branches represented in cutoffs: {unique_brs_in_cutoffs}")
        print(f"Unique college+branch combinations: {unique_cb_combos}")
        print(f"Unique college+branch+category+round combinations: {unique_cbcr_combos}")

        # Integrity checks
        op_gt_cl = conn.execute(text("SELECT count(*) FROM cutoff_records WHERE opening_rank IS NOT NULL AND opening_rank > closing_rank;")).scalar()
        cl_le_zero = conn.execute(text("SELECT count(*) FROM cutoff_records WHERE closing_rank <= 0;")).scalar()
        dup_logical = conn.execute(text("""
            SELECT college_id, branch_id, category_id, round_id, academic_year, count(*) 
            FROM cutoff_records 
            GROUP BY college_id, branch_id, category_id, round_id, academic_year 
            HAVING count(*) > 1;
        """)).fetchall()
        missing_c = conn.execute(text("SELECT count(*) FROM cutoff_records WHERE college_id IS NULL;")).scalar()
        missing_b = conn.execute(text("SELECT count(*) FROM cutoff_records WHERE branch_id IS NULL;")).scalar()
        missing_cat = conn.execute(text("SELECT count(*) FROM cutoff_records WHERE category_id IS NULL;")).scalar()
        missing_r = conn.execute(text("SELECT count(*) FROM cutoff_records WHERE round_id IS NULL;")).scalar()

        print(f"Opening rank > Closing rank: {op_gt_cl}")
        print(f"Closing rank <= 0: {cl_le_zero}")
        print(f"Duplicate logical records: {len(dup_logical)}")
        print(f"Missing college: {missing_c}, Missing branch: {missing_b}, Missing category: {missing_cat}, Missing round: {missing_r}")

        # Identical ranks across combinations check
        top_ranks = conn.execute(text("""
            SELECT closing_rank, count(*) 
            FROM cutoff_records 
            GROUP BY closing_rank 
            ORDER BY count(*) DESC 
            LIMIT 5;
        """)).fetchall()
        print(f"Most frequent closing ranks (value, count): {top_ranks}")

        print("\n30 Representative Cutoff Records:")
        sample_cutoffs = conn.execute(text("""
            SELECT 
                c.code, c.name, 
                b.code, b.name, 
                cat.code, 
                cr.code, 
                cr_rec.opening_rank, cr_rec.closing_rank,
                s.title, sv.content_hash,
                cr_rec.page_number, cr_rec.row_identifier
            FROM cutoff_records cr_rec
            JOIN colleges c ON cr_rec.college_id = c.id
            JOIN branches b ON cr_rec.branch_id = b.id
            JOIN categories cat ON cr_rec.category_id = cat.id
            JOIN counselling_rounds cr ON cr_rec.round_id = cr.id
            JOIN source_versions sv ON cr_rec.source_version_id = sv.id
            JOIN sources s ON sv.source_id = s.id
            ORDER BY cr_rec.closing_rank ASC
            LIMIT 30;
        """)).fetchall()
        for r in sample_cutoffs:
            print(f"  {r[0]:<5} {r[1][:25]:<25} | {r[2]:<4} {r[3][:20]:<20} | {r[4]:<3} | {r[5]:<4} | Op:{str(r[6]):<6} Cl:{r[7]:<6} | p{r[10]} {r[11]} | {r[8][:25]}")

        print("\n==================================================")
        print("4. CUTOFF COVERAGE")
        print("==================================================")
        cutoff_sources = conn.execute(text("""
            SELECT s.title, s.url, sv.content_hash, sv.document_type, sv.processing_status, sv.id
            FROM sources s
            JOIN source_versions sv ON s.id = sv.source_id
            WHERE s.document_type = 'CUTOFF_PDF' OR s.title ~* 'cut-off|cutoff';
        """)).fetchall()
        print(f"Total cutoff sources in DB: {len(cutoff_sources)}")
        for cs in cutoff_sources:
            sv_id = cs[5]
            rec_count = conn.execute(text(f"SELECT count(*) FROM cutoff_records WHERE source_version_id = '{sv_id}';")).scalar()
            err_count = conn.execute(text(f"SELECT count(*) FROM validation_errors WHERE source_version_id = '{sv_id}';")).scalar()
            print(f"Title: {cs[0]}")
            print(f"  URL: {cs[1]}")
            print(f"  SHA-256: {cs[2]}")
            print(f"  Status: {cs[4]}, Records in DB: {rec_count}, Errors: {err_count}")

        print("\n==================================================")
        print("5. SEAT AUDIT")
        print("==================================================")
        total_seats = conn.execute(text("SELECT count(*) FROM seat_records;")).scalar()
        print(f"Total seat records: {total_seats}")

        seat_by_source = conn.execute(text("""
            SELECT s.title, count(sr.id)
            FROM seat_records sr
            JOIN source_versions sv ON sr.source_version_id = sv.id
            JOIN sources s ON sv.source_id = s.id
            GROUP BY s.title;
        """)).fetchall()
        print(f"Seat records by source ({len(seat_by_source)} sources):")
        for sbs in seat_by_source:
            print(f"  {sbs[0][:50]} : {sbs[1]}")

        neg_seats = conn.execute(text("SELECT count(*) FROM seat_records WHERE total_seats < 0 OR vacant_seats < 0;")).scalar()
        vac_gt_tot = conn.execute(text("SELECT count(*) FROM seat_records WHERE total_seats IS NOT NULL AND vacant_seats IS NOT NULL AND vacant_seats > total_seats;")).scalar()
        missing_cb_seats = conn.execute(text("SELECT count(*) FROM seat_records WHERE college_id IS NULL OR branch_id IS NULL;")).scalar()
        print(f"Negative seats: {neg_seats}")
        print(f"Vacant > Total seats: {vac_gt_tot}")
        print(f"Missing college/branch: {missing_cb_seats}")

        print("\n20 Representative Seat Records:")
        sample_seats = conn.execute(text("""
            SELECT c.code, c.name, b.code, b.name, sr.academic_year, sr.total_seats, sr.vacant_seats, s.title, sv.content_hash
            FROM seat_records sr
            JOIN colleges c ON sr.college_id = c.id
            JOIN branches b ON sr.branch_id = b.id
            JOIN source_versions sv ON sr.source_version_id = sv.id
            JOIN sources s ON sv.source_id = s.id
            LIMIT 20;
        """)).fetchall()
        for r in sample_seats:
            print(f"  {r[0]:<5} {r[1][:25]:<25} | {r[2]:<4} {r[3][:20]:<20} | Yr:{r[4]} Tot:{str(r[5]):<4} Vac:{str(r[6]):<4} | {r[7][:25]}")

        print("\n==================================================")
        print("6. FEE AUDIT")
        print("==================================================")
        total_fees = conn.execute(text("SELECT count(*) FROM fee_records;")).scalar()
        unique_fee_cb = conn.execute(text("SELECT count(DISTINCT (college_id, branch_id)) FROM fee_records WHERE branch_id IS NOT NULL;")).scalar()
        print(f"Total fee records: {total_fees}")
        print(f"Unique college+branch combinations in fees: {unique_fee_cb}")

        neg_fees = conn.execute(text("SELECT count(*) FROM fee_records WHERE total_fee < 0;")).scalar()
        zero_fees = conn.execute(text("SELECT count(*) FROM fee_records WHERE total_fee = 0;")).scalar()
        print(f"Negative fees: {neg_fees}")
        print(f"Zero fees: {zero_fees}")

        top_fees = conn.execute(text("""
            SELECT total_fee, count(*) 
            FROM fee_records 
            GROUP BY total_fee 
            ORDER BY count(*) DESC 
            LIMIT 5;
        """)).fetchall()
        print(f"Most common total fee values (fee, count): {top_fees}")

        print("\n20 Representative Fee Records:")
        sample_fees = conn.execute(text("""
            SELECT c.code, c.name, b.code, fr.academic_year, fr.total_fee, fr.tuition_fee, fr.other_fee, fr.currency, s.title, sv.content_hash
            FROM fee_records fr
            JOIN colleges c ON fr.college_id = c.id
            LEFT JOIN branches b ON fr.branch_id = b.id
            JOIN source_versions sv ON fr.source_version_id = sv.id
            JOIN sources s ON sv.source_id = s.id
            LIMIT 20;
        """)).fetchall()
        for r in sample_fees:
            print(f"  {r[0]:<5} {r[1][:25]:<25} | {str(r[2]):<4} | Yr:{r[3]} Fee: ₹{r[4]:,.0f} (Tuit: ₹{r[5] or 0:,.0f} Oth: ₹{r[6] or 0:,.0f}) | {r[8][:25]}")

if __name__ == "__main__":
    run_audit()
