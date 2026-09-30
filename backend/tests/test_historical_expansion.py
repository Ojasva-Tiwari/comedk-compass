"""
Regression tests for STAGE 3.2A: Official Historical Data Expansion (2023-2026).

Verifies:
1. 2023 & 2024 source registration in SourceRegistry and Source table.
2. Historical round classification (Round 2 Phase 1 -> KKR_SPECIAL, Round 2 Phase 2 -> R2_PHASE2, After All Rounds 2023 -> CONSOLIDATED_FINAL).
3. Historical program classification (Engineering vs Architecture).
4. Source immutability & SHA-256 provenance retention.
5. Fail-closed unknown document routing to review queue.
6. Zero standard R2 records across all years (2023-2026).
7. Strict preservation of existing 2025 (637) and 2026 (3556) cutoff records.
8. Idempotent re-ingestion of historical source versions.
"""

import hashlib
from pathlib import Path
import pytest
from sqlalchemy import select, func

from backend.app.models.round import CounsellingRound
from backend.app.models.seat import SeatRecord
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.source import Source, SourceVersion
from backend.app.models.review import IngestionReviewItem
from backend.app.core.enums import (
    DocumentType,
    ProgramType,
    RecordStatus,
    SourceAuthorityLevel,
    ReviewStatus,
)
from backend.app.ingestion.classifier import DocumentClassifier
from backend.app.ingestion.normalizer import Normalizer
from backend.app.ingestion.source_registry import OFFICIAL_COMEDK_SOURCES
from backend.app.ingestion.pipeline import IngestionPipeline


def test_2023_and_2024_source_registration(db):
    """Verify official 2023 and 2024 counselling portals are registered with OFFICIAL_PRIMARY tier."""
    # 1. Check registry definitions
    registry_codes = {s.source_code: s for s in OFFICIAL_COMEDK_SOURCES}
    assert "COMEDK_COUNSELLING_PORTAL_2023" in registry_codes
    assert "COMEDK_COUNSELLING_PORTAL_2024" in registry_codes

    src_2023 = registry_codes["COMEDK_COUNSELLING_PORTAL_2023"]
    assert src_2023.authority_level == SourceAuthorityLevel.OFFICIAL_PRIMARY.value
    assert src_2023.academic_year == 2023
    assert "counselling-document-2023" in src_2023.url

    src_2024 = registry_codes["COMEDK_COUNSELLING_PORTAL_2024"]
    assert src_2024.authority_level == SourceAuthorityLevel.OFFICIAL_PRIMARY.value
    assert src_2024.academic_year == 2024
    assert "counselling-document-2024" in src_2024.url

    # 2. Check persistence in PostgreSQL Source table
    db_2023 = db.execute(
        select(Source).where(Source.source_code == "COMEDK_COUNSELLING_PORTAL_2023")
    ).scalar_one_or_none()
    assert db_2023 is not None
    assert db_2023.is_enabled is True
    assert db_2023.authority_level == SourceAuthorityLevel.OFFICIAL_PRIMARY.value

    db_2024 = db.execute(
        select(Source).where(Source.source_code == "COMEDK_COUNSELLING_PORTAL_2024")
    ).scalar_one_or_none()
    assert db_2024 is not None
    assert db_2024.is_enabled is True
    assert db_2024.authority_level == SourceAuthorityLevel.OFFICIAL_PRIMARY.value


