import hashlib
import uuid
import pytest
from pathlib import Path
from sqlalchemy import select, func

from backend.app.core.enums import (
    RecordStatus,
    DocumentType,
    ProgramType,
    SourceAuthorityLevel,
    FailureReason,
    ReviewStatus,
    ValidationSeverity,
)
from backend.app.models import (
    Source,
    SourceVersion,
    College,
    Branch,
    Category,
    CounsellingRound,
    CutoffRecord,
    IngestionReviewItem,
    ValidationError,
)
from backend.app.ingestion.downloader import (
    DocumentDownloader,
    DownloaderError,
    CorruptDocumentError,
)
from backend.app.ingestion.classifier import DocumentClassifier
from backend.app.ingestion.parsers.registry import ParserRegistry, NoParserAvailableError
from backend.app.ingestion.parsers.college_parser import CollegeParser
from backend.app.ingestion.parsers.cutoff_pdf_parser import CutoffPDFParser
from backend.app.ingestion.parsers.seat_and_fee_parser import SeatAndFeeParser
from backend.app.ingestion.source_registry import SourceRegistryService, OFFICIAL_COMEDK_SOURCES
from backend.app.ingestion.health import SourceHealthService
from backend.app.ingestion.review_queue import ReviewQueueService
from backend.app.ingestion.validator import DataValidator
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.ingestion.parsers.base import ParseResult

# 1. Content Hashing & SHA-256 Tests
def test_sha256_computation_and_hashing():
    content1 = b"%PDF-1.4 official comedk test document data"
    content2 = b"%PDF-1.4 official comedk test document data with changes"

    hash1 = DocumentDownloader.compute_sha256(content1)
    hash2 = DocumentDownloader.compute_sha256(content2)

    assert hash1 == hashlib.sha256(content1).hexdigest()
    assert hash2 == hashlib.sha256(content2).hexdigest()
    assert hash1 != hash2, "Distinct document contents must produce distinct SHA-256 digests"

# 2. URL Validation & Filename Sanitization
def test_url_validation_and_filename_sanitization():
    assert DocumentDownloader.validate_url("https://www.comedk.org/cutoff.pdf") is True
    assert DocumentDownloader.validate_url("http://comedk.org/data") is True
    assert DocumentDownloader.validate_url("ftp://comedk.org/data") is False
    assert DocumentDownloader.validate_url("not_a_url") is False
    assert DocumentDownloader.validate_url("") is False

    # Filename sanitization against traversal and illegal characters
    clean = DocumentDownloader.sanitize_filename("../../etc/passwd/test?<>*.pdf")
    assert ".." not in clean
    assert "/" not in clean
    assert "\\" not in clean
    assert clean.endswith(".pdf")

# 3. Raw Document Archive & Immutability Tests
def test_raw_archive_paths_and_immutability(tmp_path):
    downloader = DocumentDownloader(raw_base_dir=tmp_path)

    # Deterministic folder test
    cutoff_dir = downloader.get_destination_folder(2026, "CUTOFF_PDF")
    assert cutoff_dir == tmp_path / "2026" / "cutoff"
    assert cutoff_dir.exists()

    # Initial archive
    content_v1 = b"%PDF-1.4 Version 1 Content"
    hash_v1, path_v1, size_v1 = downloader.archive_content(
        content=content_v1,
        academic_year=2026,
        document_type="CUTOFF_PDF",
        filename="Round1_Cutoff.pdf"
    )
    assert path_v1.exists()
    assert path_v1.read_bytes() == content_v1
    assert hash_v1 == DocumentDownloader.compute_sha256(content_v1)

    # Identical content re-archive produces same file path (idempotent)
    hash_v1_re, path_v1_re, size_v1_re = downloader.archive_content(
        content=content_v1,
        academic_year=2026,
        document_type="CUTOFF_PDF",
        filename="Round1_Cutoff.pdf"
    )
    assert path_v1 == path_v1_re
    assert hash_v1 == hash_v1_re

    # Changed content under same filename preserves old and creates new versioned file
    content_v2 = b"%PDF-1.4 Version 2 Corrigendum Content"
    hash_v2, path_v2, size_v2 = downloader.archive_content(
        content=content_v2,
        academic_year=2026,
        document_type="CUTOFF_PDF",
        filename="Round1_Cutoff.pdf"
    )
    assert path_v1.exists(), "Original raw archive file must remain intact and immutable!"
    assert path_v1.read_bytes() == content_v1
    assert path_v2.exists(), "New version must be written to its own versioned path!"
    assert path_v2.read_bytes() == content_v2
    assert path_v1 != path_v2
    assert hash_v2[:8] in path_v2.name

