import pytest
from backend.app.core.enums import InstitutionType, RecordStatus
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.category import Category
from backend.app.models.round import CounsellingRound
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.source import Source, SourceVersion
from backend.app.database import SessionLocal
from sqlalchemy import select, func

def test_institution_type_classification():
    """Verify that institution_type correctly separates engineering, architecture, medical, and dental."""
    db = SessionLocal()
    try:
        colleges = db.execute(select(College)).scalars().all()
        assert len(colleges) > 0, "Colleges table should not be empty"

        types = {c.institution_type for c in colleges}
        assert InstitutionType.ENGINEERING.value in types
        assert InstitutionType.ARCHITECTURE.value in types
        assert InstitutionType.MEDICAL.value in types
        assert InstitutionType.DENTAL.value in types

        # Check known architecture colleges with E-prefix
        arch_colleges = db.execute(
            select(College).where(College.institution_type == InstitutionType.ARCHITECTURE.value)
        ).scalars().all()
        arch_codes = {c.code for c in arch_colleges}
        # E002, E008, E029, E054, E163, E168, E169, etc. must be ARCHITECTURE
        assert "E002" in arch_codes
        assert "E008" in arch_codes
        assert "E029" in arch_codes

        # Medical colleges (M-prefix)
        med_colleges = db.execute(
            select(College).where(College.institution_type == InstitutionType.MEDICAL.value)
        ).scalars().all()
        for mc in med_colleges:
            assert mc.code.startswith("M")

        # Dental colleges (D-prefix)
        dental_colleges = db.execute(
            select(College).where(College.institution_type == InstitutionType.DENTAL.value)
        ).scalars().all()
        for dc in dental_colleges:
            assert dc.code.startswith("D")

        # Engineering colleges (E-prefix that offer B.E.)
        eng_colleges = db.execute(
            select(College).where(College.institution_type == InstitutionType.ENGINEERING.value)
        ).scalars().all()
        eng_codes = {c.code for c in eng_colleges}
        assert "E001" in eng_codes # RVCE
        assert "E005" in eng_codes # BMSCE
        assert "E002" not in eng_codes # Architecture
    finally:
        db.close()

def test_engineering_api_filtering_default(client):
    """Verify that /api/v1/colleges defaults to ENGINEERING only."""
    response = client.get("/api/v1/colleges")
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert len(items) > 0
    for item in items:
        assert item["institution_type"] == "ENGINEERING"

def test_architecture_exclusion_from_engineering_searches(client):
    """Verify that architecture colleges are excluded from default college list and search."""
    # E002 is Acharya's NRV School of Architecture
    response = client.get("/api/v1/colleges?search=Architecture")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        # Only engineering institutions offering architecture or containing word in eng context
        assert item["institution_type"] == "ENGINEERING"

    # Explicitly requesting ARCHITECTURE returns them
    arch_response = client.get("/api/v1/colleges?institution_type=ARCHITECTURE")
    assert arch_response.status_code == 200
    arch_data = arch_response.json()
    assert arch_data["total"] > 0
    for item in arch_data["items"]:
        assert item["institution_type"] == "ARCHITECTURE"

def test_medical_and_dental_exclusion_from_engineering_apis(client):
    """Verify that medical and dental colleges are excluded from default colleges and cutoffs endpoints."""
    # Colleges default (page 1)
    response = client.get("/api/v1/colleges?limit=100")
    assert response.status_code == 200
    items = response.json()["items"]
    for item in items:
        assert not item["code"].startswith("M"), f"Medical college {item['code']} found in engineering endpoint"
        assert not item["code"].startswith("D"), f"Dental college {item['code']} found in engineering endpoint"

    # Cutoffs default
    cut_res = client.get("/api/v1/cutoffs?limit=100")
    assert cut_res.status_code == 200
    for item in cut_res.json()["items"]:
        col_type = item.get("college_type") or item.get("institution_type")
        if col_type:
            assert col_type == "ENGINEERING"

