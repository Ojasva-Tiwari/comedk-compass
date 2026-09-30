"""
Comprehensive tests proving:
1. KKR documents -> KKR_SPECIAL
2. Normal R1/R3/R4 documents remain unchanged
3. KKR_SPECIAL is excluded from general counselling progression
4. No KKR record remains under standard R2
5. Idempotent re-ingestion of KKR_SPECIAL data
6. Provenance is preserved for all KKR_SPECIAL records
"""
import uuid
import pytest
from sqlalchemy import select, func

from backend.app.models.round import CounsellingRound
from backend.app.models.seat import SeatRecord
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.source import Source, SourceVersion
from backend.app.models.college import College
from backend.app.models.review import IngestionReviewItem
from backend.app.models.validation import ValidationError
from backend.app.core.enums import DocumentType, RecordStatus
from backend.app.ingestion.classifier import DocumentClassifier
from backend.app.ingestion.normalizer import Normalizer
from backend.app.ingestion.parsers.seat_and_fee_parser import SeatAndFeeParser
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.tests.test_stage2_vacancy_and_validation import make_pdf_bytes


# 1. KKR documents -> KKR_SPECIAL
def test_kkr_documents_classified_as_kkr_special():
    """Verify that all KKR / Round 2 documents classify to KKR_SPECIAL."""
    kkr_titles = [
        "Architecture Vacant Seats at beginning of Round 2",
        "Architecture Vacant Seats after Round 2 Allotment",
        "Engineering Vacant Seats Before Start of Round 2",
        "Engineering Vacant Seats after Round 2 Allotment",
        "Engineering Cut-Off Ranks after Round 2 Allotment",
        "Engineering Cut-Off Ranks after Round 2 Allotment (KKR Special)",
        "COMEDK Vacant Seats Round 2",
        "COMEDK Round 2 KKR Special Allotment",
        "COMEDK R2 KKR Vacancy Matrix",
    ]
    for title in kkr_titles:
        round_code = DocumentClassifier.extract_counselling_round(title)
        assert round_code == "KKR_SPECIAL", f"Expected KKR_SPECIAL for '{title}', got '{round_code}'"

    # Normalizer test
    for r_str in ["ROUND 2", "ROUND_2", "Round 2", "R2", "KKR_SPECIAL", "kkr special", "r2 kkr"]:
        code, name, num = Normalizer.normalize_round(r_str)
        assert code == "KKR_SPECIAL"
        assert name == "Round 2 KKR Special Allotment"
        assert num == 2

    # Parser test
    parser = SeatAndFeeParser()
    headers = ["College Code", "College Name", "Course Code & Course Name", "KKR Seats Vacant"]
    rows = [["E001", "Acharya Institute", "CS-Computer Science", "5"]]
    pdf_bytes = make_pdf_bytes(headers, rows)
    res = parser.parse(pdf_bytes, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "Engineering Vacant Seats Before Start of Round 2"
    })
    assert res.metadata["seat_records"][0]["counselling_round"] == "KKR_SPECIAL"


# 2. Normal R1/R3/R4 documents remain unchanged
def test_general_rounds_r1_r3_r4_remain_unchanged():
    """Verify that standard R1, R3, R4, and MOCK documents remain completely unchanged."""
    test_cases = [
        ("Engineering Cut-Off Ranks after Round 1 Allotment", "R1"),
        ("Engineering Vacant Seats before Round 1", "R1"),
        ("Mock Round Cutoff Ranks", "MOCK"),
        ("Engineering Cut-Off Ranks after Round 3 Allotment", "R3"),
        ("Architecture Vacant Seats after Round 3 Allotment", "R3"),
        ("Vacant seats before Round 4", "R4"),
        ("Vacant seats after Round 4 allotment", "R4"),
    ]
    for title, expected_round in test_cases:
        round_code = DocumentClassifier.extract_counselling_round(title)
        assert round_code == expected_round, f"Expected {expected_round} for '{title}', got '{round_code}'"

    # Normalizer check
    assert Normalizer.normalize_round("ROUND 1") == ("R1", "Round 1", 1)
    assert Normalizer.normalize_round("ROUND 3") == ("R3", "Round 3", 3)
    assert Normalizer.normalize_round("ROUND 4") == ("R4", "Round 4", 4)
    assert Normalizer.normalize_round("MOCK") == ("MOCK", "Mock Round", 0)