# 4. Content Integrity & Disguised HTML Rejection
def test_invalid_content_and_magic_byte_detection():
    # Valid PDF magic header
    valid_pdf = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj"
    DocumentDownloader.validate_content_integrity(valid_pdf, "application/pdf", "https://comedk.org/cutoff.pdf")

    # Empty content rejection
    with pytest.raises(CorruptDocumentError, match="empty"):
        DocumentDownloader.validate_content_integrity(b"", "application/pdf", "https://comedk.org/cutoff.pdf")

    # Oversized content rejection
    huge_content = b"x" * (DocumentDownloader.MAX_SIZE_BYTES + 10)
    with pytest.raises(CorruptDocumentError, match="exceeds maximum size limit"):
        DocumentDownloader.validate_content_integrity(huge_content, "application/pdf", "https://comedk.org/cutoff.pdf")

    # Disguised HTML 404/Error page returned with .pdf URL
    html_error = b"<!DOCTYPE html><html><head><title>404 Not Found</title></head><body>Error</body></html>"
    with pytest.raises(CorruptDocumentError, match="returned HTML content instead of a valid PDF"):
        DocumentDownloader.validate_content_integrity(html_error, "application/pdf", "https://comedk.org/cutoff.pdf")

# 5. Document Type Classification & Round Detection
def test_document_classification_and_counselling_rounds():
    # Cutoffs
    assert DocumentClassifier.classify("Engineering Cut-Off Ranks after Round 1") == DocumentType.CUTOFF_PDF.value
    assert DocumentClassifier.classify("https://comedk.org/uploads/R3_cutoff.pdf") == DocumentType.CUTOFF_PDF.value

    # Vacant Seats vs Seat Matrix
    assert DocumentClassifier.classify("Engineering Vacant Seats after Round 2") == DocumentType.VACANT_SEATS_PDF.value
    assert DocumentClassifier.classify("Seat Matrix and Availability for Engineering") == DocumentType.SEAT_MATRIX_PDF.value

    # Fees & Notifications
    assert DocumentClassifier.classify("Fee Structure and Tuition Details 2026") == DocumentType.FEE_STRUCTURE_PDF.value
    assert DocumentClassifier.classify("COMEDK Counselling Process Guideline and Instructions") == DocumentType.NOTIFICATION_PDF.value

    # HTML Directories
    assert DocumentClassifier.classify("https://www.comedk.org/member-institutions") == DocumentType.MEMBER_INSTITUTIONS_HTML.value
    assert DocumentClassifier.classify("https://www.comedk.org/be-colleges") == DocumentType.BE_COLLEGES_HTML.value

    # Unknown
    assert DocumentClassifier.classify("https://www.comedk.org/random-unclassified-page") == DocumentType.UNKNOWN.value

    # Round extraction
    assert DocumentClassifier.extract_counselling_round("Engineering Cut-Off Ranks after Round 1 Allotment") == "R1"
    assert DocumentClassifier.extract_counselling_round("Mock Round Cutoff Ranks") == "MOCK"
    assert DocumentClassifier.extract_counselling_round("Cutoff after R3 Allotment") == "R3"
    assert DocumentClassifier.extract_counselling_round("Vacant seats before Round 4") == "R4"
    assert DocumentClassifier.extract_counselling_round("Member Institutions Directory") is None

# 6. Parser Registry Routing & Versioning
def test_parser_registry_selection_and_unknown_type():
    registry = ParserRegistry()

    # Known document types
    cutoff_parser = registry.get_parser(DocumentType.CUTOFF_PDF.value)
    assert isinstance(cutoff_parser, CutoffPDFParser)

    college_parser = registry.get_parser(DocumentType.MEMBER_INSTITUTIONS_HTML.value)
    assert isinstance(college_parser, CollegeParser)

    seat_parser = registry.get_parser(DocumentType.SEAT_MATRIX_PDF.value)
    assert isinstance(seat_parser, SeatAndFeeParser)

    vacant_parser = registry.get_parser(DocumentType.VACANT_SEATS_PDF.value)
    assert isinstance(vacant_parser, SeatAndFeeParser)

    # Info & supported types
    info = registry.get_parser_info(DocumentType.CUTOFF_PDF.value)
    assert "parser_name" in info
    assert "parser_version" in info

    # Unknown type raises NoParserAvailableError
    with pytest.raises(NoParserAvailableError):
        registry.get_parser(DocumentType.UNKNOWN.value)

    with pytest.raises(NoParserAvailableError):
        registry.get_parser("NON_EXISTENT_DOC_TYPE")

