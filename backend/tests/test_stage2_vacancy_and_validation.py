import uuid
import pytest
from decimal import Decimal
import pymupdf
from sqlalchemy import select, func

from backend.app.core.enums import RecordStatus, DocumentType, ProgramType, ValidationSeverity, FailureReason
from backend.app.models.source import Source, SourceVersion
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.category import Category
from backend.app.models.round import CounsellingRound
from backend.app.models.seat import SeatRecord
from backend.app.models.fee import FeeRecord
from backend.app.models.review import IngestionReviewItem
from backend.app.ingestion.parsers.seat_and_fee_parser import SeatAndFeeParser
from backend.app.ingestion.validator import DataValidator
from backend.app.ingestion.pipeline import IngestionPipeline


def make_pdf_bytes(headers, rows):
    """Generates valid vector PDF bytes with table borders detected by PyMuPDF find_tables()."""
    doc = pymupdf.open()
    page = doc.new_page()
    all_rows = [headers] + rows
    x0, y0 = 50, 50
    num_cols = len(headers)
    col_w = [500 // num_cols] * num_cols
    row_h = 22
    for r_idx, r in enumerate(all_rows):
        y = y0 + r_idx * row_h
        for c_idx, cell in enumerate(r):
            x = x0 + sum(col_w[:c_idx])
            w = col_w[c_idx]
            page.draw_rect(pymupdf.Rect(x, y, x + w, y + row_h))
            page.insert_text(pymupdf.Point(x + 3, y + 14), str(cell), fontsize=7)
    return doc.tobytes()


# 1. Test 4-column vacancy PDF extraction
def test_4_column_vacancy_pdf_extraction():
    parser = SeatAndFeeParser()

    # 4-col with Total Seats Vacant
    headers_total = ["College Code", "College Name", "Course Code & Course Name", "Total Seats Vacant"]
    rows_total = [
        ["E001", "Acharya Institute of Technology", "AE-Aeronautical Engineering", "12"],
        ["E002", "BMS College of Engineering", "CS-Computer Science and Engineering", "5"]
    ]
    pdf_total = make_pdf_bytes(headers_total, rows_total)
    res_total = parser.parse(pdf_total, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "Architecture Vacant Seats After Round 3 Allotment"
    })
    assert res_total.status == RecordStatus.PARSED
    seats_total = res_total.metadata["seat_records"]
    assert len(seats_total) == 2
    assert seats_total[0]["vacant_seats"] == 12
    assert seats_total[0]["gm_seats"] is None  # Not present in PDF, not fabricated
    assert seats_total[0]["kkr_seats"] is None
    assert seats_total[0]["category_code"] is None
    assert seats_total[0]["counselling_round"] == "R3"

    # 4-col with KKR Seats Vacant
    headers_kkr = ["College Code", "College Name", "Course Code & Course Name", "KKR Seats Vacant"]
    rows_kkr = [
        ["E001", "Acharya Institute of Technology", "AE-Aeronautical Engineering", "3"]
    ]
    pdf_kkr = make_pdf_bytes(headers_kkr, rows_kkr)
    res_kkr = parser.parse(pdf_kkr, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "Engineering Vacant Seats Before Start of Round 2"
    })
    seats_kkr = res_kkr.metadata["seat_records"]
    assert len(seats_kkr) == 1
    assert seats_kkr[0]["vacant_seats"] == 3
    assert seats_kkr[0]["kkr_seats"] == 3
    assert seats_kkr[0]["gm_seats"] is None  # Not present in PDF, not fabricated
    assert seats_kkr[0]["category_code"] == "KKR"
    assert seats_kkr[0]["counselling_round"] == "KKR_SPECIAL"

    # 4-col with GM Seats
    headers_gm = ["College Code", "College Name", "Course Code & Course Name", "Total Vacant Seats - GM"]
    rows_gm = [
        ["E001", "Acharya Institute of Technology", "AE-Aeronautical Engineering", "9"]
    ]
    pdf_gm = make_pdf_bytes(headers_gm, rows_gm)
    res_gm = parser.parse(pdf_gm, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "Engineering Vacant Seats after Round 3 Allotment"
    })
    seats_gm = res_gm.metadata["seat_records"]
    assert len(seats_gm) == 1
    assert seats_gm[0]["vacant_seats"] == 9
    assert seats_gm[0]["gm_seats"] == 9
    assert seats_gm[0]["kkr_seats"] is None  # Not present in PDF, not fabricated
    assert seats_gm[0]["category_code"] == "GM"
    assert seats_gm[0]["counselling_round"] == "R3"


