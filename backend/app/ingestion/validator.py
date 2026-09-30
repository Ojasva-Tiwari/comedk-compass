from decimal import Decimal
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
        ("VACANT_SEATS_PDF", "ENGINEERING"): 50,
        ("VACANT_SEATS_PDF", "ARCHITECTURE"): 4,
        ("SEAT_MATRIX_PDF", "ENGINEERING"): 50,
        ("SEAT_MATRIX_PDF", "ARCHITECTURE"): 4,
        ("FEE_STRUCTURE_PDF", "ENGINEERING"): 50,
        ("FEE_STRUCTURE_PDF", "ARCHITECTURE"): 4,
        "ENGINEERING_CUTOFF": 50,
        "ARCHITECTURE_CUTOFF": 4,
        "ENGINEERING_VACANT_SEATS": 50,
        "ARCHITECTURE_VACANT_SEATS": 4,
        "ENGINEERING_SEAT_MATRIX": 50,
        "ARCHITECTURE_SEAT_MATRIX": 4,
        "ENGINEERING_FEE_STRUCTURE": 50,
        "ARCHITECTURE_FEE_STRUCTURE": 4,
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

            # 3. Round validity check: COMEDK rounds across all years
            valid_rounds = {"R1", "R3", "R4", "MOCK", "KKR_SPECIAL", "R2_PHASE2", "CONSOLIDATED_FINAL"}
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

    def validate_seat_records(
        self,
        records: List[Dict[str, Any]],
        academic_year: int
    ) -> Tuple[List[Dict[str, Any]], List[ValidationErrorItem], List[ValidationErrorItem]]:
        """
        Validates a batch of raw seat/vacancy records.
        Returns: (valid_records, validation_errors, anomalies)
        """
        valid_records: List[Dict[str, Any]] = []
        errors: List[ValidationErrorItem] = []
        anomalies: List[ValidationErrorItem] = []
        seen_logical_keys: Set[Tuple] = set()

        for idx, rec in enumerate(records):
            c_code = rec.get("college_code")
            b_code = rec.get("branch_code")
            r_code = rec.get("counselling_round")
            cat_code = rec.get("category_code")
            tot_seats = rec.get("total_seats")
            vac_seats = rec.get("vacant_seats")
            gm_seats = rec.get("gm_seats")
            kkr_seats = rec.get("kkr_seats")
            year = rec.get("academic_year", academic_year)
            row_id = rec.get("row_identifier", f"seat_rec_{idx}")

            # 1. Required fields
            if not c_code:
                errors.append(ValidationErrorItem(
                    entity_type="SEAT",
                    entity_identifier=row_id,
                    error_code="MISSING_COLLEGE_CODE",
                    message="Seat record is missing required college_code",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            if not b_code:
                errors.append(ValidationErrorItem(
                    entity_type="SEAT",
                    entity_identifier=row_id,
                    error_code="MISSING_BRANCH_CODE",
                    message="Seat record is missing required branch_code",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            if tot_seats is None and vac_seats is None:
                errors.append(ValidationErrorItem(
                    entity_type="SEAT",
                    entity_identifier=row_id,
                    error_code="MISSING_SEAT_VALUES",
                    message="Seat record must provide at least total_seats or vacant_seats",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            # 2. College code existence check
            if c_code not in self.known_college_codes:
                errors.append(ValidationErrorItem(
                    entity_type="SEAT",
                    entity_identifier=row_id,
                    error_code="UNKNOWN_COLLEGE_CODE",
                    message=f"College code '{c_code}' does not exist in registry",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"college_code": c_code}
                ))
                continue

            # 3. Branch code existence check
            if b_code not in self.known_branch_codes:
                errors.append(ValidationErrorItem(
                    entity_type="SEAT",
                    entity_identifier=row_id,
                    error_code="UNKNOWN_BRANCH_CODE",
                    message=f"Branch code '{b_code}' does not exist in registry",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"branch_code": b_code}
                ))
                continue

            # 4. Numeric seat values & non-negative values
            has_numeric_err = False
            for val_name, val in [("total_seats", tot_seats), ("vacant_seats", vac_seats), ("gm_seats", gm_seats), ("kkr_seats", kkr_seats)]:
                if val is not None:
                    if not isinstance(val, int) or val < 0:
                        errors.append(ValidationErrorItem(
                            entity_type="SEAT",
                            entity_identifier=row_id,
                            error_code=f"INVALID_{val_name.upper()}",
                            message=f"{val_name} must be a non-negative integer, got: {val}",
                            severity=ValidationSeverity.ERROR.value,
                            context_data={"field": val_name, "value": val}
                        ))
                        has_numeric_err = True
            if has_numeric_err:
                continue

            # 5. Logical consistency
            # If both total_seats and vacant_seats are present: vacant_seats <= total_seats
            if tot_seats is not None and vac_seats is not None:
                if vac_seats > tot_seats:
                    errors.append(ValidationErrorItem(
                        entity_type="SEAT",
                        entity_identifier=row_id,
                        error_code="VACANCY_EXCEEDS_TOTAL_SEATS",
                        message=f"Vacant seats ({vac_seats}) exceeds total seats ({tot_seats})",
                        severity=ValidationSeverity.ERROR.value,
                        context_data={"total_seats": tot_seats, "vacant_seats": vac_seats}
                    ))
                    continue

            if gm_seats is not None and kkr_seats is not None and tot_seats is not None:
                if (gm_seats + kkr_seats) > tot_seats:
                    errors.append(ValidationErrorItem(
                        entity_type="SEAT",
                        entity_identifier=row_id,
                        error_code="SEAT_SUM_EXCEEDS_TOTAL",
                        message=f"Sum of GM ({gm_seats}) and KKR ({kkr_seats}) seats exceeds total seats ({tot_seats})",
                        severity=ValidationSeverity.ERROR.value,
                        context_data={"gm_seats": gm_seats, "kkr_seats": kkr_seats, "total_seats": tot_seats}
                    ))
                    continue

            if gm_seats is not None and kkr_seats is not None and vac_seats is not None:
                if (gm_seats + kkr_seats) > vac_seats:
                    errors.append(ValidationErrorItem(
                        entity_type="SEAT",
                        entity_identifier=row_id,
                        error_code="SEAT_SUM_EXCEEDS_VACANCY",
                        message=f"Sum of GM ({gm_seats}) and KKR ({kkr_seats}) vacant seats exceeds total vacant seats ({vac_seats})",
                        severity=ValidationSeverity.ERROR.value,
                        context_data={"gm_seats": gm_seats, "kkr_seats": kkr_seats, "vacant_seats": vac_seats}
                    ))
                    continue

            # 6. Duplicate logical record check
            logical_key = (c_code, b_code, r_code, cat_code, year)
            if logical_key in seen_logical_keys:
                errors.append(ValidationErrorItem(
                    entity_type="SEAT",
                    entity_identifier=row_id,
                    error_code="DUPLICATE_LOGICAL_RECORD",
                    message=f"Duplicate seat record in same batch for key {logical_key}",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"logical_key": str(logical_key)}
                ))
                continue
            seen_logical_keys.add(logical_key)

            rec["status"] = RecordStatus.PUBLISHED.value
            valid_records.append(rec)

        return valid_records, errors, anomalies

    def validate_fee_records(
        self,
        records: List[Dict[str, Any]],
        academic_year: int
    ) -> Tuple[List[Dict[str, Any]], List[ValidationErrorItem], List[ValidationErrorItem]]:
        """
        Validates a batch of raw fee records.
        Returns: (valid_records, validation_errors, anomalies)
        """
        valid_records: List[Dict[str, Any]] = []
        errors: List[ValidationErrorItem] = []
        anomalies: List[ValidationErrorItem] = []
        seen_logical_keys: Set[Tuple] = set()

        for idx, rec in enumerate(records):
            c_code = rec.get("college_code")
            b_code = rec.get("branch_code")
            tot_fee = rec.get("total_fee")
            tuit_fee = rec.get("tuition_fee")
            oth_fee = rec.get("other_fee")
            year = rec.get("academic_year", academic_year)
            row_id = rec.get("row_identifier", f"fee_rec_{idx}")

            # 1. Required fields
            if not c_code:
                errors.append(ValidationErrorItem(
                    entity_type="FEE",
                    entity_identifier=row_id,
                    error_code="MISSING_COLLEGE_CODE",
                    message="Fee record is missing required college_code",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            if tot_fee is None:
                errors.append(ValidationErrorItem(
                    entity_type="FEE",
                    entity_identifier=row_id,
                    error_code="MISSING_TOTAL_FEE",
                    message="Fee record is missing required total_fee",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"record": rec}
                ))
                continue

            # 2. College code existence check
            if c_code not in self.known_college_codes:
                errors.append(ValidationErrorItem(
                    entity_type="FEE",
                    entity_identifier=row_id,
                    error_code="UNKNOWN_COLLEGE_CODE",
                    message=f"College code '{c_code}' does not exist in registry",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"college_code": c_code}
                ))
                continue

            # 3. Branch code existence check (if branch is provided)
            if b_code and b_code not in self.known_branch_codes:
                errors.append(ValidationErrorItem(
                    entity_type="FEE",
                    entity_identifier=row_id,
                    error_code="UNKNOWN_BRANCH_CODE",
                    message=f"Branch code '{b_code}' does not exist in registry",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"branch_code": b_code}
                ))
                continue

            # 4. Numeric fee values & non-negative values
            has_fee_err = False
            for val_name, val in [("total_fee", tot_fee), ("tuition_fee", tuit_fee), ("other_fee", oth_fee)]:
                if val is not None:
                    try:
                        num_val = Decimal(str(val))
                        if num_val < Decimal("0"):
                            errors.append(ValidationErrorItem(
                                entity_type="FEE",
                                entity_identifier=row_id,
                                error_code=f"INVALID_{val_name.upper()}",
                                message=f"{val_name} must be non-negative, got: {val}",
                                severity=ValidationSeverity.ERROR.value,
                                context_data={"field": val_name, "value": str(val)}
                            ))
                            has_fee_err = True
                    except Exception:
                        errors.append(ValidationErrorItem(
                            entity_type="FEE",
                            entity_identifier=row_id,
                            error_code=f"NON_NUMERIC_{val_name.upper()}",
                            message=f"{val_name} must be a valid numeric amount, got: {val}",
                            severity=ValidationSeverity.ERROR.value,
                            context_data={"field": val_name, "value": str(val)}
                        ))
                        has_fee_err = True

            if has_fee_err:
                continue

            dec_tot = Decimal(str(tot_fee))
            dec_tuit = Decimal(str(tuit_fee)) if tuit_fee is not None else None
            dec_oth = Decimal(str(oth_fee)) if oth_fee is not None else None

            # 5. Logical consistency
            # Check individual components do not exceed total
            if dec_tuit is not None and dec_tuit > dec_tot:
                errors.append(ValidationErrorItem(
                    entity_type="FEE",
                    entity_identifier=row_id,
                    error_code="TUITION_EXCEEDS_TOTAL_FEE",
                    message=f"Tuition fee ({dec_tuit}) exceeds total fee ({dec_tot})",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"tuition_fee": str(dec_tuit), "total_fee": str(dec_tot)}
                ))
                continue

            if dec_oth is not None and dec_oth > dec_tot:
                errors.append(ValidationErrorItem(
                    entity_type="FEE",
                    entity_identifier=row_id,
                    error_code="OTHER_FEE_EXCEEDS_TOTAL_FEE",
                    message=f"Other fee ({dec_oth}) exceeds total fee ({dec_tot})",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"other_fee": str(dec_oth), "total_fee": str(dec_tot)}
                ))
                continue

            # If both components are present, sum must match total fee (allowing rounding up to 100)
            if dec_tuit is not None and dec_oth is not None:
                comp_sum = dec_tuit + dec_oth
                if abs(comp_sum - dec_tot) > Decimal("100"):
                    errors.append(ValidationErrorItem(
                        entity_type="FEE",
                        entity_identifier=row_id,
                        error_code="FEE_COMPONENTS_MISMATCH",
                        message=f"Sum of tuition ({dec_tuit}) and other fee ({dec_oth}) = {comp_sum} does not match total fee ({dec_tot})",
                        severity=ValidationSeverity.ERROR.value,
                        context_data={"tuition_fee": str(dec_tuit), "other_fee": str(dec_oth), "total_fee": str(dec_tot)}
                    ))
                    continue

            # 6. Duplicate logical records check
            logical_key = (c_code, b_code, year)
            if logical_key in seen_logical_keys:
                errors.append(ValidationErrorItem(
                    entity_type="FEE",
                    entity_identifier=row_id,
                    error_code="DUPLICATE_LOGICAL_RECORD",
                    message=f"Duplicate fee record in same batch for key {logical_key}",
                    severity=ValidationSeverity.ERROR.value,
                    context_data={"logical_key": str(logical_key)}
                ))
                continue
            seen_logical_keys.add(logical_key)

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
        Prevents an incomplete parse from superseding good data.

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

        # 3. Vacancy PDF Completeness Validation
        elif doc_type == DocumentType.VACANT_SEATS_PDF.value:
            ptype = (program_type or ProgramType.ENGINEERING.value).upper()
            resolved_min = (
                minimum_threshold
                if minimum_threshold is not None
                else self.get_completeness_threshold(doc_type, ptype)
            )

            if extracted_count <= 0:
                errors.append(ValidationErrorItem(
                    entity_type="DOCUMENT",
                    entity_identifier=doc_type,
                    error_code="SUSPICIOUS_LOW_COUNT",
                    message=f"Parsed 0 vacancy records for {ptype}; document is empty or unparseable.",
                    severity=ValidationSeverity.CRITICAL.value,
                    context_data={"extracted": extracted_count, "minimum": resolved_min, "program_type": ptype}
                ))
                return errors

            if extracted_count < resolved_min:
                errors.append(ValidationErrorItem(
                    entity_type="DOCUMENT",
                    entity_identifier=doc_type,
                    error_code="SUSPICIOUS_LOW_COUNT",
                    message=f"{ptype} vacancy parse yielded only {extracted_count} records (minimum expected: {resolved_min})",
                    severity=ValidationSeverity.CRITICAL.value,
                    context_data={"extracted": extracted_count, "minimum": resolved_min, "program_type": ptype}
                ))

        # 4. Seat Matrix & Fee Structure PDF Completeness Validation
        elif doc_type in (DocumentType.SEAT_MATRIX_PDF.value, DocumentType.FEE_STRUCTURE_PDF.value):
            ptype = (program_type or ProgramType.ENGINEERING.value).upper()
            resolved_min = (
                minimum_threshold
                if minimum_threshold is not None
                else self.get_completeness_threshold(doc_type, ptype)
            )

            if extracted_count <= 0:
                errors.append(ValidationErrorItem(
                    entity_type="DOCUMENT",
                    entity_identifier=doc_type,
                    error_code="SUSPICIOUS_LOW_COUNT",
                    message=f"Parsed 0 records for {ptype} {doc_type}; document is empty or unparseable.",
                    severity=ValidationSeverity.CRITICAL.value,
                    context_data={"extracted": extracted_count, "minimum": resolved_min, "program_type": ptype}
                ))
                return errors

            if extracted_count < resolved_min:
                errors.append(ValidationErrorItem(
                    entity_type="DOCUMENT",
                    entity_identifier=doc_type,
                    error_code="SUSPICIOUS_LOW_COUNT",
                    message=f"{ptype} {doc_type} parse yielded only {extracted_count} records (minimum expected: {resolved_min})",
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

