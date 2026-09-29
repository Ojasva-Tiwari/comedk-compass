from backend.app.ingestion.validator import DataValidator
from backend.app.core.enums import RecordStatus

def test_validator_accepts_valid_cutoff():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )
    records = [{
        "college_code": "E001",
        "branch_code": "CS",
        "category_code": "GM",
        "round_code": "R1",
        "closing_rank": 1420,
        "opening_rank": 500,
        "academic_year": 2026
    }]
    valid, errors, anomalies = validator.validate_cutoff_records(records, 2026)
    assert len(valid) == 1
    assert len(errors) == 0
    assert valid[0]["status"] == RecordStatus.PUBLISHED.value

def test_validator_rejects_unknown_college():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )
    records = [{
        "college_code": "E999",
        "branch_code": "CS",
        "category_code": "GM",
        "round_code": "R1",
        "closing_rank": 1420,
        "academic_year": 2026
    }]
    valid, errors, anomalies = validator.validate_cutoff_records(records, 2026)
    assert len(valid) == 0
    assert len(errors) == 1
    assert errors[0].error_code == "UNKNOWN_COLLEGE_CODE"

def test_validator_rejects_opening_greater_than_closing():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )
    records = [{
        "college_code": "E001",
        "branch_code": "CS",
        "category_code": "GM",
        "round_code": "R1",
        "opening_rank": 5000,
        "closing_rank": 1420,
        "academic_year": 2026
    }]
    valid, errors, anomalies = validator.validate_cutoff_records(records, 2026)
    assert len(valid) == 0
    assert len(errors) == 1
    assert errors[0].error_code == "OPENING_GREATER_THAN_CLOSING"

def test_validator_detects_duplicates_in_batch():
    validator = DataValidator(
        known_college_codes={"E001"},
        known_branch_codes={"CS"},
        known_categories={"GM"}
    )
    records = [
        {
            "college_code": "E001",
            "branch_code": "CS",
            "category_code": "GM",
            "round_code": "R1",
            "closing_rank": 1420,
            "academic_year": 2026
        },
        {
            "college_code": "E001",
            "branch_code": "CS",
            "category_code": "GM",
            "round_code": "R1",
            "closing_rank": 1420,
            "academic_year": 2026
        }
    ]
    valid, errors, anomalies = validator.validate_cutoff_records(records, 2026)
    assert len(valid) == 1
    assert len(errors) == 1
    assert errors[0].error_code == "DUPLICATE_LOGICAL_RECORD"