# 3. KKR_SPECIAL is excluded from general counselling progression
def test_kkr_special_excluded_from_general_counselling_progression(db, client):
    """Verify KKR_SPECIAL is flagged as is_general_round=False and excluded from default API queries."""
    # Check DB flags
    rounds = db.execute(select(CounsellingRound)).scalars().all()
    round_map = {r.code: r for r in rounds}

    assert "KKR_SPECIAL" in round_map
    assert round_map["KKR_SPECIAL"].is_general_round is False, "KKR_SPECIAL must NOT be marked as general round"

    for gen_code in ["R1", "R3", "R4"]:
        if gen_code in round_map:
            assert round_map[gen_code].is_general_round is True, f"{gen_code} must be marked as general round"

    # Check that general counselling progression in DB is strictly R1 -> R3 -> R4 for each academic year
    for yr in [2026, 2025]:
        general_rounds = db.execute(
            select(CounsellingRound.code)
            .where(CounsellingRound.is_general_round.is_(True), CounsellingRound.academic_year == yr)
            .order_by(CounsellingRound.round_number)
        ).scalars().all()
        assert "KKR_SPECIAL" not in general_rounds
        assert [r for r in general_rounds if r.startswith("R")] == ["R1", "R3", "R4"]

    kkr_round_ids = {str(r.id) for r in rounds if r.code == "KKR_SPECIAL"}

    # Test Cutoffs API excludes KKR_SPECIAL by default
    resp_default = client.get("/api/v1/cutoffs?limit=200")
    assert resp_default.status_code == 200
    for item in resp_default.json()["items"]:
        assert item["round_id"] not in kkr_round_ids, "Default cutoffs endpoint must not return KKR_SPECIAL"

    # Test Cutoffs API with round_code=KKR_SPECIAL returns KKR cutoffs
    resp_special = client.get("/api/v1/cutoffs?round_code=KKR_SPECIAL&limit=100")
    assert resp_special.status_code == 200
    assert len(resp_special.json()["items"]) > 0
    for item in resp_special.json()["items"]:
        assert item["round_id"] in kkr_round_ids

    # Test Cutoffs API with round_code=R2 returns 0 items
    resp_r2 = client.get("/api/v1/cutoffs?round_code=R2")
    assert resp_r2.status_code == 200
    assert resp_r2.json()["total"] == 0

    # Test Seats API excludes KKR_SPECIAL by default
    resp_seats_default = client.get("/api/v1/seat-records?limit=200")
    assert resp_seats_default.status_code == 200
    for item in resp_seats_default.json()["items"]:
        assert item["round_id"] not in kkr_round_ids, "Default seats endpoint must not return KKR_SPECIAL"

    # Test Seats API includes KKR_SPECIAL when include_special_rounds=true
    resp_seats_special = client.get("/api/v1/seat-records?round_code=KKR_SPECIAL&include_special_rounds=true&limit=100")
    assert resp_seats_special.status_code == 200
    assert len(resp_seats_special.json()["items"]) > 0
    for item in resp_seats_special.json()["items"]:
        assert item["round_id"] in kkr_round_ids


# 4. No KKR record remains under standard R2
def test_no_kkr_records_remain_under_standard_r2(db):
    """Verify that 0 records remain under standard R2, and all KKR records are under KKR_SPECIAL."""
    # Check standard R2 counts
    r2_seat_count = db.execute(
        select(func.count(SeatRecord.id))
        .join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "R2")
    ).scalar_one()
    assert r2_seat_count == 0, f"Expected 0 seat records under R2, found {r2_seat_count}"

    r2_cutoff_count = db.execute(
        select(func.count(CutoffRecord.id))
        .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "R2")
    ).scalar_one()
    assert r2_cutoff_count == 0, f"Expected 0 cutoff records under R2, found {r2_cutoff_count}"

    r2_round_exists = db.execute(
        select(func.count(CounsellingRound.id)).where(CounsellingRound.code == "R2")
    ).scalar_one()
    assert r2_round_exists == 0, "Standard R2 round row should not exist in counselling_rounds"

    # Check KKR_SPECIAL counts match audited totals
    kkr_seat_count = db.execute(
        select(func.count(SeatRecord.id))
        .join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "KKR_SPECIAL")
    ).scalar_one()
    assert kkr_seat_count == 2172, f"Expected 2172 KKR_SPECIAL seat records, got {kkr_seat_count}"

    kkr_cutoff_count = db.execute(
        select(func.count(CutoffRecord.id))
        .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "KKR_SPECIAL")
    ).scalar_one()
    assert kkr_cutoff_count == 185, f"Expected 185 KKR_SPECIAL cutoff records, got {kkr_cutoff_count}"


