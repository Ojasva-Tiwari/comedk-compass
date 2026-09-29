import re
from decimal import Decimal
from typing import Optional, Dict, Any, List
import pymupdf
from backend.app.ingestion.parsers.base import BaseParser, ParseResult
from backend.app.ingestion.normalizer import Normalizer
from backend.app.core.enums import RecordStatus

class SeatAndFeeParser(BaseParser):
    """
    Parses official COMEDK Seat Availability and Fee Structure PDFs.
    Extracts both seat_records and fee_records, along with branch/college metadata.
    """
    def parse(self, content: bytes, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        result = ParseResult()
        ctx = context or {}
        academic_year = ctx.get("academic_year", 2026)

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            result.page_count = len(doc)
        except Exception as e:
            result.status = RecordStatus.REJECTED
            result.errors.append({"error": f"Failed to open Seat/Fee PDF: {e}"})
            return result

        if result.page_count == 0:
            result.status = RecordStatus.REJECTED
            result.errors.append({"error": "PDF has 0 pages"})
            return result

        seat_records = []
        fee_records = []
        discovered_branches: Dict[str, str] = {}
        discovered_colleges_dict: Dict[str, Dict[str, Any]] = {}

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

                for row in extracted[1:]:
                    if len(row) < 7:
                        continue

                    raw_code = row[0]
                    raw_college_name = row[1]
                    raw_course = row[2]

                    if not raw_code or not raw_course:
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

                    # Total seats
                    def clean_int(val: Any) -> Optional[int]:
                        if not val:
                            return None
                        nums = re.sub(r'[^0-9]', '', str(val))
                        return int(nums) if nums else None

                    total_seats = clean_int(row[3]) if len(row) > 3 else None
                    gm_seats = clean_int(row[4]) if len(row) > 4 else None
                    kkr_seats = clean_int(row[5]) if len(row) > 5 else None

                    if total_seats is not None:
                        seat_records.append({
                            "college_code": norm_code,
                            "branch_code": b_code,
                            "academic_year": academic_year,
                            "total_seats": total_seats,
                            "vacant_seats": None, # Initial matrix lists total seats; vacancy PDFs list vacant seats
                            "gm_seats": gm_seats,
                            "kkr_seats": kkr_seats,
                            "page_number": page_idx + 1
                        })

                    # Fees
                    def clean_decimal(val: Any) -> Optional[Decimal]:
                        if not val:
                            return None
                        nums = re.sub(r'[^0-9.]', '', str(val))
                        try:
                            return Decimal(nums) if nums else None
                        except Exception:
                            return None

                    tuition_fee = clean_decimal(row[6]) if len(row) > 6 else None
                    other_fee = clean_decimal(row[7]) if len(row) > 7 else None
                    total_fee = clean_decimal(row[8]) if len(row) > 8 else None

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
                            "page_number": page_idx + 1
                        })

        result.metadata["seat_records"] = seat_records
        result.metadata["fee_records"] = fee_records
        result.discovered_branches = discovered_branches
        result.discovered_colleges = list(discovered_colleges_dict.values())
        result.row_count = len(seat_records) + len(fee_records)
        result.status = RecordStatus.PARSED if (seat_records or fee_records) else RecordStatus.NEEDS_REVIEW
        return result