def test_data_health_institution_counts(client):
    """Verify that /api/v1/data-health reports institution_type_counts breakdown."""
    response = client.get("/api/v1/data-health")
    assert response.status_code == 200
    data = response.json()
    assert "institution_type_counts" in data
    counts = data["institution_type_counts"]
    assert counts.get("ENGINEERING", 0) > 0
    assert counts.get("ARCHITECTURE", 0) > 0
    assert counts.get("MEDICAL", 0) > 0
    assert counts.get("DENTAL", 0) > 0
    assert data["engineering_college_count"] == counts["ENGINEERING"]

def test_multi_round_and_category_cutoff_uniqueness():
    """Verify that multiple rounds and categories (GM/KKR) for the same college+branch exist without collision."""
    db = SessionLocal()
    try:
        # Check RV College of Engineering (E001) cutoffs
        rvce = db.execute(select(College).where(College.code == "E001")).scalar_one_or_none()
        if rvce:
            cutoffs = db.execute(
                select(CutoffRecord).where(CutoffRecord.college_id == rvce.id)
            ).scalars().all()

            # Verify no two cutoffs share (college_id, branch_id, category_id, round_id, academic_year)
            seen = set()
            for c in cutoffs:
                key = (c.college_id, c.branch_id, c.category_id, c.round_id, c.academic_year)
                assert key not in seen, f"Duplicate cutoff record found for key: {key}"
                seen.add(key)
    finally:
        db.close()

def test_category_quota_uniqueness():
    """Verify that GM and KKR quotas for the same college+branch+round are stored as distinct records."""
    db = SessionLocal()
    try:
        # RVCE CSE in Round 1
        rvce = db.execute(select(College).where(College.code == "E001")).scalar_one_or_none()
        cse = db.execute(select(Branch).where(Branch.code == "CS")).scalar_one_or_none()
        r1 = db.execute(select(CounsellingRound).where(CounsellingRound.code == "R1", CounsellingRound.academic_year == 2026)).scalar_one_or_none()
        gm = db.execute(select(Category).where(Category.code == "GM")).scalar_one_or_none()
        kkr = db.execute(select(Category).where(Category.code == "KKR")).scalar_one_or_none()

        if rvce and cse and r1 and gm and kkr:
            gm_cutoff = db.execute(
                select(CutoffRecord).where(
                    CutoffRecord.college_id == rvce.id,
                    CutoffRecord.branch_id == cse.id,
                    CutoffRecord.round_id == r1.id,
                    CutoffRecord.category_id == gm.id
                )
            ).scalar_one_or_none()

            kkr_cutoff = db.execute(
                select(CutoffRecord).where(
                    CutoffRecord.college_id == rvce.id,
                    CutoffRecord.branch_id == cse.id,
                    CutoffRecord.round_id == r1.id,
                    CutoffRecord.category_id == kkr.id
                )
            ).scalar_one_or_none()

            assert gm_cutoff is not None, "RVCE CSE GM cutoff should exist for Round 1"
            assert kkr_cutoff is not None, "RVCE CSE KKR cutoff should exist for Round 1"
            assert gm_cutoff.id != kkr_cutoff.id, "GM and KKR records must be distinct entities"
            assert gm_cutoff.category_id != kkr_cutoff.category_id
    finally:
        db.close()

def test_source_provenance_retention():
    """Verify that every published cutoff record links to source_version, page_number, and row_identifier."""
    db = SessionLocal()
    try:
        cutoffs = db.execute(
            select(CutoffRecord).where(CutoffRecord.status == RecordStatus.PUBLISHED.value).limit(50)
        ).scalars().all()

        for c in cutoffs:
            assert c.source_version_id is not None, "Cutoff must have a source_version_id"
            assert c.page_number is not None and c.page_number > 0, "Cutoff must preserve page_number"
            assert c.row_identifier is not None and len(c.row_identifier) > 0, "Cutoff must preserve row_identifier"
            assert c.closing_rank > 0, "Closing rank must be positive"
    finally:
        db.close()

