import re
from decimal import Decimal
from typing import Optional, Dict, Any, List
import pymupdf
from backend.app.ingestion.parsers.base import BaseParser, ParseResult
from backend.app.ingestion.normalizer import Normalizer
from backend.app.core.enums import RecordStatus

class SeatAndFeeParser(BaseParser):
    """
    Parses official COMEDK Seat Availability, Vacant Seats, and Fee Structure PDFs.
    Extracts seat_records (total_seats and/or vacant_seats) and fee_records, along with branch/college metadata.
    """
    def parse(self, content: bytes, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        result = ParseResult()
        ctx = context or {}
        academic_year = ctx.get("academic_year", 2026)
        counselling_round = ctx.get("counselling_round")
        if not counselling_round:
            title_hint = str(ctx.get("source_title", ""))
            from backend.app.ingestion.classifier import DocumentClassifier
            counselling_round = DocumentClassifier.extract_counselling_round(title_hint)

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            result.page_count = len(doc)
        except Exception as e:
            result.status = RecordStatus.REJECTED
            result.is_usable_text = False
            result.errors.append({"error": f"Failed to open Seat/Fee PDF: {e}"})
            return result

        if result.page_count == 0:
            result.status = RecordStatus.REJECTED
            result.is_usable_text = False
            result.errors.append({"error": "PDF has 0 pages"})
            return result

        # Verify usable text across the document
        total_text = ""
        for page in doc:
            total_text += page.get_text()

        if len(total_text.strip()) < 50:
            result.is_usable_text = False
            result.status = RecordStatus.NEEDS_REVIEW
            result.errors.append({"error": "PDF has non-extractable text or is scanned"})
            return result

        seat_records = []
        fee_records = []
        discovered_branches: Dict[str, str] = {}
        discovered_colleges_dict: Dict[str, Dict[str, Any]] = {}

        def clean_int(val: Any) -> Optional[int]:
            if val is None:
                return None
            nums = re.sub(r'[^0-9]', '', str(val))
            return int(nums) if nums else None

        def clean_decimal(val: Any) -> Optional[Decimal]:
            if val is None:
                return None
            nums = re.sub(r'[^0-9.]', '', str(val))
            try:
                return Decimal(nums) if nums else None
            except Exception:
                return None

        # Determine if document as a whole is a vacancy document
        doc_type_hint = str(ctx.get("document_type", "")).lower()
        title_hint = str(ctx.get("source_title", "")).lower()
        is_vacancy_doc = "vacant" in doc_type_hint or "vacancy" in doc_type_hint or "vacant" in title_hint or "vacancy" in title_hint

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            try:
                table_finder = page.find_tables()
                tables = table_finder.tables
            except Exception as e:
                result.anomalies.append({
                    "warning": f"Table extraction issue on page {page_idx+1}: {e}"
                })
                continue

            for table in tables:
                extracted = table.extract()
                if not extracted or len(extracted) < 2:
                    continue

                headers = [Normalizer.clean_text(h or '') for h in extracted[0]]
                headers_lower = [h.lower() for h in headers]
                header_str = " ".join(headers_lower)
                is_vacancy_table = is_vacancy_doc or any(kw in header_str for kw in ["vacant", "vacancy"])

                for row_idx, row in enumerate(extracted[1:]):
                    # Need at least college code, college name, course, and at least one numeric column
                    if len(row) < 4:
                        continue

                    raw_code = row[0]
                    raw_college_name = row[1]
                    raw_course = row[2]

                    if not raw_code or not raw_course:
                        continue

                    # Skip repeated header rows
                    if "college" in str(raw_code).lower() or "code" in str(raw_code).lower():
                        continue

                    norm_code = Normalizer.normalize_college_code(raw_code)
                    norm_college_name, orig_college_name = Normalizer.normalize_college_name(raw_college_name or "")

                    if not norm_code:
                        continue

                    # Parse branch code and name from course cell (e.g. 'AE-Aeronautical Engineering')
                    course_str = " ".join(raw_course.split())
                    if "-" in course_str:
                        parts = course_str.split("-", 1)
                        b_code = Normalizer.normalize_branch_code(parts[0])
                        b_name, orig_b_name = Normalizer.normalize_branch_name(parts[1])
                    else:
                        b_code = Normalizer.normalize_branch_code(course_str[:4])
                        b_name, orig_b_name = Normalizer.normalize_branch_name(course_str)

                    if not b_code:
                        continue

                    if b_code not in discovered_branches:
                        discovered_branches[b_code] = b_name

                    if norm_code not in discovered_colleges_dict and norm_college_name:
                        discovered_colleges_dict[norm_code] = {
                            "code": norm_code,
                            "name": norm_college_name,
                            "original_name": orig_college_name,
                            "location": None
                        }

                    row_identifier = f"{norm_code}_{b_code}_{page_idx+1}_{row_idx+1}"

                    # Case A: Vacancy table (4, 5, or 6 columns)
                    if is_vacancy_table or (len(row) < 7 and not any("fee" in h for h in headers_lower)):
                        vacant_val: Optional[int] = None
                        gm_vac: Optional[int] = None
                        kkr_vac: Optional[int] = None
                        cat_code: Optional[str] = None

                        if len(row) >= 6 and len(headers_lower) >= 6 and "gm" in headers_lower[4] and "kkr" in headers_lower[5]:
                            # 6-col structure: Total Seats Vacant, GM Seats Vacant, KKR Seats Vacant
                            total_vac = clean_int(row[3])
                            gm_vac = clean_int(row[4])
                            kkr_vac = clean_int(row[5])
                            vacant_val = total_vac if total_vac is not None else ((gm_vac or 0) + (kkr_vac or 0))
                        elif len(row) == 5:
                            # 5-col structure: (GM, KKR) or (Total, GM)
                            if len(headers_lower) >= 5 and "total" in headers_lower[3] and "gm" in headers_lower[4]:
                                total_vac = clean_int(row[3])
                                gm_vac = clean_int(row[4])
                                vacant_val = total_vac
                            else:
                                gm_vac = clean_int(row[3])
                                kkr_vac = clean_int(row[4])
                                vacant_val = (gm_vac or 0) + (kkr_vac or 0)
                        else:
                            # 4-col structure: col 3 is the vacancy value
                            h3 = headers_lower[3] if len(headers_lower) > 3 else ""
                            vacant_val = clean_int(row[3])
                            if "kkr" in h3:
                                cat_code = "KKR"
                                kkr_vac = vacant_val
                            elif "gm" in h3:
                                cat_code = "GM"
                                gm_vac = vacant_val

                        if vacant_val is not None:
                            seat_records.append({
                                "college_code": norm_code,
                                "college_name": norm_college_name,
                                "branch_code": b_code,
                                "branch_name": b_name,
                                "academic_year": academic_year,
                                "counselling_round": counselling_round,
                                "total_seats": None,
                                "vacant_seats": vacant_val,
                                "gm_seats": gm_vac,
                                "kkr_seats": kkr_vac,
                                "category_code": cat_code,
                                "page_number": page_idx + 1,
                                "row_identifier": row_identifier
                            })
                        else:
                            result.errors.append({
                                "error": f"Malformed vacancy row at page {page_idx+1}, row {row_idx+1}: {row}",
                                "row_identifier": row_identifier
                            })

                    # Case B: Initial Seat Availability & Fee Structure table (7 to 9 columns)
                    else:
                        total_seats = clean_int(row[3]) if len(row) > 3 else None
                        gm_seats = clean_int(row[4]) if len(row) > 4 else None
                        kkr_seats = clean_int(row[5]) if len(row) > 5 else None

                        if total_seats is not None:
                            seat_records.append({
                                "college_code": norm_code,
                                "college_name": norm_college_name,
                                "branch_code": b_code,
                                "branch_name": b_name,
                                "academic_year": academic_year,
                                "counselling_round": counselling_round,
                                "total_seats": total_seats,
                                "vacant_seats": None,
                                "gm_seats": gm_seats,
                                "kkr_seats": kkr_seats,
                                "category_code": None,
                                "page_number": page_idx + 1,
                                "row_identifier": row_identifier
                            })

                        # Fees extraction
                        tuition_fee = clean_decimal(row[6]) if len(row) > 6 else None
                        other_fee = clean_decimal(row[7]) if len(row) > 7 else None
                        total_fee = clean_decimal(row[8]) if len(row) > 8 else (tuition_fee if tuition_fee is not None else None)

                        if total_fee is not None or tuition_fee is not None:
                            effective_total = total_fee or tuition_fee or Decimal("0")
                            fee_records.append({
                                "college_code": norm_code,
                                "branch_code": b_code,
                                "academic_year": academic_year,
                                "total_fee": effective_total,
                                "tuition_fee": tuition_fee,
                                "other_fee": other_fee,
                                "currency": "INR",
                                "page_number": page_idx + 1,
                                "row_identifier": row_identifier
                            })

        result.metadata["seat_records"] = seat_records
        result.metadata["fee_records"] = fee_records
        result.discovered_branches = discovered_branches
        result.discovered_colleges = list(discovered_colleges_dict.values())
        result.row_count = len(seat_records) + len(fee_records)
        if result.errors:
            result.status = RecordStatus.NEEDS_REVIEW
        elif seat_records or fee_records:
            result.status = RecordStatus.PARSED
        else:
            result.status = RecordStatus.NEEDS_REVIEW
        return result
