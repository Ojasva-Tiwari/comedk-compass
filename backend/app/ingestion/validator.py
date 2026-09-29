from typing import List, Dict, Any, Tuple, Optional, Set
from uuid import UUID
from backend.app.config import settings
from backend.app.core.enums import RecordStatus, ValidationSeverity, DocumentType, ProgramType

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

    DEFAULT_COMPLETENESS_THRESHOLDS: Dict[Any, int] = {
        ("CUTOFF_PDF", "ENGINEERING"): 50,
        ("CUTOFF_PDF", "ARCHITECTURE"): 4,
        "ENGINEERING_CUTOFF": 50,
        "ARCHITECTURE_CUTOFF": 4,
    }

    def __init__(
        self,
        known_college_codes: Set[str],
        known_branch_codes: Set[str],
        known_categories: Set[str],
        completeness_thresholds: Optional[Dict[Any, int]] = None,
    ):
        self.known_college_codes = known_college_codes
        self.known_branch_codes = known_branch_codes
        self.known_categories = known_categories
        self.completeness_thresholds = dict(self.DEFAULT_COMPLETENESS_THRESHOLDS)
        if completeness_thresholds:
            self.completeness_thresholds.update(completeness_thresholds)

    def get_completeness_threshold(self, doc_type: str, program_type: Optional[str] = None) -> int:
        ptype = (program_type or ProgramType.ENGINEERING.value).upper()
        dtype = (doc_type or "").upper()

        if (dtype, ptype) in self.completeness_thresholds:
            return self.completeness_thresholds[(dtype, ptype)]

        compound_key = f"{ptype}_{dtype.replace('_PDF', '')}"
        if compound_key in self.completeness_thresholds:
            return self.completeness_thresholds[compound_key]

        if dtype in self.completeness_thresholds:
            return self.completeness_thresholds[dtype]

        if ptype == ProgramType.ARCHITECTURE.value:
            return getattr(settings, "MIN_CUTOFF_THRESHOLD_ARCHITECTURE", 4)
        return getattr(settings, "MIN_CUTOFF_THRESHOLD_ENGINEERING", 50)

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

            # 3. Round validity check
            valid_rounds = {"R1", "R2", "R3", "R4", "MOCK"}
            if not r_code or r_code not in valid_rounds:
                errors.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="INVALID_COUNSELLING_ROUND",
                    message=f"Invalid counselling round '{r_code}'. Expected one of {valid_rounds}",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"round": r_code}
                ))
                continue

            # 4. Category validity check
            if not cat_code or cat_code not in self.known_categories:
                anomalies.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="UNEXPECTED_CATEGORY",
                    message=f"Category '{cat_code}' is unexpected for COMEDK quota",
                    severity=ValidationSeverity.WARNING.value,
                    context_data={"category": cat_code}
                ))

            # 5. Rank positivity check
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

            # 6. Opening rank relationship
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

            # 7. Rank upper bound anomaly check
            if c_rank > self.MAX_REASONABLE_RANK:
                anomalies.append(ValidationErrorItem(
                    entity_type="CUTOFF",
                    entity_identifier=row_id,
                    error_code="ANOMALOUS_HIGH_RANK",
                    message=f"Closing rank {c_rank} exceeds typical COMEDK candidate ceiling ({self.MAX_REASONABLE_RANK})",
                    severity=ValidationSeverity.WARNING.value,
                    context_data={"closing_rank": c_rank}
                ))

            # 8. Duplicate logical key check
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

    def validate_batch_completeness(
        self,
        doc_type: str,
        extracted_count: int,
        historical_baseline_count: Optional[int] = None,
        program_type: Optional[str] = None,
        minimum_threshold: Optional[int] = None
    ) -> List[ValidationErrorItem]:
        """
        Enforces FAIL CLOSED principle for truncated, suspicious, or unknown parses.
        Prevents an incomplete parse (e.g., 37 engineering records when 1,200 expected,
        or 2 architecture records when 4 expected) from superseding good data.

        Configurable by document type and program type (Engineering vs Architecture).
        Unknown document types automatically fail closed and are routed to review.
        """
        errors: List[ValidationErrorItem] = []

        # 1. Unknown or unrecognized document types fail closed
        if not doc_type or doc_type in (DocumentType.UNKNOWN.value, "UNKNOWN", "OTHER"):
            errors.append(ValidationErrorItem(
                entity_type="DOCUMENT",
                entity_identifier=doc_type or "UNKNOWN",
                error_code="UNKNOWN_DOCUMENT_TYPE",
                message=f"Document type '{doc_type}' cannot be verified for batch completeness; requires manual review.",
                severity=ValidationSeverity.CRITICAL.value,
                context_data={"doc_type": doc_type, "extracted_count": extracted_count}
            ))
            return errors

        # 2. Cutoff PDF Completeness Validation
        if doc_type == DocumentType.CUTOFF_PDF.value:
            ptype = (program_type or ProgramType.ENGINEERING.value).upper()
            resolved_min = (
                minimum_threshold
                if minimum_threshold is not None
                else self.get_completeness_threshold(doc_type, ptype)
            )

            # Truly incomplete data: 0 or negative records
            if extracted_count <= 0:
                errors.append(ValidationErrorItem(
                    entity_type="DOCUMENT",
                    entity_identifier=doc_type,
                    error_code="SUSPICIOUS_LOW_COUNT",
                    message=f"Parsed 0 cutoff records for {ptype}; document is empty or unparseable.",
                    severity=ValidationSeverity.CRITICAL.value,
                    context_data={"extracted": extracted_count, "minimum": resolved_min, "program_type": ptype}
                ))
                return errors

            # Engineering strict historical baseline check (>100 records baseline, 30% threshold)
            if ptype == ProgramType.ENGINEERING.value and historical_baseline_count and historical_baseline_count > 100:
                dynamic_threshold = int(historical_baseline_count * 0.3)
                if extracted_count < dynamic_threshold:
                    errors.append(ValidationErrorItem(
                        entity_type="DOCUMENT",
                        entity_identifier=doc_type,
                        error_code="SUSPICIOUS_LOW_COUNT",
                        message=(
                            f"Suspiciously low {ptype} record count: parsed {extracted_count} records, "
                            f"which is far below the baseline of {historical_baseline_count} (threshold: {dynamic_threshold})"
                        ),
                        severity=ValidationSeverity.CRITICAL.value,
                        context_data={
                            "extracted": extracted_count,
                            "baseline": historical_baseline_count,
                            "threshold": dynamic_threshold,
                            "program_type": ptype
                        }
                    ))
                    return errors

            # Check against program-specific minimum threshold (e.g. 50 for Engineering, 4 for Architecture)
            if extracted_count < resolved_min:
                errors.append(ValidationErrorItem(
                    entity_type="DOCUMENT",
                    entity_identifier=doc_type,
                    error_code="SUSPICIOUS_LOW_COUNT",
                    message=(
                        f"{ptype} cutoff parse yielded only {extracted_count} records "
                        f"(minimum expected: {resolved_min})"
                    ),
                    severity=ValidationSeverity.CRITICAL.value,
                    context_data={"extracted": extracted_count, "minimum": resolved_min, "program_type": ptype}
                ))

        return errors

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