def test_ingestion_idempotency_after_full_batch():
    """Verify that across the entire database, 0 duplicate logical records exist."""
    db = SessionLocal()
    try:
        duplicates = db.execute(
            select(
                CutoffRecord.college_id,
                CutoffRecord.branch_id,
                CutoffRecord.category_id,
                CutoffRecord.round_id,
                CutoffRecord.academic_year,
                CutoffRecord.source_version_id,
                func.count('*')
            )
            .group_by(
                CutoffRecord.college_id,
                CutoffRecord.branch_id,
                CutoffRecord.category_id,
                CutoffRecord.round_id,
                CutoffRecord.academic_year,
                CutoffRecord.source_version_id
            )
            .having(func.count('*') > 1)
        ).all()
        assert len(duplicates) == 0, f"Found {len(duplicates)} duplicate cutoff keys in database!"
    finally:
        db.close()

def test_existing_cutoff_record_cannot_be_silently_overwritten_by_later_source_version():
    """
    Verify that an existing cutoff record's factual values cannot be silently overwritten
    by a later source version. Historical factual values must remain 100% recoverable.
    """
    import uuid
    from backend.app.ingestion.parsers.base import ParseResult
    from backend.app.ingestion.pipeline import IngestionPipeline

    db = SessionLocal()
    try:
        # 1. Fetch an existing published cutoff
        existing_record = db.execute(
            select(CutoffRecord)
            .where(CutoffRecord.status == RecordStatus.PUBLISHED.value)
            .limit(1)
        ).scalar_one()

        orig_id = existing_record.id
        orig_closing_rank = existing_record.closing_rank
        orig_source_version_id = existing_record.source_version_id
        orig_col_id = existing_record.college_id
        orig_br_id = existing_record.branch_id
        orig_cat_id = existing_record.category_id
        orig_rnd_id = existing_record.round_id
        orig_year = existing_record.academic_year

        college = db.execute(select(College).where(College.id == orig_col_id)).scalar_one()
        branch = db.execute(select(Branch).where(Branch.id == orig_br_id)).scalar_one()
        cat = db.execute(select(Category).where(Category.id == orig_cat_id)).scalar_one()
        rnd = db.execute(select(CounsellingRound).where(CounsellingRound.id == orig_rnd_id)).scalar_one()

        # 2. Create a new simulated source version (e.g. an official corrigendum)
        src = db.execute(select(Source).limit(1)).scalar_one()
        new_sv = SourceVersion(
            source_id=src.id,
            source_url="https://www.comedk.org/corrigendum-test.pdf",
            source_title="COMEDK Engineering Corrigendum Test",
            publisher="COMEDK",
            academic_year=orig_year,
            document_type="CUTOFF_PDF",
            counselling_round=rnd.code,
            content_hash=f"test_hash_{uuid.uuid4().hex[:16]}",
            local_path="/tmp/corrigendum_test.pdf",
            parser_version="1.0.0",
            processing_status=RecordStatus.DOWNLOADED.value
        )
        db.add(new_sv)
        db.flush()

        # 3. Simulate parsing a modified closing rank in the new source version
        different_rank = orig_closing_rank + 1000
        simulated_parse_res = ParseResult(
            records=[{
                "college_code": college.code,
                "college_name": college.name,
                "branch_code": branch.code,
                "branch_name": branch.name,
                "category_code": cat.code,
                "round_code": rnd.code,
                "round_name": rnd.name,
                "academic_year": orig_year,
                "opening_rank": None,
                "closing_rank": different_rank,
                "page_number": 99,
                "row_identifier": f"corrigendum_test_{college.code}_{branch.code}_{cat.code}"
            }],
            discovered_branches={},
            discovered_colleges=[],
            row_count=1,
            status=RecordStatus.PARSED,
            metadata={"pdf_page_count": 1, "extracted_pages_count": 1, "raw_rows_detected": 1}
        )

        pipeline = IngestionPipeline(db=db, academic_year=orig_year)
        stats = {
            "records_parsed": 0, "records_validated": 0, "records_published": 0,
            "records_rejected": 0, "records_needs_review": 0, "validation_errors": 0, "anomalies": 0
        }

        # Ingest the new source version
        pipeline._ingest_cutoff_records(
            parse_res=simulated_parse_res,
            sv=new_sv,
            cat_map={},
            round_map={},
            run_id=uuid.uuid4(),
            stats=stats
        )

        # 4. Verify that the ORIGINAL historical record was NOT overwritten!
        db.refresh(existing_record)
        assert existing_record.id == orig_id
        assert existing_record.closing_rank == orig_closing_rank, "Original factual closing rank MUST NOT be mutated!"
        assert existing_record.source_version_id == orig_source_version_id, "Original source_version_id MUST NOT be mutated!"
        assert existing_record.status == RecordStatus.SUPERSEDED.value, "Original record status should be updated to SUPERSEDED"

        # 5. Verify that the new source version created its own separate record
        new_record = db.execute(
            select(CutoffRecord).where(
                CutoffRecord.source_version_id == new_sv.id,
                CutoffRecord.college_id == orig_col_id,
                CutoffRecord.branch_id == orig_br_id,
                CutoffRecord.category_id == orig_cat_id
            )
        ).scalar_one()
        assert new_record.closing_rank == different_rank
        assert new_record.status == RecordStatus.PUBLISHED.value

        # Clean up test artifacts
        db.delete(new_record)
        existing_record.status = RecordStatus.PUBLISHED.value
        db.delete(new_sv)
        db.commit()

    finally:
        db.close()

