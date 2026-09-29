from typing import List, Dict, Any, Tuple, Optional, Set
from uuid import UUID
from backend.app.core.enums import RecordStatus, ValidationSeverity

class ValidationErrorItem:
    def __init__(
        self,
        entity_type: str,
        entity_identifier: Optional[str],
        error_code: str,
        message: str,
        severity: str = ValidationSeverity.ERROR.value,
        context_data: Optional[Dict[str, Any]] = None
    ):
        self.entity_type = entity_type
        self.entity_identifier = entity_identifier
        self.error_code = error_code
        self.message = message
        self.severity = severity
        self.context_data = context_data or {}

class DataValidator:
    """
    Validates ingested records and detects data anomalies before database persistence.
    Follows FAIL CLOSED principle: invalid or unverified records are never published.
    """
    MAX_REASONABLE_RANK = 250000

    def __init__(
        self,
        known_college_codes: Set[str],
        known_branch_codes: Set[str],
        known_categories: Set[str],
    ):
        self.known_college_codes = known_college_codes
        self.known_branch_codes = known_branch_codes
        self.known_categories = known_categories

    def validate_cutoff_records(
        self,
        records: List[Dict[str, Any]],
        academic_year: int
    ) -> Tuple[List[Dict[str, Any]], List[ValidationErrorItem], List[ValidationErrorItem]]:
        """
        Validates a batch of raw cutoff records.
        Returns: (valid_records, validation_errors, anomalies)
        """
        valid_records: List[Dict[str, Any]] = []
        errors: List[ValidationErrorItem] = []
        anomalies: List[ValidationErrorItem] = []
        seen_logical_keys: Set[Tuple] = set()

        for idx, rec in enumerate(records):
            c_code = rec.get("college_code")
            b_code = rec.get("branch_code")
            cat_code = rec.get("category_code")
            r_code = rec.get("round_code")
            c_rank = rec.get("closing_rank")
            o_rank = rec.get("opening_rank")
            row_id = rec.get("row_identifier", f"rec_{idx}")

            # 1. College existence check
            if not c_code or c_code not in self.known_college_codes:
                errors.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="UNKNOWN_COLLEGE_CODE",
                    message=f"College code '{c_code}' does not exist in registry",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            # 2. Branch existence check
            if not b_code or b_code not in self.known_branch_codes:
                errors.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="UNKNOWN_BRANCH_CODE",
                    message=f"Branch code '{b_code}' does not exist in registry",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            # 3. Category validity check
            if not cat_code or cat_code not in self.known_categories:
                anomalies.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="UNEXPECTED_CATEGORY",
                    message=f"Category '{cat_code}' is unexpected for COMEDK quota",
                    severity=ValidationSeverity.WARNING.value,
                    context_data={"category": cat_code}
                ))

            # 4. Rank positivity check
            if c_rank is None or c_rank <= 0:
                errors.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="INVALID_CLOSING_RANK",
                    message=f"Closing rank must be a positive integer, got: {c_rank}",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            # 5. Opening rank relationship
            if o_rank is not None:
                if o_rank <= 0:
                    errors.append(ValidationErrorItem(
                        entity_type="CUTOFF",
                        entity_identifier=row_id,
                        error_code="INVALID_OPENING_RANK",
                        message=f"Opening rank must be positive, got: {o_rank}",
                        severity=ValidationSeverity.ERROR.value
                    ))
                    continue
                if o_rank > c_rank:
                    errors.append(ValidationErrorItem(
                        entity_type="CUTOFF",
                        entity_identifier=row_id,
                        error_code="OPENING_GREATER_THAN_CLOSING",
                        message=f"Opening rank ({o_rank}) is greater than closing rank ({c_rank})",
                        severity=ValidationSeverity.ERROR.value,
                        context_data={"opening": o_rank, "closing": c_rank}
                    ))
                    continue

            # 6. Rank upper bound anomaly check
            if c_rank > self.MAX_REASONABLE_RANK:
                anomalies.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="ANOMALOUS_HIGH_RANK",
                    message=f"Closing rank {c_rank} exceeds typical COMEDK candidate ceiling ({self.MAX_REASONABLE_RANK})",
                    severity=ValidationSeverity.WARNING.value,
                    context_data={"closing_rank": c_rank}
                ))

            # 7. Duplicate logical key check
            logical_key = (c_code, b_code, cat_code, r_code, academic_year)
            if logical_key in seen_logical_keys:
                errors.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="DUPLICATE_LOGICAL_RECORD",
                    message=f"Duplicate cutoff record in same batch for key {logical_key}",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"logical_key": str(logical_key)}
                ))
                continue
            seen_logical_keys.add(logical_key)

            # Record passed all checks
            rec["status"] = RecordStatus.PUBLISHED.value
            valid_records.append(rec)

        return valid_records, errors, anomalies

    def validate_document_anomaly(
        self,
        doc_type: str,
        extracted_count: int,
        is_usable_text: bool
    ) -> List[ValidationErrorItem]:
        anomalies: List[ValidationErrorItem] = []
        if not is_usable_text:
            anomalies.append(ValidationErrorItem(
                entity_type="DOCUMENT",
                entity_identifier=doc_type,
                error_code="SCANNED_OR_EMPTY_PDF",
                message="PDF document has non-extractable text; requires OCR or manual review",
                severity=ValidationSeverity.WARNING.value
            ))
        elif extracted_count == 0 and "HTML" not in doc_type and "NOTIFICATION" not in doc_type:
            anomalies.append(ValidationErrorItem(
                entity_type="DOCUMENT",
                entity_identifier=doc_type,
                error_code="SUSPICIOUSLY_EMPTY_DOCUMENT",
                message=f"0 records extracted from structured {doc_type} document",
                severity=ValidationSeverity.WARNING.value
            ))
        return anomalies