# 7. Source Registry Sync & Freshness Telemetry
def test_source_registry_sync_and_freshness(db):
    service = SourceRegistryService(db)
    synced = service.sync_registered_sources()
    assert len(synced) >= 3

    # Verify official source configuration fields
    member_src = db.execute(
        select(Source).where(Source.source_code == "COMEDK_MEMBER_INSTITUTIONS")
    ).scalar_one()
    assert member_src.authority_level == SourceAuthorityLevel.OFFICIAL_PRIMARY.value
    assert member_src.is_enabled is True
    assert member_src.check_frequency_hours == 24

    # Record check and success
    service.record_check(member_src.id)
    db.refresh(member_src)
    assert member_src.last_checked_at is not None

    test_hash = "abc123def456"
    service.record_success(member_src.id, content_hash=test_hash)
    db.refresh(member_src)
    assert member_src.last_success_at is not None
    assert member_src.last_seen_hash == test_hash

    # Source Health Service report
    health_svc = SourceHealthService(db)
    report = health_svc.get_source_freshness_report()
    assert report["sources_count"] >= 3
    assert "sources" in report
    matched = next((s for s in report["sources"] if s["source_code"] == "COMEDK_MEMBER_INSTITUTIONS"), None)
    assert matched is not None
    assert matched["last_seen_hash"] == test_hash

# 8. Review Queue Persistence & Status Transitions
def test_review_queue_lifecycle(db):
    queue = ReviewQueueService(db)
    src = db.execute(select(Source).limit(1)).scalar_one()

    # Add a review item
    item = queue.add_review_item(
        source_id=src.id,
        document_type=DocumentType.CUTOFF_PDF.value,
        document_url="https://comedk.org/corrupt_cutoff.pdf",
        failure_reason=FailureReason.CORRUPT_DOCUMENT.value,
        validation_errors=[{"error": "Invalid magic bytes"}],
        review_notes="HTML error page disguised as PDF"
    )
    assert item.id is not None
    assert item.status == ReviewStatus.PENDING_REVIEW.value
    assert item.failure_reason == FailureReason.CORRUPT_DOCUMENT.value

    # Query pending
    pending = queue.get_pending_items()
    assert any(p.id == item.id for p in pending)

    # Transition status to APPROVED / REJECTED
    updated = queue.update_item_status(
        item_id=item.id,
        new_status=ReviewStatus.REJECTED.value,
        reviewed_by="TEST_OPERATOR",
        notes="Confirmed corrupt source file"
    )
    assert updated.status == ReviewStatus.REJECTED.value
    assert updated.reviewed_by == "TEST_OPERATOR"

    # Clean up
    db.delete(item)
    db.commit()

