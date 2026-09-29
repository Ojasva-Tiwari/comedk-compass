import sys
import uuid
from pathlib import Path
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database import SessionLocal

def run_migration():
    db = SessionLocal()

    # 1. Add column if not exists
    db.execute(text('ALTER TABLE counselling_rounds ADD COLUMN IF NOT EXISTS is_general_round BOOLEAN NOT NULL DEFAULT TRUE;'))
    db.commit()

    # 2. Check existing rounds
    rounds = db.execute(text('SELECT id, code, name, academic_year, round_number, is_general_round FROM counselling_rounds ORDER BY academic_year, round_number;')).fetchall()
    print('Existing rounds before migration:')
    for r in rounds:
        print(' ', r)

    # 3. Create KKR_SPECIAL for 2026 and 2025 if not present
    for yr in (2026, 2025):
        existing_kkr = db.execute(text('SELECT id FROM counselling_rounds WHERE code = :code AND academic_year = :yr'), {'code': 'KKR_SPECIAL', 'yr': yr}).scalar()
        if not existing_kkr:
            new_id = uuid.uuid4()
            db.execute(text('''
                INSERT INTO counselling_rounds (id, code, name, academic_year, round_number, is_general_round, created_at, updated_at)
                VALUES (:id, :code, :name, :yr, 2, FALSE, NOW(), NOW())
            '''), {
                'id': new_id,
                'code': 'KKR_SPECIAL',
                'name': 'Round 2 KKR Special Allotment',
                'yr': yr
            })
            print(f'Created KKR_SPECIAL for {yr} with id={new_id}')
    db.commit()

    # 4. Migrate existing R2 records to KKR_SPECIAL
    for yr in (2026, 2025):
        r2_id = db.execute(text('SELECT id FROM counselling_rounds WHERE code = :code AND academic_year = :yr'), {'code': 'R2', 'yr': yr}).scalar()
        kkr_id = db.execute(text('SELECT id FROM counselling_rounds WHERE code = :code AND academic_year = :yr'), {'code': 'KKR_SPECIAL', 'yr': yr}).scalar()
        
        if r2_id and kkr_id:
            # Move seat_records
            res_seats = db.execute(text('UPDATE seat_records SET round_id = :kkr_id WHERE round_id = :r2_id'), {'kkr_id': kkr_id, 'r2_id': r2_id})
            print(f'Migrated {res_seats.rowcount} seat_records from R2 to KKR_SPECIAL for year {yr}')

            # Move cutoff_records
            res_cutoffs = db.execute(text('UPDATE cutoff_records SET round_id = :kkr_id WHERE round_id = :r2_id'), {'kkr_id': kkr_id, 'r2_id': r2_id})
            print(f'Migrated {res_cutoffs.rowcount} cutoff_records from R2 to KKR_SPECIAL for year {yr}')

            # Remove the empty standard R2 row so no standard R2 round exists
            db.execute(text('DELETE FROM counselling_rounds WHERE id = :r2_id'), {'r2_id': r2_id})
            print(f'Deleted unreferenced R2 round from counselling_rounds for year {yr}')

    # 5. Update SourceVersion counselling_round strings from R2 to KKR_SPECIAL
    res_sv = db.execute(text("UPDATE source_versions SET counselling_round = 'KKR_SPECIAL' WHERE counselling_round = 'R2'"))
    print(f'Updated {res_sv.rowcount} source_versions from R2 to KKR_SPECIAL')

    db.commit()

    # 6. Verify final counts
    kkr_seats = db.execute(text("SELECT count(s.id) FROM seat_records s JOIN counselling_rounds r ON s.round_id = r.id WHERE r.code = 'KKR_SPECIAL'")).scalar()
    kkr_cutoffs = db.execute(text("SELECT count(c.id) FROM cutoff_records c JOIN counselling_rounds r ON c.round_id = r.id WHERE r.code = 'KKR_SPECIAL'")).scalar()
    r2_seats = db.execute(text("SELECT count(s.id) FROM seat_records s JOIN counselling_rounds r ON s.round_id = r.id WHERE r.code = 'R2'")).scalar()
    r2_cutoffs = db.execute(text("SELECT count(c.id) FROM cutoff_records c JOIN counselling_rounds r ON c.round_id = r.id WHERE r.code = 'R2'")).scalar()

    print('\nVerification after migration:')
    print(f'  KKR_SPECIAL seat records:   {kkr_seats}')
    print(f'  KKR_SPECIAL cutoff records: {kkr_cutoffs}')
    print(f'  Standard R2 seat records:   {r2_seats}')
    print(f'  Standard R2 cutoff records: {r2_cutoffs}')

    db.close()

if __name__ == "__main__":
    run_migration()
