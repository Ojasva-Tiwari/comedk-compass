import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, func

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.models import SourceVersion, IngestionRun, SeatRecord
from backend.app.core.enums import DocumentType, RunStatus, RecordStatus
from backend.app.ingestion.parsers.seat_and_fee_parser import SeatAndFeeParser
from backend.app.ingestion.classifier import DocumentClassifier
from backend.app.ingestion.pipeline import IngestionPipeline


def ingest_official_vacancies():
    print("=" * 80)
    print("INGESTING OFFICIAL 2026 COMEDK VACANCY DOCUMENTS")
    print("=" * 80)

    db = SessionLocal()
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    parser = SeatAndFeeParser()

    folder = "data/raw/comedk/2026/seat_matrix"
    files = sorted([f for f in os.listdir(folder) if "vacan" in f.lower()])
    print(f"Discovered {len(files)} official vacancy documents in archive.")

    run_record = IngestionRun(
        started_at=datetime.now(timezone.utc),
        status=RunStatus.RUNNING.value,
        parser_version=settings.PARSER_VERSION
    )
    db.add(run_record)
    db.commit()
    db.refresh(run_record)

    stats = {
        "records_parsed": 0,
        "records_validated": 0,
        "records_published": 0,
        "records_rejected": 0,
        "records_needs_review": 0,
        "validation_errors": 0,
        "anomalies": 0,
        "documents_parsed": 0,
        "documents_needs_review": 0,
    }

    published_docs = 0
    needs_review_docs = 0

    for i, f in enumerate(files, 1):
        rel_path = os.path.join(folder, f)
        abs_path = os.path.abspath(rel_path)

        with open(rel_path, "rb") as fp:
            pdf_bytes = fp.read()

        c_round = DocumentClassifier.extract_counselling_round(f)

        # Locate existing SourceVersion
        sv = db.execute(select(SourceVersion).where(
            (SourceVersion.local_path == rel_path) |
            (SourceVersion.local_path == rel_path.replace("/", "\\\\")) |
            (SourceVersion.local_path.like(f"%{f}%"))
        )).scalar_one_or_none()

        if not sv:
            print(f"[{i:2}/{len(files)}] WARNING: No existing SourceVersion found for {f}")
            continue

        # Update document_type and round on the SourceVersion
        sv.document_type = DocumentType.VACANT_SEATS_PDF.value
        sv.counselling_round = c_round
        db.flush()

        # Parse with updated vacancy parser
        parse_res = parser.parse(pdf_bytes, {
            "academic_year": 2026,
            "document_type": DocumentType.VACANT_SEATS_PDF.value,
            "source_title": f,
            "counselling_round": c_round,
            "program_type": DocumentClassifier.extract_program_type(f)
        })

        # Ingest and validate through pipeline fail-closed mechanism
        report = pipeline._ingest_seat_and_fee_records(
            parse_res=parse_res,
            sv=sv,
            run_id=run_record.id,
            stats=stats
        )

        status = report.get("status")
        published_seats = report.get("published_seats", 0)
        candidate_records = report.get("candidate_records", 0)

        if status == "PUBLISHED":
            published_docs += 1
            print(f"[{i:2}/{len(files)}] OK: {f[:55]:<55} | Round: {c_round:4} | Candidates: {candidate_records:4} | Published: {published_seats:4}")
        else:
            needs_review_docs += 1
            print(f"[{i:2}/{len(files)}] NEEDS_REVIEW: {f[:55]:<55} | Reason: {report.get('failure_reason')}")

        db.commit()

    run_record.completed_at = datetime.now(timezone.utc)
    run_record.status = RunStatus.SUCCESS.value if needs_review_docs == 0 else RunStatus.PARTIAL_SUCCESS.value
    run_record.records_parsed = stats["records_parsed"]
    run_record.records_validated = stats["records_validated"]
    run_record.records_published = stats["records_published"]
    run_record.records_rejected = stats["records_rejected"]
    run_record.records_needs_review = stats["records_needs_review"]
    run_record.validation_errors_count = stats["validation_errors"]
    run_record.anomalies_count = stats["anomalies"]
    db.commit()

    print("\n" + "=" * 80)
    print("INGESTION COMPLETE SUMMARY")
    print("=" * 80)
    print(f"Documents Processed:     {len(files)}")
    print(f"Documents Published:     {published_docs}")
    print(f"Documents Needs Review:  {needs_review_docs}")
    print(f"Total Seats Published:   {stats['records_published']}")

    # Final DB verification
    total_seats = db.execute(select(func.count(SeatRecord.id))).scalar_one()
    vacant_seats = db.execute(
        select(func.count(SeatRecord.id)).where(SeatRecord.vacant_seats.isnot(None))
    ).scalar_one()
    total_with_total_seats = db.execute(
        select(func.count(SeatRecord.id)).where(SeatRecord.total_seats.isnot(None))
    ).scalar_one()

    from backend.app.models.round import CounsellingRound
    print(f"\nPOSTGRESQL SEAT_RECORDS VERIFICATION:")
    print(f"  Total seat_records in DB:              {total_seats}")
    print(f"  Seat records with total_seats:          {total_with_total_seats}")
    print(f"  Seat records with vacant_seats IS NOT NULL: {vacant_seats}")

    print("\nVACANT SEATS BREAKDOWN BY ROUND:")
    round_counts = db.execute(
        select(CounsellingRound.code, CounsellingRound.is_general_round, func.count(SeatRecord.id))
        .join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id)
        .where(SeatRecord.vacant_seats.isnot(None))
        .group_by(CounsellingRound.code, CounsellingRound.is_general_round)
        .order_by(CounsellingRound.code)
    ).all()
    for code, is_gen, count in round_counts:
        gen_str = "GENERAL" if is_gen else "SPECIAL_QUOTA"
        print(f"  {code:15} ({gen_str:13}): {count:5} records")

    r2_count = db.execute(
        select(func.count(SeatRecord.id))
        .join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "R2")
    ).scalar_one()
    print(f"\n  Standard R2 seat records: {r2_count} (must be 0)")
    print("=" * 80)

    db.close()


if __name__ == "__main__":
    ingest_official_vacancies()