# 9. Batch Completeness Check: Incomplete Parse Fails Closed & Routes to Review Queue
def test_batch_completeness_failure_prevents_publishing_and_queues_review(db):
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()

    # Create a simulated source version for a full cutoff document
    sv = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/partial-cutoff-test.pdf",
        source_title="COMEDK Engineering Full Round 1 Cutoff PDF",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.CUTOFF_PDF.value,
        counselling_round="R1",
        content_hash=f"hash_{uuid.uuid4().hex[:12]}",
        local_path="/tmp/partial_cutoff.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.DOWNLOADED.value
    )
    db.add(sv)
    db.flush()

    # Simulate an incomplete parse of only 20 records (below the 50 minimum threshold)
    colleges = db.execute(select(College).limit(20)).scalars().all()
    branch = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one()

    simulated_records = [{
        "college_code": colleges[i].code,
        "college_name": colleges[i].name,
        "branch_code": branch.code,
        "branch_name": branch.name,
        "category_code": "GM",
        "round_code": "R1",
        "round_name": "Round 1",
        "academic_year": 2026,
        "opening_rank": None,
        "closing_rank": 5000 + i,
        "page_number": 1,
        "row_identifier": f"partial_row_{i}"
    } for i in range(len(colleges))]

    sim_res = ParseResult(
        records=simulated_records,
        discovered_branches={},
        discovered_colleges=[],
        row_count=20,
        status=RecordStatus.PARSED,
        metadata={"pdf_page_count": 15, "extracted_pages_count": 1, "raw_rows_detected": 20}
    )

    stats = {
        "records_parsed": 0, "records_validated": 0, "records_published": 0,
        "records_rejected": 0, "records_needs_review": 0, "validation_errors": 0,
        "anomalies": 0, "documents_needs_review": 0
    }

    report = pipeline._ingest_cutoff_records(
        parse_res=sim_res,
        sv=sv,
        cat_map={},
        round_map={},
        run_id=uuid.uuid4(),
        stats=stats
    )

    # 1. Verify report status is NEEDS_REVIEW
    assert report["status"] == "NEEDS_REVIEW"
    assert report["failure_reason"] == FailureReason.SUSPICIOUS_LOW_COUNT.value
    assert report["published_records"] == 0, "Suspiciously low cutoff records must NOT be published!"

    # 2. Verify source version is flagged for review
    db.refresh(sv)
    assert sv.processing_status == RecordStatus.NEEDS_REVIEW.value

    # 3. Verify item was created in IngestionReviewItem table
    review_item = db.execute(
        select(IngestionReviewItem).where(
            IngestionReviewItem.source_version_id == sv.id
        )
    ).scalar_one_or_none()
    assert review_item is not None
    assert review_item.failure_reason == FailureReason.SUSPICIOUS_LOW_COUNT.value
    assert review_item.status == ReviewStatus.PENDING_REVIEW.value

    # 4. Verify no CutoffRecords were created under this suspicious version
    published_for_sv = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.source_version_id == sv.id)
    ).scalar_one()
    assert published_for_sv == 0

    # Clean up test artifacts
    db.delete(review_item)
    db.delete(sv)
    db.commit()

# 10. Duplicate Natural Keys in Batch Rejected
def test_duplicate_natural_keys_in_batch_rejected():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )
    duplicate_records = [
        {
            "college_code": "E001",
            "branch_code": "CS",
            "category_code": "GM",
            "round_code": "R1",
            "academic_year": 2026,
            "opening_rank": 100,
            "closing_rank": 1200,
            "row_identifier": "row_1"
        },
        {
            "college_code": "E001",
            "branch_code": "CS",
            "category_code": "GM",
            "round_code": "R1",
            "academic_year": 2026,
            "opening_rank": 150,
            "closing_rank": 1250,
            "row_identifier": "row_2"
        }
    ]
    valid_recs, errors, anomalies = validator.validate_cutoff_records(duplicate_records, 2026)
    assert len(valid_recs) == 1, "Only first unique occurrence of logical key must be accepted"
    assert len(errors) == 1
    assert errors[0].error_code == "DUPLICATE_LOGICAL_RECORD"

# 11. Changed Document Content Creates New Version Without Mutating Historical Records
def test_changed_document_creates_new_version_without_overwriting_historical(db):
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()

    # Step A: Ingest Version 1
    sv1 = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/official-cutoff-v1.pdf",
        source_title="COMEDK Cutoff Corrigendum V1",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.CUTOFF_PDF.value,
        counselling_round="R1",
        content_hash="hash_version_1_initial",
        local_path="/tmp/cutoff_v1.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.PUBLISHED.value
    )
    db.add(sv1)
    db.flush()

    college = db.execute(select(College).where(College.code == "E001")).scalar_one()
    branch = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one()
    cat = db.execute(select(Category).where(Category.code == "GM")).scalar_one()

    parse_res_v1 = ParseResult(
        records=[{
            "college_code": college.code,
            "college_name": college.name,
            "branch_code": branch.code,
            "branch_name": branch.name,
            "category_code": cat.code,
            "round_code": "R1",
            "academic_year": 2026,
            "closing_rank": 1500,
            "row_identifier": "v1_row"
        }],
        row_count=1
    )
    stats1 = {}
    pipeline._ingest_cutoff_records(parse_res_v1, sv1, {}, {}, uuid.uuid4(), stats1)
    db.commit()

    rec_v1 = db.execute(
        select(CutoffRecord).where(CutoffRecord.source_version_id == sv1.id)
    ).scalar_one()
    assert rec_v1.closing_rank == 1500
    assert rec_v1.status == RecordStatus.PUBLISHED.value
    rec_v1_id = rec_v1.id

    # Step B: Ingest Version 2 with Changed Content Hash
    sv2 = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/official-cutoff-v1.pdf",
        source_title="COMEDK Cutoff Corrigendum V2",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.CUTOFF_PDF.value,
        counselling_round="R1",
        content_hash="hash_version_2_updated",
        local_path="/tmp/cutoff_v2.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.PUBLISHED.value
    )
    db.add(sv2)
    db.flush()

    parse_res_v2 = ParseResult(
        records=[{
            "college_code": college.code,
            "college_name": college.name,
            "branch_code": branch.code,
            "branch_name": branch.name,
            "category_code": cat.code,
            "round_code": "R1",
            "academic_year": 2026,
            "closing_rank": 1600,
            "row_identifier": "v2_row"
        }],
        row_count=1
    )
    stats2 = {}
    pipeline._ingest_cutoff_records(parse_res_v2, sv2, {}, {}, uuid.uuid4(), stats2)
    db.commit()

    # Step C: Verify Historical Immutability
    db.refresh(rec_v1)
    assert rec_v1.id == rec_v1_id
    assert rec_v1.closing_rank == 1500, "Historical closing rank MUST NOT be mutated!"
    assert rec_v1.status == RecordStatus.SUPERSEDED.value, "Old version record must transition to SUPERSEDED"

    rec_v2 = db.execute(
        select(CutoffRecord).where(CutoffRecord.source_version_id == sv2.id)
    ).scalar_one()
    assert rec_v2.closing_rank == 1600
    assert rec_v2.status == RecordStatus.PUBLISHED.value

    # Clean up test artifacts
    db.delete(rec_v2)
    db.delete(rec_v1)
    db.delete(sv2)
    db.delete(sv1)
    db.commit()

