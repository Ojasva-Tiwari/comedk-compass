import re
from typing import Optional, Tuple
from backend.app.core.enums import DocumentType, ProgramType

class DocumentClassifier:
    """
    Robust classifier for COMEDK document types, counselling rounds, and program types.
    Utilizes URL patterns, enclosing HTML context, link text, and header keywords.
    """

    @classmethod
    def classify(cls, text_or_url: str) -> str:
        s = text_or_url.lower()

        # 1. Cutoff detection
        if any(kw in s for kw in ["cut-off", "cutoff", "cut_off", "cut off"]):
            return DocumentType.CUTOFF_PDF.value

        # 2. Vacant seats detection (must precede general seat matrix)
        if "vacant" in s or "vacancy" in s:
            return DocumentType.VACANT_SEATS_PDF.value

        # 3. Seat matrix
        if "seat" in s and ("matrix" in s or "allocation" in s or "allotment" in s or "available" in s):
            return DocumentType.SEAT_MATRIX_PDF.value

        # 4. Fee structure
        if "fee" in s or "fees" in s or "tuition" in s:
            return DocumentType.FEE_STRUCTURE_PDF.value

        # 5. Course / branch catalogue
        if "branches offered" in s or "branch code" in s or "courses offered" in s:
            return DocumentType.BRANCHES_OFFERED_PDF.value

        # 6. Notifications, process guides & rules
        if any(kw in s for kw in ["notification", "guideline", "process", "instruction", "procedure", "brochure", "information bulletin"]):
            return DocumentType.NOTIFICATION_PDF.value

        # 7. HTML directories
        if "member-institutions" in s:
            return DocumentType.MEMBER_INSTITUTIONS_HTML.value
        if "be-colleges" in s:
            return DocumentType.BE_COLLEGES_HTML.value
        if "counselling-document" in s:
            return DocumentType.COUNSELLING_PORTAL_HTML.value

        return DocumentType.UNKNOWN.value

    @classmethod
    def extract_counselling_round(cls, text_or_url: str) -> Optional[str]:
        s = text_or_url.lower().replace("_", " ").replace("-", " ")
        if "mock" in s:
            return "MOCK"

        # Check Phase 1 vs Phase 2 first
        # In COMEDK history, Round 2 Phase 1 is KKR/Article 371J regional quota special allotment
        if "kkr special" in s or "kkr_special" in s or "r2 kkr" in s or "phase 1" in s or "phase1" in s:
            return "KKR_SPECIAL"
        # Round 2 Phase 2 is General Merit Round 2 allotment
        if "phase 2" in s or "phase2" in s or "r2 phase2" in s or "r2_phase2" in s:
            return "R2_PHASE2"

        # Match Round 1, R1, Round-1, Round_1
        if re.search(r'\b(round\s*1|r\s*1)\b', s):
            return "R1"

        # Match Round 3, R3, Round-3, Round_3
        if re.search(r'\b(round\s*3|r\s*3)\b', s):
            return "R3"

        # Match Round 4, R4, Round-4, Round_4
        if re.search(r'\b(round\s*4|r\s*4)\b', s):
            return "R4"

        # Match After All Rounds / Consolidated
        if "after all rounds" in s or "all rounds" in s or "consolidated" in s:
            year = cls.extract_academic_year(text_or_url, default=2026)
            if year == 2025:
                return "R4"
            return "CONSOLIDATED_FINAL"

        # 2026 fallback where Round 2 specifically represents the KKR special allotment
        if re.search(r'\b(round\s*2|r\s*2)\b', s) or "kkr" in s:
            return "KKR_SPECIAL"

        return None

    @classmethod
    def extract_academic_year(cls, text_or_url: str, default: int = 2026) -> int:
        s = text_or_url.lower()
        # Prefer matching leading year like "2025 - Engineering"
        match = re.search(r'\b(202[0-9])\b', s)
        if match:
            return int(match.group(1))
        return default

    @classmethod
    def classify_with_round(cls, text_or_url: str) -> Tuple[str, Optional[str]]:
        doc_type = cls.classify(text_or_url)
        round_code = cls.extract_counselling_round(text_or_url)
        return doc_type, round_code

    @classmethod
    def extract_program_type(cls, text_or_url: str) -> str:
        s = text_or_url.lower()
        if any(kw in s for kw in ["architecture", "b.arch", "barch", "b arch", "nata"]):
            return ProgramType.ARCHITECTURE.value
        return ProgramType.ENGINEERING.value