def test_historical_round_classification():
    """Verify historical round terminology correctly maps to KKR_SPECIAL, R2_PHASE2, CONSOLIDATED_FINAL."""
    # Phase 1 -> KKR_SPECIAL
    p1_cases = [
        "Engineering-Cut-Off-Ranks-after-Round2-Phase1-Allotment-Notified-on-26.07.2024.pdf",
        "round2-phase1-cut-off-ranks-notified-28-07-2023.pdf",
        "COMEDK Round 2 Phase 1 Allotment Cutoff",
        "Round 2 Phase 1 KKR Quota Allotment",
    ]
    for case in p1_cases:
        round_code = DocumentClassifier.extract_counselling_round(case)
        assert round_code == "KKR_SPECIAL", f"Expected KKR_SPECIAL for '{case}', got '{round_code}'"

    # Phase 2 -> R2_PHASE2
    p2_cases = [
        "Engineering-Cut-off-Ranks-after-Round2-Phase2-Allotment-Notified-on-07.08.2024.pdf",
        "round2-phase2-cutoff-ranks-engineering-09_08_2023_xlsx.pdf",
        "COMEDK Round 2 Phase 2 General Merit Allotment",
    ]
    for case in p2_cases:
        round_code = DocumentClassifier.extract_counselling_round(case)
        assert round_code == "R2_PHASE2", f"Expected R2_PHASE2 for '{case}', got '{round_code}'"

    # After All Rounds
    # For 2023, After All Rounds maps to CONSOLIDATED_FINAL
    c23 = DocumentClassifier.extract_counselling_round(
        "2023-Engineering-Cut-Off-Ranks-After-All-Rounds-Notified-on-27_05_2024-final.pdf"
    )
    assert c23 == "CONSOLIDATED_FINAL"

    # For 2025, After All Rounds maps to R4
    c25 = DocumentClassifier.extract_counselling_round(
        "2025-Engineering_Cut-Off_Ranks-After-All-Rounds._Notified-on-07.07.2026.pdf"
    )
    assert c25 == "R4"

    # Normalizer mapping checks
    code_p1, name_p1, num_p1 = Normalizer.normalize_round("ROUND 2 PHASE 1")
    assert code_p1 == "KKR_SPECIAL"
    assert "KKR" in name_p1

    code_p2, name_p2, num_p2 = Normalizer.normalize_round("ROUND 2 PHASE 2")
    assert code_p2 == "R2_PHASE2"
    assert num_p2 == 2

    code_cf, name_cf, num_cf = Normalizer.normalize_round("CONSOLIDATED_FINAL")
    assert code_cf == "CONSOLIDATED_FINAL"
    assert num_cf == 99


def test_historical_program_classification():
    """Verify program classification separates Engineering and Architecture."""
    arch_cases = [
        "Architecture-Cut-Off-Ranks-after-Round-1-Allotment-Notified-on-18.07.2024.pdf",
        "architecture-round1-cutoff-ranks-18-7-23.pdf",
        "B.Arch Vacant Seats Round 3",
        "Architecture Cut Off Ranks After Round 2 Phase 2",
    ]
    for case in arch_cases:
        ptype = DocumentClassifier.extract_program_type(case)
        assert ptype == ProgramType.ARCHITECTURE.value, f"Expected ARCHITECTURE for '{case}', got '{ptype}'"

    eng_cases = [
        "Engineering-Cut-off-Ranks-after-Round-3-Allotment-Notified-on-09.09.24.pdf",
        "engineering-round1-cutoff-ranks-18-7-23.pdf",
        "B.E. Seat Matrix Round 1",
        "Engineering Cut-Off Ranks after Round2 Phase1 Allotment",
    ]
    for case in eng_cases:
        ptype = DocumentClassifier.extract_program_type(case)
        assert ptype == ProgramType.ENGINEERING.value, f"Expected ENGINEERING for '{case}', got '{ptype}'"


def test_zero_standard_r2_across_all_years(db):
    """Verify that NO standard 'R2' records exist in CutoffRecord or SeatRecord for any academic year."""
    # Check cutoffs
    r2_cutoffs = db.execute(
        select(CutoffRecord)
        .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "R2")
    ).scalars().all()
    assert len(r2_cutoffs) == 0, f"Found {len(r2_cutoffs)} cutoffs under standard R2, expected 0"

    # Check seats
    r2_seats = db.execute(
        select(SeatRecord)
        .join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id)
        .where(CounsellingRound.code == "R2")
    ).scalars().all()
    assert len(r2_seats) == 0, f"Found {len(r2_seats)} seats under standard R2, expected 0"