# 12. Idempotent Second Run Produces Zero Changes
def test_idempotent_ingestion_produces_zero_duplicates_and_zero_factual_changes(db):
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()

    sv = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/idempotent-test.pdf",
        source_title="COMEDK Cutoff Idempotent Test Corrigendum",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.CUTOFF_PDF.value,
        counselling_round="R1",
        content_hash="hash_idempotent_test_123",
        local_path="/tmp/idempotent_test.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.PUBLISHED.value
    )
    db.add(sv)
    db.flush()

    college = db.execute(select(College).where(College.code == "E001")).scalar_one()
    branch = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one()
    cat = db.execute(select(Category).where(Category.code == "GM")).scalar_one()

    parse_res = ParseResult(
        records=[{
            "college_code": college.code,
            "college_name": college.name,
            "branch_code": branch.code,
            "branch_name": branch.name,
            "category_code": cat.code,
            "round_code": "R1",
            "academic_year": 2026,
            "closing_rank": 1500,
            "row_identifier": "idempotent_row_1"
        }],
        row_count=1
    )

    # First Run: Record is inserted & published
    stats_run1 = {}
    rep1 = pipeline._ingest_cutoff_records(parse_res, sv, {}, {}, uuid.uuid4(), stats_run1)
    db.commit()
    assert rep1["published_records"] == 1
    assert rep1["verified_unchanged_records"] == 0

    # Second Run: Exact same source version & document -> 0 published, 1 verified unchanged
    stats_run2 = {}
    rep2 = pipeline._ingest_cutoff_records(parse_res, sv, {}, {}, uuid.uuid4(), stats_run2)
    db.commit()
    assert rep2["published_records"] == 0, "Idempotent re-run must NOT publish duplicate records!"
    assert rep2["verified_unchanged_records"] == 1, "Existing record must be verified identical in-place"
    assert rep2["factual_changes"] == 0

    # Clean up test artifacts
    recs = db.execute(select(CutoffRecord).where(CutoffRecord.source_version_id == sv.id)).scalars().all()
    for r in recs:
        db.delete(r)
    db.delete(sv)
    db.commit()


# 13. Valid Engineering Cutoff Below Threshold is Rejected
def test_valid_engineering_cutoff_below_threshold_rejected():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )
    # Engineering cutoff with 30 records (< 50 threshold)
    errors = validator.validate_batch_completeness(
        doc_type=DocumentType.CUTOFF_PDF.value,
        extracted_count=30,
        program_type=ProgramType.ENGINEERING.value
    )
    assert len(errors) == 1
    assert errors[0].error_code == "SUSPICIOUS_LOW_COUNT"
    assert "ENGINEERING" in errors[0].message.upper()
    assert errors[0].severity == ValidationSeverity.CRITICAL.value