# 2. Test 5-column vacancy PDF extraction
def test_5_column_vacancy_pdf_extraction():
    parser = SeatAndFeeParser()
    headers = ["College Code", "College Name", "Course Code & Course Name", "GM Seats", "KKR Seats"]
    rows = [
        ["E001", "Acharya Institute of Technology", "AE-Aeronautical Engineering", "10", "4"],
        ["E002", "BMS College of Engineering", "CS-Computer Science and Engineering", "2", "1"]
    ]
    pdf_bytes = make_pdf_bytes(headers, rows)
    res = parser.parse(pdf_bytes, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "COMEDK Vacant Seats Round 2"
    })
    assert res.status == RecordStatus.PARSED
    seats = res.metadata["seat_records"]
    assert len(seats) == 2
    assert seats[0]["vacant_seats"] == 14  # 10 + 4
    assert seats[0]["gm_seats"] == 10
    assert seats[0]["kkr_seats"] == 4
    assert seats[0]["counselling_round"] == "KKR_SPECIAL"
    assert seats[1]["vacant_seats"] == 3   # 2 + 1
    assert seats[1]["gm_seats"] == 2
    assert seats[1]["kkr_seats"] == 1


# 3. Test 6-column vacancy PDF extraction
def test_6_column_vacancy_pdf_extraction():
    parser = SeatAndFeeParser()
    headers = ["College Code", "College Name", "Course Code & Course Name", "Total Seats Vacant", "GM Seats Vacant", "KKR Seats Vacant"]
    rows = [
        ["E001", "Acharya Institute of Technology", "AE-Aeronautical Engineering", "8", "6", "2"]
    ]
    pdf_bytes = make_pdf_bytes(headers, rows)
    res = parser.parse(pdf_bytes, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "Architecture Vacant Seats After Round-1 Allotment"
    })
    assert res.status == RecordStatus.PARSED
    seats = res.metadata["seat_records"]
    assert len(seats) == 1
    assert seats[0]["vacant_seats"] == 8
    assert seats[0]["gm_seats"] == 6
    assert seats[0]["kkr_seats"] == 2
    assert seats[0]["counselling_round"] == "R1"


# 4. Test malformed vacancy PDF
def test_malformed_vacancy_pdf():
    parser = SeatAndFeeParser()
    headers = ["College Code", "College Name", "Course Code & Course Name", "Total Seats Vacant"]
    rows = [
        ["E001", "Acharya Institute of Technology", "AE-Aeronautical Engineering", "INVALID_NOT_A_NUMBER"]
    ]
    pdf_bytes = make_pdf_bytes(headers, rows)
    res = parser.parse(pdf_bytes, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "Vacant Seats Corrupted"
    })
    assert res.status == RecordStatus.NEEDS_REVIEW
    assert len(res.errors) >= 1
    assert "Malformed vacancy row" in res.errors[0]["error"]


# 5. Test zero-record vacancy PDF
def test_zero_record_vacancy_pdf():
    parser = SeatAndFeeParser()
    headers = ["College Code", "College Name", "Course Code & Course Name", "Total Seats Vacant"]
    pdf_bytes = make_pdf_bytes(headers, [])  # Header only, no data rows
    res = parser.parse(pdf_bytes, {
        "academic_year": 2026,
        "document_type": DocumentType.VACANT_SEATS_PDF.value,
        "source_title": "Empty Vacant Seats Document"
    })
    assert res.status == RecordStatus.NEEDS_REVIEW
    assert len(res.metadata.get("seat_records", [])) == 0


