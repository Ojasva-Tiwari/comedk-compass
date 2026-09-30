import uuid
import pytest
from pathlib import Path
from sqlalchemy import select, func

from backend.app.core.enums import DocumentType, RecordStatus
from backend.app.ingestion.classifier import DocumentClassifier
from backend.app.ingestion.parsers.cutoff_pdf_parser import CutoffPDFParser
from backend.app.ingestion.validator import DataValidator
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.source import SourceVersion
from backend.app.models.round import CounsellingRound
from backend.app.models.category import Category
from backend.app.models.college import College
from backend.app.models.branch import Branch

HISTORICAL_2025_SV_ID = uuid.UUID("92eda924-2802-4501-8ad3-682db2ec75d1")
HISTORICAL_2025_PDF_REL = Path("data/raw/comedk/2026/cutoff/2025-Engineering_Cut-Off_Ranks-After-All-Rounds._Notified-on-07.07.2026.pdf")
HISTORICAL_2025_HASH = "051ffd4a13148052b811cbe18c6dbc700195a5d88c001205e03d79af4eedce1f"

def test_2025_document_classification():
    title = "2025 - Engineering Cut-off Ranks After All Rounds. Notified on 07.07.2026 Click Here"
    url = "https://comedk.org/uploads/2025-Engineering Cut-Off Ranks-After-All-Rounds. Notified-on-07.07.2026.pdf"
    combined = f"{title} {url}"

    doc_type = DocumentClassifier.classify(combined)
    c_round = DocumentClassifier.extract_counselling_round(combined)
    academic_year = DocumentClassifier.extract_academic_year(combined, default=2026)

    assert doc_type == DocumentType.CUTOFF_PDF.value
    assert c_round == "R4"
    assert academic_year == 2025

def test_2025_cutoff_pdf_parsing():
    root = Path(__file__).resolve().parents[2]
    pdf_path = root / HISTORICAL_2025_PDF_REL
    assert pdf_path.exists(), f"Historical 2025 PDF not found at {pdf_path}"

    with open(pdf_path, "rb") as f:
        content = f.read()

    parser = CutoffPDFParser()
    parse_res = parser.parse(content, {
        "academic_year": 2025,
        "counselling_round": "R4"
    })

    assert parse_res.status == RecordStatus.PARSED
    assert len(parse_res.records) == 637
    assert parse_res.metadata["pdf_page_count"] == 55
    assert parse_res.metadata["raw_rows_detected"] == 1010
    assert len(parse_res.discovered_colleges) == 101
    assert len(parse_res.discovered_branches) == 46

    # Every record must factually have academic_year = 2025 and round_code = 'R4'
    for r in parse_res.records:
        assert r["academic_year"] == 2025
        assert r["round_code"] == "R4"
        assert r["closing_rank"] > 0
        assert r["category_code"] in ("GM", "KKR")

def test_2025_cutoff_validation(db):
    college_map = {c.code: c.id for c in db.execute(select(College)).scalars().all()}
    branch_map = {b.code: b.id for b in db.execute(select(Branch)).scalars().all()}
    category_map = {c.code: c.id for c in db.execute(select(Category)).scalars().all()}

    validator = DataValidator(
        known_college_codes=set(college_map.keys()),
        known_branch_codes=set(branch_map.keys()),
        known_categories=set(category_map.keys()),
    )

    root = Path(__file__).resolve().parents[2]
    pdf_path = root / HISTORICAL_2025_PDF_REL
    with open(pdf_path, "rb") as f:
        content = f.read()

    parser = CutoffPDFParser()
    parse_res = parser.parse(content, {
        "academic_year": 2025,
        "counselling_round": "R4"
    })

    valid_records, errors, anomalies = validator.validate_cutoff_records(
        records=parse_res.records,
        academic_year=2025
    )

    assert len(valid_records) == 637
    assert len(errors) == 0
    assert len(anomalies) == 0

    completeness_errors = validator.validate_batch_completeness(
        doc_type="CUTOFF_PDF",
        extracted_count=len(valid_records),
        program_type="ENGINEERING"
    )
    assert len(completeness_errors) == 0