# 14. Valid Architecture Cutoff with 4 to 28 Records is Accepted
def test_valid_architecture_cutoff_with_4_to_28_records_accepted(db):
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"AT"},
        known_categories={"GM"}
    )
    # Direct validator checks: 4, 15, and 28 records are all accepted for architecture
    for count in [4, 15, 28]:
        errors = validator.validate_batch_completeness(
            doc_type=DocumentType.CUTOFF_PDF.value,
            extracted_count=count,
            program_type=ProgramType.ARCHITECTURE.value
        )
        assert len(errors) == 0, f"Architecture batch with {count} records must be accepted"

    # Full pipeline check for Architecture document
    pipeline = IngestionPipeline(db=db, academic_year=2026)
    src = db.execute(select(Source).limit(1)).scalar_one()

    sv = SourceVersion(
        source_id=src.id,
        source_url="https://www.comedk.org/architecture-cutoff-test.pdf",
        source_title="COMEDK Architecture Cut-off Ranks Round 1",
        publisher="COMEDK",
        academic_year=2026,
        document_type=DocumentType.CUTOFF_PDF.value,
        counselling_round="R1",
        content_hash="arch_test_hash_4_records",
        local_path="/tmp/arch_test.pdf",
        parser_version="v1.0.0",
        processing_status=RecordStatus.DOWNLOADED.value
    )
    db.add(sv)
    db.flush()

    colleges = db.execute(select(College).limit(6)).scalars().all()
    arch_branch = db.execute(select(Branch).where(Branch.code == "AT")).scalar_one()

    arch_records = [{
        "college_code": colleges[i].code,
        "college_name": colleges[i].name,
        "branch_code": arch_branch.code,
        "branch_name": arch_branch.name,
        "category_code": "GM",
        "round_code": "R1",
        "round_name": "Round 1",
        "academic_year": 2026,
        "opening_rank": None,
        "closing_rank": 300 + i,
        "row_identifier": f"arch_row_{i}"
    } for i in range(6)]

    parse_res = ParseResult(
        records=arch_records,
        row_count=6,
        status=RecordStatus.PARSED
    )

    stats = {}
    report = pipeline._ingest_cutoff_records(
        parse_res=parse_res,
        sv=sv,
        cat_map={},
        round_map={},
        run_id=uuid.uuid4(),
        stats=stats
    )

    assert report["status"] == "PUBLISHED"
    assert report["published_records"] == 6
    assert sv.processing_status == RecordStatus.PUBLISHED.value

    # Verify no review item was created
    review_item = db.execute(
        select(IngestionReviewItem).where(IngestionReviewItem.source_version_id == sv.id)
    ).scalar_one_or_none()
    assert review_item is None, "Valid architecture cutoff must NOT be routed to review queue"

    # Clean up test artifacts
    recs = db.execute(select(CutoffRecord).where(CutoffRecord.source_version_id == sv.id)).scalars().all()
    for r in recs:
        db.delete(r)
    db.delete(sv)
    db.commit()


# 15. Truly Incomplete Architecture Data is Rejected
def test_truly_incomplete_architecture_data_rejected():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"AT"},
        known_categories={"GM"}
    )
    # 0 records (empty)
    errors_0 = validator.validate_batch_completeness(
        doc_type=DocumentType.CUTOFF_PDF.value,
        extracted_count=0,
        program_type=ProgramType.ARCHITECTURE.value
    )
    assert len(errors_0) == 1
    assert errors_0[0].error_code == "SUSPICIOUS_LOW_COUNT"
    assert errors_0[0].severity == ValidationSeverity.CRITICAL.value

    # 1 record (< 4)
    errors_1 = validator.validate_batch_completeness(
        doc_type=DocumentType.CUTOFF_PDF.value,
        extracted_count=1,
        program_type=ProgramType.ARCHITECTURE.value
    )
    assert len(errors_1) == 1
    assert errors_1[0].error_code == "SUSPICIOUS_LOW_COUNT"

    # 3 records (< 4)
    errors_3 = validator.validate_batch_completeness(
        doc_type=DocumentType.CUTOFF_PDF.value,
        extracted_count=3,
        program_type=ProgramType.ARCHITECTURE.value
    )
    assert len(errors_3) == 1
    assert errors_3[0].error_code == "SUSPICIOUS_LOW_COUNT"


# 16. Unknown Document Type Fails Closed to Review
def test_unknown_document_type_fails_closed_to_review():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )
    errors = validator.validate_batch_completeness(
        doc_type=DocumentType.UNKNOWN.value,
        extracted_count=100
    )
    assert len(errors) == 1
    assert errors[0].error_code == "UNKNOWN_DOCUMENT_TYPE"
    assert errors[0].severity == ValidationSeverity.CRITICAL.value