# 6. Test DataValidator validate_seat_records (valid and invalid)
def test_validate_seat_records():
    validator = DataValidator(
        known_college_codes={"E001", "E002"},
        known_branch_codes={"AE", "CS"},
        known_categories={"GM", "KKR"}
    )

    # Valid vacancy record
    valid_recs = [
        {
            "college_code": "E001",
            "branch_code": "AE",
            "counselling_round": "R1",
            "category_code": "GM",
            "academic_year": 2026,
            "total_seats": None,
            "vacant_seats": 5,
            "gm_seats": 5,
            "row_identifier": "row_1"
        }
    ]
    v, errs, anoms = validator.validate_seat_records(valid_recs, 2026)
    assert len(v) == 1
    assert len(errs) == 0

    # Missing college code
    v, errs, _ = validator.validate_seat_records([{"college_code": "", "branch_code": "AE", "vacant_seats": 5}], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "MISSING_COLLEGE_CODE"

    # Missing branch code
    v, errs, _ = validator.validate_seat_records([{"college_code": "E001", "branch_code": "", "vacant_seats": 5}], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "MISSING_BRANCH_CODE"

    # Unknown college
    v, errs, _ = validator.validate_seat_records([{"college_code": "E999", "branch_code": "AE", "vacant_seats": 5}], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "UNKNOWN_COLLEGE_CODE"

    # Unknown branch
    v, errs, _ = validator.validate_seat_records([{"college_code": "E001", "branch_code": "ZZ", "vacant_seats": 5}], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "UNKNOWN_BRANCH_CODE"

    # Negative total seats
    v, errs, _ = validator.validate_seat_records([{"college_code": "E001", "branch_code": "AE", "total_seats": -1}], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "INVALID_TOTAL_SEATS"

    # Negative vacant seats
    v, errs, _ = validator.validate_seat_records([{"college_code": "E001", "branch_code": "AE", "vacant_seats": -5}], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "INVALID_VACANT_SEATS"

    # Vacancy exceeds total seats
    v, errs, _ = validator.validate_seat_records([{"college_code": "E001", "branch_code": "AE", "total_seats": 10, "vacant_seats": 15}], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "VACANCY_EXCEEDS_TOTAL_SEATS"

    # Sum of GM + KKR exceeds vacant seats
    v, errs, _ = validator.validate_seat_records([{
        "college_code": "E001", "branch_code": "AE", "vacant_seats": 5, "gm_seats": 4, "kkr_seats": 3
    }], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "SEAT_SUM_EXCEEDS_VACANCY"


# 7. Test DataValidator validate_fee_records (valid and invalid)
def test_validate_fee_records():
    validator = DataValidator(
        known_college_codes={"E001", "E002"},
        known_branch_codes={"AE", "CS"},
        known_categories={"GM"}
    )

    # Valid full fee record
    valid_recs = [
        {
            "college_code": "E001",
            "branch_code": "CS",
            "academic_year": 2026,
            "total_fee": Decimal("322000"),
            "tuition_fee": Decimal("302000"),
            "other_fee": Decimal("20000"),
            "row_identifier": "fee_1"
        }
    ]
    v, errs, _ = validator.validate_fee_records(valid_recs, 2026)
    assert len(v) == 1
    assert len(errs) == 0

    # Valid fee record where tuition_fee and other_fee are legitimately absent
    v, errs, _ = validator.validate_fee_records([{
        "college_code": "E001",
        "branch_code": "CS",
        "academic_year": 2026,
        "total_fee": Decimal("250000"),
        "tuition_fee": None,
        "other_fee": None,
        "row_identifier": "fee_no_breakdown"
    }], 2026)
    assert len(v) == 1
    assert len(errs) == 0

    # Negative total fee
    v, errs, _ = validator.validate_fee_records([{
        "college_code": "E001", "branch_code": "CS", "total_fee": Decimal("-100")
    }], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "INVALID_TOTAL_FEE"

    # Tuition exceeds total fee
    v, errs, _ = validator.validate_fee_records([{
        "college_code": "E001",
        "branch_code": "CS",
        "total_fee": Decimal("100000"),
        "tuition_fee": Decimal("150000")
    }], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "TUITION_EXCEEDS_TOTAL_FEE"

    # Components mismatch: 200,000 + 50,000 != 300,000
    v, errs, _ = validator.validate_fee_records([{
        "college_code": "E001",
        "branch_code": "CS",
        "total_fee": Decimal("300000"),
        "tuition_fee": Decimal("200000"),
        "other_fee": Decimal("50000")
    }], 2026)
    assert len(v) == 0
    assert errs[0].error_code == "FEE_COMPONENTS_MISMATCH"


# 8. Test duplicate seat and fee records detection
def test_duplicate_seat_and_fee_records():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )

    # Duplicate seat records
    duplicate_seats = [
        {"college_code": "E001", "branch_code": "CS", "counselling_round": "R1", "category_code": "GM", "academic_year": 2026, "vacant_seats": 5},
        {"college_code": "E001", "branch_code": "CS", "counselling_round": "R1", "category_code": "GM", "academic_year": 2026, "vacant_seats": 3}
    ]
    v_seats, err_seats, _ = validator.validate_seat_records(duplicate_seats, 2026)
    assert len(v_seats) == 1
    assert len(err_seats) == 1
    assert err_seats[0].error_code == "DUPLICATE_LOGICAL_RECORD"

    # Duplicate fee records
    duplicate_fees = [
        {"college_code": "E001", "branch_code": "CS", "academic_year": 2026, "total_fee": Decimal("200000")},
        {"college_code": "E001", "branch_code": "CS", "academic_year": 2026, "total_fee": Decimal("220000")}
    ]
    v_fees, err_fees, _ = validator.validate_fee_records(duplicate_fees, 2026)
    assert len(v_fees) == 1
    assert len(err_fees) == 1
    assert err_fees[0].error_code == "DUPLICATE_LOGICAL_RECORD"


# 9. Test fail-closed zero-record vacancy ingestion
def test_fail_closed_zero_record_vacancy_ingestion(db):
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()

    sv = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/empty-vacancy.pdf",
        source_title="Engineering Vacant Seats Empty",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.VACANT_SEATS_PDF.value,
        counselling_round="KKR_SPECIAL",
        content_hash="hash_empty_vacancy_test",
        local_path="/tmp/empty_vacancy.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.DOWNLOADED.value
    )
    db.add(sv)
    db.flush()

    try:
        headers = ["College Code", "College Name", "Course Code & Course Name", "Total Seats Vacant"]
        pdf_bytes = make_pdf_bytes(headers, [])  # Zero data rows
        parser = SeatAndFeeParser()
        parse_res = parser.parse(pdf_bytes, {
            "academic_year": 2026,
            "document_type": DocumentType.VACANT_SEATS_PDF.value,
            "source_title": sv.source_title
        })

        stats = {}
        report = pipeline._ingest_seat_and_fee_records(parse_res, sv, uuid.uuid4(), stats)

        assert report["status"] == "NEEDS_REVIEW"
        assert sv.processing_status == RecordStatus.NEEDS_REVIEW.value

        # Verify review item was created
        review_item = db.execute(
            select(IngestionReviewItem).where(IngestionReviewItem.source_version_id == sv.id)
        ).scalar_one_or_none()
        assert review_item is not None
        assert review_item.document_type == DocumentType.VACANT_SEATS_PDF.value
    finally:
        db.execute(select(IngestionReviewItem).where(IngestionReviewItem.source_version_id == sv.id))
        from backend.app.models.validation import ValidationError
        db.query(IngestionReviewItem).filter(IngestionReviewItem.source_version_id == sv.id).delete()
        db.query(ValidationError).filter(ValidationError.source_version_id == sv.id).delete()
        db.delete(sv)
        db.commit()


# 10. Test fail-closed malformed vacancy ingestion
def test_fail_closed_malformed_vacancy_ingestion(db):
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()

    sv = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/malformed-vacancy.pdf",
        source_title="Engineering Vacant Seats Malformed",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.VACANT_SEATS_PDF.value,
        counselling_round="KKR_SPECIAL",
        content_hash="hash_malformed_vacancy_test",
        local_path="/tmp/malformed_vacancy.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.DOWNLOADED.value
    )
    db.add(sv)
    db.flush()

    try:
        headers = ["College Code", "College Name", "Course Code & Course Name", "Total Seats Vacant"]
        rows = [["E001", "Acharya Institute of Technology", "AE-Aeronautical Engineering", "CORRUPTED_TEXT"]]
        pdf_bytes = make_pdf_bytes(headers, rows)
        parser = SeatAndFeeParser()
        parse_res = parser.parse(pdf_bytes, {
            "academic_year": 2026,
            "document_type": DocumentType.VACANT_SEATS_PDF.value,
            "source_title": sv.source_title
        })

        stats = {}
        report = pipeline._ingest_seat_and_fee_records(parse_res, sv, uuid.uuid4(), stats)

        assert report["status"] == "NEEDS_REVIEW"
        assert sv.processing_status == RecordStatus.NEEDS_REVIEW.value

        review_item = db.execute(
            select(IngestionReviewItem).where(IngestionReviewItem.source_version_id == sv.id)
        ).scalar_one_or_none()
        assert review_item is not None
        assert review_item.failure_reason == FailureReason.MALFORMED_ROW.value
    finally:
        from backend.app.models.validation import ValidationError
        db.query(IngestionReviewItem).filter(IngestionReviewItem.source_version_id == sv.id).delete()
        db.query(ValidationError).filter(ValidationError.source_version_id == sv.id).delete()
        db.delete(sv)
        db.commit()


# 11. Test idempotent vacancy re-ingestion
def test_idempotent_vacancy_reingestion(db):
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()
    college = db.execute(select(College).where(College.code == "E001")).scalar_one()
    branch = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one()

    sv = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/idempotent-vacancy.pdf",
        source_title="Architecture Vacant Seats Idempotent Test",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.VACANT_SEATS_PDF.value,
        counselling_round="R1",
        content_hash="hash_idempotent_vacancy_test",
        local_path="/tmp/idempotent_vacancy.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.DOWNLOADED.value
    )
    db.add(sv)
    db.flush()

    try:
        headers = ["College Code", "College Name", "Course Code & Course Name", "Total Seats Vacant"]
        # 4 rows to satisfy Architecture completeness threshold (>= 4)
        rows = [
            ["E001", "Acharya Institute", "CS-Computer Science", "3"],
            ["E002", "BMS College", "CS-Computer Science", "5"],
            ["E003", "Ramaiah Institute", "CS-Computer Science", "2"],
            ["E004", "RV College", "CS-Computer Science", "1"],
        ]
        # Ensure all colleges exist in DB
        for c_code, c_name in [("E002", "BMS"), ("E003", "Ramaiah"), ("E004", "RV")]:
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

        # First run
        stats1 = {}
        report1 = pipeline._ingest_seat_and_fee_records(parse_res, sv, uuid.uuid4(), stats1)
        assert report1["status"] == "PUBLISHED"
        assert report1["published_seats"] == 4

        # Count seats
        initial_count = db.execute(
            select(func.count(SeatRecord.id)).where(SeatRecord.source_version_id == sv.id)
        ).scalar_one()
        assert initial_count == 4

        # Second run (re-ingestion of same source_version)
        stats2 = {}
        report2 = pipeline._ingest_seat_and_fee_records(parse_res, sv, uuid.uuid4(), stats2)
        assert report2["status"] == "PUBLISHED"
        assert report2["published_seats"] == 0  # 0 duplicates created!

        final_count = db.execute(
            select(func.count(SeatRecord.id)).where(SeatRecord.source_version_id == sv.id)
        ).scalar_one()
        assert final_count == 4  # Count completely unchanged
    finally:
        from backend.app.models.validation import ValidationError
        db.query(SeatRecord).filter(SeatRecord.source_version_id == sv.id).delete()
        db.query(IngestionReviewItem).filter(IngestionReviewItem.source_version_id == sv.id).delete()
        db.query(ValidationError).filter(ValidationError.source_version_id == sv.id).delete()
        db.delete(sv)
        db.commit()