def test_2025_counselling_rounds_seeded(db):
    rounds_2025 = {
        r.code: r for r in db.execute(
            select(CounsellingRound).where(CounsellingRound.academic_year == 2025)
        ).scalars().all()
    }

    assert "R4" in rounds_2025
    assert rounds_2025["R4"].is_general_round is True
    assert rounds_2025["R4"].round_number == 4

    assert "R1" in rounds_2025
    assert rounds_2025["R1"].is_general_round is True

    assert "R3" in rounds_2025
    assert rounds_2025["R3"].is_general_round is True

    assert "KKR_SPECIAL" in rounds_2025
    assert rounds_2025["KKR_SPECIAL"].is_general_round is False

def test_2025_cutoff_db_provenance_and_quality(db):
    # Total count in DB
    total_2025 = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.academic_year == 2025)
    ).scalar()
    assert total_2025 == 637

    # Category breakdown
    gm_count = db.execute(
        select(func.count(CutoffRecord.id))
        .join(Category, CutoffRecord.category_id == Category.id)
        .where(CutoffRecord.academic_year == 2025, Category.code == "GM")
    ).scalar()
    kkr_count = db.execute(
        select(func.count(CutoffRecord.id))
        .join(Category, CutoffRecord.category_id == Category.id)
        .where(CutoffRecord.academic_year == 2025, Category.code == "KKR")
    ).scalar()
    assert gm_count == 459
    assert kkr_count == 178
    assert gm_count + kkr_count == 637

    # Round breakdown: all belong to R4
    r4_count = db.execute(
        select(func.count(CutoffRecord.id))
        .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        .where(CutoffRecord.academic_year == 2025, CounsellingRound.code == "R4")
    ).scalar()
    assert r4_count == 637

    # SourceVersion linkage and SHA-256
    sv_records = db.execute(
        select(func.count(CutoffRecord.id))
        .where(CutoffRecord.source_version_id == HISTORICAL_2025_SV_ID)
    ).scalar()
    assert sv_records == 637

    sv = db.execute(select(SourceVersion).where(SourceVersion.id == HISTORICAL_2025_SV_ID)).scalar_one()
    assert sv.academic_year == 2025
    assert sv.counselling_round == "R4"
    assert sv.content_hash == HISTORICAL_2025_HASH
    assert sv.processing_status == RecordStatus.PUBLISHED.value

    # Quality: 0 invalid closing ranks, 0 missing foreign keys
    invalid = db.execute(
        select(func.count(CutoffRecord.id))
        .where(CutoffRecord.academic_year == 2025, CutoffRecord.closing_rank <= 0)
    ).scalar()
    assert invalid == 0

    missing_cols = db.execute(
        select(func.count(CutoffRecord.id))
        .where(
            CutoffRecord.academic_year == 2025,
            (CutoffRecord.college_id.is_(None)) |
            (CutoffRecord.branch_id.is_(None)) |
            (CutoffRecord.category_id.is_(None)) |
            (CutoffRecord.round_id.is_(None)) |
            (CutoffRecord.source_version_id.is_(None))
        )
    ).scalar()
    assert missing_cols == 0

    # Duplicates check
    dupes = db.execute(
        select(
            CutoffRecord.college_id,
            CutoffRecord.branch_id,
            CutoffRecord.category_id,
            CutoffRecord.round_id,
            CutoffRecord.academic_year,
            func.count(CutoffRecord.id)
        )
        .where(CutoffRecord.academic_year == 2025)
        .group_by(
            CutoffRecord.college_id,
            CutoffRecord.branch_id,
            CutoffRecord.category_id,
            CutoffRecord.round_id,
            CutoffRecord.academic_year
        )
        .having(func.count(CutoffRecord.id) > 1)
    ).all()
    assert len(dupes) == 0

def test_2025_idempotent_reingestion(db):
    pipeline = IngestionPipeline(db=db, academic_year=2025)
    report = pipeline.ingest_source_version(HISTORICAL_2025_SV_ID)

    assert report["published_records"] == 0
    assert report["verified_unchanged_records"] == 637
    assert report["factual_changes"] == 0

    total_2025 = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.academic_year == 2025)
    ).scalar()
    assert total_2025 == 637

def test_2026_records_strictly_unchanged(db):
    total_2026 = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.academic_year == 2026)
    ).scalar()
    assert total_2026 == 3556
