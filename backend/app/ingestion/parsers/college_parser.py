import re
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from backend.app.ingestion.parsers.base import BaseParser, ParseResult
from backend.app.ingestion.normalizer import Normalizer
from backend.app.core.enums import RecordStatus, InstitutionType

class CollegeParser(BaseParser):
    """
    Parses HTML content from COMEDK member-institutions and be-colleges pages.
    Classifies institutions by institution_type based on official source table context.
    """
    def parse(self, content: bytes, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        result = ParseResult()
        try:
            html = content.decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            result.status = RecordStatus.REJECTED
            result.errors.append({"error": f"Failed to decode or parse HTML: {e}"})
            return result

        tables = soup.find_all("table")
        if not tables:
            result.status = RecordStatus.NEEDS_REVIEW
            result.anomalies.append({"warning": "No tables found in page content"})
            return result

        colleges_found_map: Dict[str, Dict[str, Any]] = {}

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            header_row = rows[0]
            headers = [Normalizer.clean_text(th.get_text()).upper() for th in header_row.find_all(["th", "td"])]
            header_text_combined = " ".join(headers)

            # Determine institution type from official table context
            table_inst_type = InstitutionType.ENGINEERING.value
            if "ARCHITECTURE" in header_text_combined:
                table_inst_type = InstitutionType.ARCHITECTURE.value
            elif "DENTAL" in header_text_combined:
                table_inst_type = InstitutionType.DENTAL.value
            elif "MEDICAL" in header_text_combined:
                table_inst_type = InstitutionType.MEDICAL.value
            elif "ENGINEERING" in header_text_combined:
                table_inst_type = InstitutionType.ENGINEERING.value
            else:
                prev_head = table.find_previous(["div", "h1", "h2", "h3", "h4", "p"])
                if prev_head:
                    p_text = prev_head.get_text().upper()
                    if "ARCHITECTURE" in p_text:
                        table_inst_type = InstitutionType.ARCHITECTURE.value
                    elif "DENTAL" in p_text:
                        table_inst_type = InstitutionType.DENTAL.value
                    elif "MEDICAL" in p_text:
                        table_inst_type = InstitutionType.MEDICAL.value
                    elif "ENGINEERING" in p_text:
                        table_inst_type = InstitutionType.ENGINEERING.value

            # Identify column positions
            code_col = -1
            name_col = -1
            loc_col = -1

            for idx, h in enumerate(headers):
                if "CODE" in h:
                    code_col = idx
                elif "COLLEGE" in h or "INSTITUT" in h:
                    name_col = idx
                elif "LOCATION" in h or "CITY" in h or "DISTRICT" in h:
                    loc_col = idx

            # Fallback for standard 3-column table
            if code_col == -1 and len(headers) >= 3:
                code_col, name_col, loc_col = 0, 1, 2

            if code_col == -1 or name_col == -1:
                continue

            # Process data rows
            for row in rows[1:]:
                cols = row.find_all(["td", "th"])
                if len(cols) <= max(code_col, name_col):
                    continue

                raw_code = cols[code_col].get_text(strip=True)
                raw_name = cols[name_col].get_text(strip=True)
                raw_loc = cols[loc_col].get_text(strip=True) if loc_col != -1 and len(cols) > loc_col else ""

                if not raw_code or not raw_name:
                    continue

                norm_code = Normalizer.normalize_college_code(raw_code)
                norm_name, orig_name = Normalizer.normalize_college_name(raw_name)
                norm_loc = Normalizer.normalize_location(raw_loc)

                if not norm_code or not norm_name:
                    continue

                if norm_code in colleges_found_map:
                    # If already present as ARCHITECTURE, promote to ENGINEERING if listed in Engineering
                    if table_inst_type == InstitutionType.ENGINEERING.value:
                        colleges_found_map[norm_code]["institution_type"] = InstitutionType.ENGINEERING.value
                else:
                    colleges_found_map[norm_code] = {
                        "code": norm_code,
                        "name": norm_name,
                        "original_name": orig_name,
                        "location": norm_loc,
                        "institution_type": table_inst_type,
                    }

        discovered_list = list(colleges_found_map.values())
        result.discovered_colleges = discovered_list
        result.row_count = len(discovered_list)
        result.status = RecordStatus.PARSED if discovered_list else RecordStatus.NEEDS_REVIEW
        return result
