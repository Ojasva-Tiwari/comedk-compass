import re
from typing import Tuple, Optional

# Well-known acronyms in Karnataka/COMEDK colleges to preserve in uppercase
PRESERVED_ACRONYMS = {
    "RV", "R.V.", "BMS", "B.M.S.", "PES", "P.E.S.", "MSRIT", "MS", "M.S.",
    "BVB", "BVBCET", "KLE", "K.L.E.", "JSS", "J.S.S.", "BIT", "B.I.T.",
    "BMSIT", "BNMIT", "NIE", "N.I.E.", "NMIT", "NMAMIT", "SMVIT", "S.M.V.I.T.",
    "SJCE", "S.J.C.E.", "SDM", "S.D.M.", "BLDEA", "BLDE", "AIT", "A.I.T.",
    "ACS", "AMC", "MVJ", "ATRIA", "CMR", "CMRIT", "DSCE", "DSATM", "KSIT",
    "KSSEM", "RNSIT", "RNS", "SCT", "TJS", "HKES", "PDA", "AIET", "AJIET",
    "SCEM", "CEC", "SCE", "GSSSIETW", "EWIT", "SVCE", "SKIT", "DBIT",
    "RRCE", "RRIT", "SAMBHRAM", "SEA", "SJCIT", "BGS", "BGSIT", "CIT", "C.I.T.",
    "GMIT", "UBDT", "BIET", "STJIT", "RYMEC", "VDRIT", "KLS", "GIT", "SGBIT",
    "AGMR", "SEC", "VCET", "YIT", "MIT", "MITE", "PESITM", "JNNCE", "KVG",
    "IIIT", "IIT", "NIT", "AI", "ML", "CSE", "ECE", "EEE", "ISE", "IOT",
    "VLSI", "AR", "VR", "IT"
}

class Normalizer:
    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        if not text:
            return ""
        # Replace non-breaking spaces and collapse multiple whitespaces
        cleaned = re.sub(r'[\r\n\t]+', ' ', text)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    @classmethod
    def normalize_college_code(cls, code: str) -> str:
        cleaned = cls.clean_text(code).upper()
        # Remove trailing dots, colons, or dashes
        cleaned = re.sub(r'[^A-Z0-9]', '', cleaned)
        if cleaned in ("COLLEGECODE", "COLLEGE", "CODE", "SLNO", "INSTITUTE"):
            return ""
        return cleaned

    @classmethod
    def normalize_college_name(cls, raw_name: str) -> Tuple[str, str]:
        """
        Returns (normalized_name, original_name).
        Preserves original official name while normalizing formatting & casing.
        """
        original = cls.clean_text(raw_name)
        if not original:
            return "", ""

        # Normalize line-break hyphens
        normalized = re.sub(r'-\s+', '- ', original)
        
        # Smart casing
        words = normalized.split()
        smart_words = []
        for word in words:
            # Check punctuation stripped version for acronyms
            bare = re.sub(r'[^A-Za-z0-9.]', '', word).upper()
            if bare in PRESERVED_ACRONYMS or bare.replace('.', '') in PRESERVED_ACRONYMS:
                smart_words.append(word.upper())
            elif word.lower() in ("of", "and", "&", "in", "for", "at", "the", "on", "to"):
                smart_words.append(word.lower())
            else:
                smart_words.append(word.capitalize())
        
        normalized_name = " ".join(smart_words)
        # Ensure first letter is capitalized
        if normalized_name:
            normalized_name = normalized_name[0].upper() + normalized_name[1:]
        
        return normalized_name, original

    @classmethod
    def normalize_location(cls, location: Optional[str]) -> Optional[str]:
        if not location:
            return None
        cleaned = cls.clean_text(location)
        # City name capitalization
        parts = [p.capitalize() for p in cleaned.split()]
        return " ".join(parts) if parts else None

    @classmethod
    def normalize_branch_code(cls, code: str) -> str:
        cleaned = cls.clean_text(code).upper()
        return re.sub(r'[^A-Z0-9]', '', cleaned)

    @classmethod
    def normalize_branch_name(cls, raw_name: str) -> Tuple[str, str]:
        original = cls.clean_text(raw_name)
        # Fix hyphenation splits like "Communicat- ion" -> "Communication"
        repaired = re.sub(r'([A-Za-z]+)-\s+([a-z]+)', r'\1\2', original)
        repaired = re.sub(r'([A-Za-z]+)-\s+([A-Z][a-z]+)', r'\1-\2', repaired)
        
        # Standardize & / and spacing
        repaired = re.sub(r'\s*&\s*', ' & ', repaired)
        repaired = cls.clean_text(repaired)
        return repaired, original

    @classmethod
    def normalize_category_code(cls, category: str) -> str:
        cleaned = cls.clean_text(category).upper()
        # Common aliases
        if cleaned in ("GENERAL", "GEN", "OPEN", "GM"):
            return "GM"
        if cleaned in ("KKR", "HYDERABAD KARNATAKA", "HKR"):
            return cleaned
        return cleaned

    @classmethod
    def normalize_round(cls, round_raw: str, academic_year: int = 2026) -> Tuple[str, str, int]:
        """
        Maps round strings to (round_code, round_display_name, round_number).
        e.g., 'Round 1' -> ('R1', 'Round 1', 1)
              'Mock' -> ('MOCK', 'Mock Round', 0)
        """
        r_str = cls.clean_text(round_raw).upper()
        if "MOCK" in r_str:
            return "MOCK", "Mock Round", 0
        if "ROUND 1" in r_str or "ROUND-1" in r_str or "R1" in r_str or "ROUND_1" in r_str:
            return "R1", "Round 1", 1
        if "KKR" in r_str or "ROUND 2" in r_str or "ROUND-2" in r_str or "R2" in r_str or "ROUND_2" in r_str:
            return "KKR_SPECIAL", "Round 2 KKR Special Allotment", 2
        if "ROUND 3" in r_str or "ROUND-3" in r_str or "R3" in r_str or "ROUND_3" in r_str:
            return "R3", "Round 3", 3
        if "ROUND 4" in r_str or "ROUND-4" in r_str or "R4" in r_str or "ROUND_4" in r_str:
            return "R4", "Round 4", 4

        # Fallback to sanitized uppercase
        safe_code = re.sub(r'[^A-Z0-9]', '', r_str)
        return safe_code or "UNKNOWN", round_raw, 99