# 5. Idempotent re-ingestion
def test_idempotent_reingestion_kkr_special(db):
    """Verify re-ingesting a KKR_SPECIAL vacancy document produces 0 duplicates and preserves existing data."""
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()

    sv = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/kkr-special-test.pdf",
        source_title="Architecture Vacant Seats at beginning of Round 2 Test",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.VACANT_SEATS_PDF.value,
        counselling_round="KKR_SPECIAL",
        content_hash="hash_kkr_special_idempotency_test",
        local_path="/tmp/kkr_special_test.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.DOWNLOADED.value
    )
    db.add(sv)
    db.flush()

    try:
        headers = ["College Code", "College Name", "Course Code & Course Name", "KKR Seats Vacant"]
        rows = [
            ["E001", "Acharya Institute", "CS-Computer Science", "2"],
            ["E002", "BMS College", "CS-Computer Science", "4"],
            ["E003", "Ramaiah Institute", "CS-Computer Science", "1"],
            ["E004", "RV College", "CS-Computer Science", "3"],
        ]
        for c_code, c_name in [("E001", "Acharya"), ("E002", "BMS"), ("E003", "Ramaiah"), ("E004", "RV")]:
            if not db.execute(select(College).where(College.code == c_code)).scalar_one_or_none():
                db.add(College(code=c_code, name=c_name, original_name=c_name, institution_type="ENGINEERING"))
        db.flush()

        pdf_bytes = make_pdf_bytes(headers, rows)
        parser = SeatAndFeeParser()
        parse_res = parser.parse(pdf_bytes, {
            "academic_year": 2026,
            "document_type": DocumentType.VACANT_SEATS_PDF.value,
            "source_title": sv.source_title
        })

        # Run 1
        stats1 = {}
        report1 = pipeline._ingest_seat_and_fee_records(parse_res, sv, uuid.uuid4(), stats1)
        assert report1["status"] == "PUBLISHED"
        assert report1["published_seats"] == 4

        count_after_1 = db.execute(
            select(func.count(SeatRecord.id)).where(SeatRecord.source_version_id == sv.id)
        ).scalar_one()
        assert count_after_1 == 4

        # Verify round is KKR_SPECIAL
        sample_seat = db.execute(
            select(SeatRecord).where(SeatRecord.source_version_id == sv.id).limit(1)
        ).scalar_one()
        round_obj = db.execute(
            select(CounsellingRound).where(CounsellingRound.id == sample_seat.round_id)
        ).scalar_one()
        assert round_obj.code == "KKR_SPECIAL"

        # Run 2 (re-ingestion)
        stats2 = {}
        report2 = pipeline._ingest_seat_and_fee_records(parse_res, sv, uuid.uuid4(), stats2)
        assert report2["status"] == "PUBLISHED"
        assert report2["published_seats"] == 0, "Re-ingestion must publish 0 new seat duplicates"

        count_after_2 = db.execute(
            select(func.count(SeatRecord.id)).where(SeatRecord.source_version_id == sv.id)
        ).scalar_one()
        assert count_after_2 == 4, "Total count must remain exactly 4 after re-ingestion"
    finally:
        db.query(SeatRecord).filter(SeatRecord.source_version_id == sv.id).delete()
        db.query(IngestionReviewItem).filter(IngestionReviewItem.source_version_id == sv.id).delete()
        db.query(ValidationError).filter(ValidationError.source_version_id == sv.id).delete()
        db.delete(sv)
        db.commit()


# 6. Provenance is preserved
def test_provenance_preserved_for_kkr_special(db):
    """Verify that all KKR_SPECIAL records preserve provenance to official SourceVersion records."""
    # Check seat records
    kkr_seats = db.execute(
        select(SeatRecord)
        .join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "KKR_SPECIAL")
    ).scalars().all()
    assert len(kkr_seats) == 2172

    # Check that every record has a source_version_id
    sv_ids = {s.source_version_id for s in kkr_seats}
    assert None not in sv_ids
    assert len(sv_ids) > 0

    # Verify all linked source versions exist, have content_hash, and have counselling_round == KKR_SPECIAL
    for sv_id in sv_ids:
        sv = db.execute(select(SourceVersion).where(SourceVersion.id == sv_id)).scalar_one_or_none()
        assert sv is not None, f"SourceVersion {sv_id} must exist"
        assert sv.counselling_round == "KKR_SPECIAL", f"SourceVersion {sv_id} counselling_round must be KKR_SPECIAL"
        assert sv.content_hash is not None and len(sv.content_hash) == 64, "SourceVersion must have valid SHA-256"
        assert sv.source_url.startswith("http"), "SourceVersion must have a valid source URL"
        assert sv.publisher == "COMEDK", "Publisher must be COMEDK"

    # Check cutoff records
    kkr_cutoffs = db.execute(
        select(CutoffRecord)
        .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "KKR_SPECIAL")
    ).scalars().all()
    assert len(kkr_cutoffs) == 185

    cutoff_sv_ids = {c.source_version_id for c in kkr_cutoffs}
    assert None not in cutoff_sv_ids
    for sv_id in cutoff_sv_ids:
        sv = db.execute(select(SourceVersion).where(SourceVersion.id == sv_id)).scalar_one_or_none()
        assert sv is not None
        assert sv.counselling_round == "KKR_SPECIAL"
