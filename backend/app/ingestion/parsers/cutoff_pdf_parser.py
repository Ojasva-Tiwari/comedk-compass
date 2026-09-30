import re
from typing import Optional, Dict, Any, List, Set, Tuple
import pymupdf
from backend.app.ingestion.parsers.base import BaseParser, ParseResult, OCRInterface
from backend.app.ingestion.normalizer import Normalizer
from backend.app.core.enums import RecordStatus

class CutoffPDFParser(BaseParser):
    """
    Parses official COMEDK Cut-off rank PDFs.
    Uses PyMuPDF table extraction with robust character and layout verification.
    """
    MIN_USABLE_TEXT_CHARS = 100

    def parse(self, content: bytes, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        result = ParseResult()
        ctx = context or {}
        academic_year = ctx.get("academic_year", 2026)
        round_raw = ctx.get("counselling_round", "R1")

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
            result.page_count = len(doc)
        except Exception as e:
            result.status = RecordStatus.REJECTED
            result.errors.append({"error": f"Failed to open PDF document: {e}"})
            return result

        if result.page_count == 0:
            result.status = RecordStatus.REJECTED
            result.errors.append({"error": "PDF has 0 pages"})
            return result

        # Check usable text across first few pages
        total_sample_chars = 0
        for pno in range(min(3, len(doc))):
            total_sample_chars += len(doc[pno].get_text().strip())

        if total_sample_chars < self.MIN_USABLE_TEXT_CHARS:
            result.is_usable_text = False
            result.status = RecordStatus.NEEDS_REVIEW
            result.anomalies.append({
                "warning": "PDF appears to be scanned or contains insufficient extractable text",
                "character_count": total_sample_chars,
                "pages": len(doc)
            })
            return result

        records = []
        discovered_branches: Dict[str, str] = {}
        discovered_colleges_dict: Dict[str, Dict[str, Any]] = {}
        extracted_pages: Set[int] = set()
        raw_rows_detected = 0

        round_code, round_name, round_num = Normalizer.normalize_round(round_raw, academic_year)

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            try:
                table_finder = page.find_tables()
                tables = table_finder.tables
            except Exception as e:
                result.anomalies.append({
                    "warning": f"Table finder exception on page {page_idx+1}: {e}"
                })
                continue

            for table in tables:
                extracted = table.extract()
                if not extracted or len(extracted) < 2:
                    continue

                raw_header = extracted[0]
                header_clean = [Normalizer.clean_text(c).lower() if c else "" for c in raw_header]

                # Format B: 4-column vertical layout (College Code, College Name, Course Name, Cutoff)
                is_4col_vertical = (
                    len(raw_header) == 4
                    and any("cutoff" in c or "cut-off" in c or "cut off" in c for c in header_clean[2:])
                    and any("course" in c or "branch" in c for c in header_clean[1:3])
                )

                # Format C: Category columns layout (College Code, College Name, Course Name/Code, GM, KKR...)
                is_cat_cols = (
                    len(raw_header) >= 4
                    and any("course" in c for c in header_clean[1:3])
                    and any(cat in c for c in header_clean[3:] for cat in ["gm", "kkr", "hkr", "general"])
                )

                if is_4col_vertical:
                    course_idx = 2
                    rank_idx = 3
                    for row_idx, row in enumerate(extracted[1:], start=1):
                        raw_rows_detected += 1
                        if len(row) < 4:
                            continue
                        raw_code = row[0]
                        raw_college_name = row[1]
                        raw_course = row[course_idx]
                        raw_rank = row[rank_idx]

                        if not raw_code or not raw_rank or not raw_course:
                            continue
                        norm_code = Normalizer.normalize_college_code(raw_code)
                        norm_college_name, orig_college_name = Normalizer.normalize_college_name(raw_college_name or "")
                        if not norm_code:
                            continue

                        clean_rank_str = re.sub(r'[^0-9]', '', str(raw_rank).strip())
                        if not clean_rank_str:
                            continue
                        try:
                            closing_rank = int(clean_rank_str)
                        except ValueError:
                            continue
                        if closing_rank <= 0:
                            continue

                        course_clean = Normalizer.clean_text(raw_course)
                        if "-" in course_clean:
                            parts = course_clean.split("-", 1)
                            b_code = Normalizer.normalize_branch_code(parts[0])
                            b_name, _ = Normalizer.normalize_branch_name(parts[1])
                        else:
                            b_code = Normalizer.normalize_branch_code(course_clean[:4])
                            b_name, _ = Normalizer.normalize_branch_name(course_clean)

                        if not b_code:
                            continue

                        extracted_pages.add(page_idx + 1)
                        if b_code not in discovered_branches:
                            discovered_branches[b_code] = b_name
                        if norm_code not in discovered_colleges_dict and norm_college_name:
                            discovered_colleges_dict[norm_code] = {
                                "code": norm_code,
                                "name": norm_college_name,
                                "original_name": orig_college_name,
                                "location": None
                            }

                        records.append({
                            "college_code": norm_code,
                            "college_name": norm_college_name,
                            "category_code": "GM",
                            "branch_code": b_code,
                            "branch_name": b_name,
                            "academic_year": academic_year,
                            "round_code": round_code,
                            "round_name": round_name,
                            "round_number": round_num,
                            "opening_rank": None,
                            "closing_rank": closing_rank,
                            "page_number": page_idx + 1,
                            "row_identifier": f"p{page_idx+1}_r{row_idx}_{norm_code}_GM_{b_code}"
                        })

                elif is_cat_cols:
                    cat_cols: Dict[int, str] = {}
                    for c_idx in range(3, len(raw_header)):
                        c_name = header_clean[c_idx]
                        if "gm" in c_name or "general" in c_name:
                            cat_cols[c_idx] = "GM"
                        elif "kkr" in c_name or "hkr" in c_name:
                            cat_cols[c_idx] = "KKR"

                    for row_idx, row in enumerate(extracted[1:], start=1):
                        raw_rows_detected += 1
                        if len(row) < 4:
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

                        course_clean = Normalizer.clean_text(raw_course)
                        if "-" in course_clean:
                            parts = course_clean.split("-", 1)
                            b_code = Normalizer.normalize_branch_code(parts[0])
                            b_name, _ = Normalizer.normalize_branch_name(parts[1])
                        else:
                            b_code = Normalizer.normalize_branch_code(course_clean[:4])
                            b_name, _ = Normalizer.normalize_branch_name(course_clean)

                        if not b_code:
                            continue

                        extracted_pages.add(page_idx + 1)
                        if b_code not in discovered_branches:
                            discovered_branches[b_code] = b_name
                        if norm_code not in discovered_colleges_dict and norm_college_name:
                            discovered_colleges_dict[norm_code] = {
                                "code": norm_code,
                                "name": norm_college_name,
                                "original_name": orig_college_name,
                                "location": None
                            }

                        for c_idx, cat in cat_cols.items():
                            if c_idx < len(row) and row[c_idx]:
                                clean_rank_str = re.sub(r'[^0-9]', '', str(row[c_idx]).strip())
                                if clean_rank_str:
                                    try:
                                        closing_rank = int(clean_rank_str)
                                    except ValueError:
                                        continue
                                    if closing_rank > 0:
                                        records.append({
                                            "college_code": norm_code,
                                            "college_name": norm_college_name,
                                            "category_code": cat,
                                            "branch_code": b_code,
                                            "branch_name": b_name,
                                            "academic_year": academic_year,
                                            "round_code": round_code,
                                            "round_name": round_name,
                                            "round_number": round_num,
                                            "opening_rank": None,
                                            "closing_rank": closing_rank,
                                            "page_number": page_idx + 1,
                                            "row_identifier": f"p{page_idx+1}_r{row_idx}_{norm_code}_{cat}_{b_code}"
                                        })

                else:
                    # Format A: Standard Wide Matrix (branches in cols 3+)
                    branch_cols: Dict[int, Tuple[str, str]] = {}
                    for col_idx in range(3, len(raw_header)):
                        col_text = raw_header[col_idx]
                        if not col_text:
                            continue
                        cleaned = " ".join(col_text.split())
                        if "-" in cleaned:
                            parts = cleaned.split("-", 1)
                            b_code = Normalizer.normalize_branch_code(parts[0])
                            b_name, _ = Normalizer.normalize_branch_name(parts[1])
                            if b_code:
                                branch_cols[col_idx] = (b_code, b_name)
                                if b_code not in discovered_branches:
                                    discovered_branches[b_code] = b_name

                    # Parse row records
                    for row_idx, row in enumerate(extracted[1:], start=1):
                        raw_rows_detected += 1
                        if len(row) < 3:
                            continue

                        raw_code = row[0]
                        raw_college_name = row[1]
                        raw_cat = row[2]

                        if not raw_code:
                            continue

                        norm_code = Normalizer.normalize_college_code(raw_code)
                        norm_college_name, orig_college_name = Normalizer.normalize_college_name(raw_college_name or "")
                        norm_cat = Normalizer.normalize_category_code(raw_cat or "GM")

                        if not norm_code:
                            continue

                        extracted_pages.add(page_idx + 1)

                        if norm_code not in discovered_colleges_dict and norm_college_name:
                            discovered_colleges_dict[norm_code] = {
                                "code": norm_code,
                                "name": norm_college_name,
                                "original_name": orig_college_name,
                                "location": None
                            }

                        # Iterate over each branch cell in this row
                        for col_idx, (b_code, b_name) in branch_cols.items():
                            if col_idx >= len(row):
                                continue
                            cell_val = row[col_idx]
                            if not cell_val:
                                continue

                            # Clean rank string
                            clean_rank_str = re.sub(r'[^0-9]', '', str(cell_val).strip())
                            if not clean_rank_str:
                                continue

                            try:
                                closing_rank = int(clean_rank_str)
                            except ValueError:
                                continue

                            # Valid COMEDK rank is positive
                            if closing_rank <= 0:
                                continue

                            records.append({
                                "college_code": norm_code,
                                "college_name": norm_college_name,
                                "category_code": norm_cat,
                                "branch_code": b_code,
                                "branch_name": b_name,
                                "academic_year": academic_year,
                                "round_code": round_code,
                                "round_name": round_name,
                                "round_number": round_num,
                                "opening_rank": None, # COMEDK cutoff matrices publish closing/cutoff rank
                                "closing_rank": closing_rank,
                                "page_number": page_idx + 1,
                                "row_identifier": f"p{page_idx+1}_r{row_idx}_{norm_code}_{norm_cat}_{b_code}"
                            })

        result.records = records
        result.discovered_branches = discovered_branches
        result.discovered_colleges = list(discovered_colleges_dict.values())
        result.row_count = len(records)
        result.status = RecordStatus.PARSED if records else RecordStatus.NEEDS_REVIEW
        result.metadata = {
            "pdf_page_count": len(doc),
            "extracted_pages": sorted(list(extracted_pages)),
            "extracted_pages_count": len(extracted_pages),
            "raw_rows_detected": raw_rows_detected,
            "candidate_records": len(records),
            "discovered_branches_count": len(discovered_branches),
            "discovered_colleges_count": len(discovered_colleges_dict),
            "parser_warnings": [a.get("warning") for a in result.anomalies if "warning" in a]
        }
        return result