def test_no_non_be_program_in_engineering_counselling_results(client):
    """
    CRITICAL INVARIANT TEST:
    No non-B.E. program (Architecture, Design, Planning) may appear in an engineering counselling result.
    """
    # 1. Test /api/v1/cutoffs default endpoint
    response = client.get("/api/v1/cutoffs?limit=500")
    assert response.status_code == 200
    cutoffs = response.json()["items"]
    assert len(cutoffs) > 0

    db = SessionLocal()
    non_be_branch_ids = {
        str(b_id) for b_id in db.execute(
            select(Branch.id).where(Branch.program_type != "ENGINEERING")
        ).scalars().all()
    }
    non_be_codes = {
        code for code in db.execute(
            select(Branch.code).where(Branch.program_type != "ENGINEERING")
        ).scalars().all()
    }
    db.close()

    for c in cutoffs:
        assert c["branch_id"] not in non_be_branch_ids, f"Non-B.E. program branch_id {c['branch_id']} found in engineering cutoffs!"

    # 2. Test /api/v1/branches default endpoint
    b_response = client.get("/api/v1/branches?limit=100")
    assert b_response.status_code == 200
    branches = b_response.json()["items"]
    for b in branches:
        assert b["program_type"] == "ENGINEERING", f"Branch {b['code']} has non-engineering type {b['program_type']}"
        assert b["is_canonical"] is True, f"Non-canonical branch {b['code']} returned in default canonical list"
        assert b["code"] not in non_be_codes, f"Non-B.E. code {b['code']} found in engineering branch catalogue!"

    # 3. Test explicit non-engineering queries
    arch_b = client.get("/api/v1/branches?program_type=ARCHITECTURE")
    assert arch_b.status_code == 200
    arch_codes = {b["code"] for b in arch_b.json()["items"]}
    assert "AT" in arch_codes

    design_b = client.get("/api/v1/branches?program_type=DESIGN")
    assert design_b.status_code == 200
    design_codes = {b["code"] for b in design_b.json()["items"]}
    assert "DC" in design_codes or "BI" in design_codes