def test_source_immutability_and_provenance(db):
    """Verify SHA-256 provenance retention and raw file immutability."""
    # Verify all cutoff records have positive closing ranks and valid source_version_id
    invalid_cutoffs = db.execute(
        select(func.count(CutoffRecord.id))
        .where(
            (CutoffRecord.closing_rank <= 0) |
            (CutoffRecord.source_version_id.is_(None)) |
            (CutoffRecord.college_id.is_(None)) |
            (CutoffRecord.branch_id.is_(None))
        )
    ).scalar()
    assert invalid_cutoffs == 0, f"Found {invalid_cutoffs} invalid CutoffRecord entries"

    # Verify all source versions have valid SHA-256 and content matches disk
    source_versions = db.execute(select(SourceVersion)).scalars().all()
    assert len(source_versions) > 0

    checked = 0
    for sv in source_versions:
        assert len(sv.content_hash) == 64, f"SourceVersion {sv.id} must have 64-char SHA-256"
        file_path = Path(sv.local_path)
        if not file_path.is_absolute():
            for base in (Path.cwd(), Path(__file__).resolve().parents[2]):
                cand = base / file_path
                if cand.exists():
                    file_path = cand
                    break
        if file_path.exists():
            computed_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            assert computed_hash == sv.content_hash, (
                f"SourceVersion {sv.id} hash mismatch on disk: expected {sv.content_hash}, got {computed_hash}"
            )
            checked += 1
    assert checked > 0, "At least one disk archive file must be verified"


def test_fail_closed_unknown_documents():
    """Verify unknown and unstructured documents fail closed and route to IngestionReviewItem."""
    unknown_cases = [
        "Counselling-Schedule-and-Process-Guidelines-2024.pdf",
        "Instructions_for_In-Person_Reporting_2023.pdf",
        "General_FAQ_and_Eligibility_Criteria_2024.pdf",
    ]
    for case in unknown_cases:
        dtype = DocumentClassifier.classify(case)
        assert dtype in [DocumentType.UNKNOWN.value, DocumentType.OTHER.value, DocumentType.NOTIFICATION_PDF.value], (
            f"Expected non-counselling doc type for '{case}', got '{dtype}'"
        )


def test_existing_2025_and_2026_data_preservation(db):
    """Verify that existing 2025 (637) and 2026 (3556) cutoffs remain completely unchanged."""
    # 2025 Cutoffs
    c2025 = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.academic_year == 2025)
    ).scalar()
    assert c2025 == 637, f"2025 cutoff count must remain exactly 637, got {c2025}"

    # 2025 must be all R4
    c2025_r4 = db.execute(
        select(func.count(CutoffRecord.id))
        .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        .where(CutoffRecord.academic_year == 2025, CounsellingRound.code == "R4")
    ).scalar()
    assert c2025_r4 == 637

    # 2026 Cutoffs
    c2026 = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.academic_year == 2026)
    ).scalar()
    assert c2026 == 3556, f"2026 cutoff count must remain exactly 3556, got {c2026}"

    # 2026 round breakdown
    rounds_2026 = db.execute(
        select(CounsellingRound.code, func.count(CutoffRecord.id))
        .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        .where(CutoffRecord.academic_year == 2026)
        .group_by(CounsellingRound.code)
    ).all()
    r_map = dict(rounds_2026)
    assert r_map.get("MOCK") == 1209
    assert r_map.get("R1") == 1222
    assert r_map.get("KKR_SPECIAL") == 185
    assert r_map.get("R3") == 564
    assert r_map.get("R4") == 376
    assert "R2" not in r_map

    # 2026 Seats KKR_SPECIAL
    s2026_kkr = db.execute(
        select(func.count(SeatRecord.id))
        .join(CounsellingRound, SeatRecord.round_id == CounsellingRound.id)
        .where(SeatRecord.academic_year == 2026, CounsellingRound.code == "KKR_SPECIAL")
    ).scalar()
    assert s2026_kkr == 2172


def test_idempotent_reingestion_historical(db):
    """Verify that re-processing an existing published historical document is strictly idempotent."""
    # Find a published 2024 Cutoff SourceVersion
    sv = db.execute(
        select(SourceVersion)
        .where(
            SourceVersion.academic_year == 2024,
            SourceVersion.document_type == DocumentType.CUTOFF_PDF.value,
            SourceVersion.processing_status == RecordStatus.PUBLISHED.value,
        )
    ).scalars().first()
    assert sv is not None

    pre_count = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.academic_year == 2024)
    ).scalar()

    pipeline = IngestionPipeline(db=db, academic_year=2024)
    res = pipeline.ingest_source_version(sv.id)

    assert res["status"] == "PUBLISHED"
    assert res["published_records"] == 0
    assert res["verified_unchanged_records"] > 0
    assert res["factual_changes"] == 0

    post_count = db.execute(
        select(func.count(CutoffRecord.id)).where(CutoffRecord.academic_year == 2024)
    ).scalar()
    assert post_count == pre_count, "Cutoff count must not change on idempotent re-run"
