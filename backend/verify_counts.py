import sys
from pathlib import Path
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database import SessionLocal

def main():
    db = SessionLocal()

    print("=" * 80)
    print("STAGE 2 FINAL ROUND & RECORD AUDIT")
    print("=" * 80)

    # Cutoffs
    print("\nCUTOFF RECORDS BY ROUND:")
    rows_c = db.execute(text('''
        SELECT coalesce(r.code, 'NO_ROUND'), coalesce(r.is_general_round, true), count(c.id)
        FROM cutoff_records c
        LEFT JOIN counselling_rounds r ON c.round_id = r.id
        GROUP BY r.code, r.is_general_round
        ORDER BY r.code;
    ''')).fetchall()
    for r in rows_c:
        gen = "GENERAL" if r[1] else "SPECIAL_QUOTA"
        print(f"  {r[0]:15} ({gen:13}): {r[2]:5} records")

    # Seats
    print("\nSEAT RECORDS (VACANCIES) BY ROUND:")
    rows_s = db.execute(text('''
        SELECT coalesce(r.code, 'NO_ROUND'), coalesce(r.is_general_round, true), count(s.id)
        FROM seat_records s
        LEFT JOIN counselling_rounds r ON s.round_id = r.id
        WHERE s.vacant_seats IS NOT NULL
        GROUP BY r.code, r.is_general_round
        ORDER BY r.code;
    ''')).fetchall()
    for r in rows_s:
        gen = "GENERAL" if r[1] else "SPECIAL_QUOTA"
        print(f"  {r[0]:15} ({gen:13}): {r[2]:5} records")

    kkr_seats = db.execute(text("SELECT count(s.id) FROM seat_records s JOIN counselling_rounds r ON s.round_id = r.id WHERE r.code = 'KKR_SPECIAL'")).scalar()
    kkr_cutoffs = db.execute(text("SELECT count(c.id) FROM cutoff_records c JOIN counselling_rounds r ON c.round_id = r.id WHERE r.code = 'KKR_SPECIAL'")).scalar()
    r2_seats = db.execute(text("SELECT count(s.id) FROM seat_records s JOIN counselling_rounds r ON s.round_id = r.id WHERE r.code = 'R2'")).scalar()
    r2_cutoffs = db.execute(text("SELECT count(c.id) FROM cutoff_records c JOIN counselling_rounds r ON c.round_id = r.id WHERE r.code = 'R2'")).scalar()

    print("\n" + "=" * 80)
    print("KEY METRICS FOR AUDIT REPORT:")
    print(f"  number of KKR_SPECIAL seat records:   {kkr_seats}")
    print(f"  number of KKR_SPECIAL cutoff records: {kkr_cutoffs}")
    print(f"  number of standard R2 seat records:   {r2_seats}")
    print(f"  number of standard R2 cutoff records: {r2_cutoffs}")
    print("=" * 80)

    db.close()

if __name__ == "__main__":
    main()
