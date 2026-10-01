"""Constants, Enums, and Round Semantics for COMEDK Compass Historical Analytics.

All round definitions, comparability mappings, and analytical enumerations are
strictly deterministic and read-only.
"""

from enum import Enum
from typing import Dict, List, Set, Tuple, Optional


class RankDirection(str, Enum):
    EARLIER_NUMERICALLY = "EARLIER_NUMERICALLY"
    LATER_NUMERICALLY = "LATER_NUMERICALLY"
    UNCHANGED = "UNCHANGED"


class ComparabilityStatus(str, Enum):
    DIRECT = "DIRECT"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


class VolatilityDataQuality(str, Enum):
    INSUFFICIENT = "INSUFFICIENT"  # n = 1 (no variance possible)
    SPARSE = "SPARSE"              # n = 2 (only 1 degree of freedom, captures single interval)
    OBSERVABLE = "OBSERVABLE"      # n >= 3 (multi-year longitudinal trajectory)


class AnomalyType(str, Enum):
    BACKWARD_ROUND_MOVEMENT = "BACKWARD_ROUND_MOVEMENT"
    MISSING_YEARS_SPARSE = "MISSING_YEARS_SPARSE"
    INCOMPARABLE_ROUND_ATTEMPT = "INCOMPARABLE_ROUND_ATTEMPT"
    INVALID_RANK_VALUE = "INVALID_RANK_VALUE"
    MISSING_PROVENANCE = "MISSING_PROVENANCE"


# Canonical Round Codes across academic years
ROUND_MOCK = "MOCK"
ROUND_R1 = "R1"
ROUND_KKR_SPECIAL = "KKR_SPECIAL"
ROUND_R2_PHASE2 = "R2_PHASE2"
ROUND_R3 = "R3"
ROUND_R4 = "R4"
ROUND_CONSOLIDATED_FINAL = "CONSOLIDATED_FINAL"

# Rounds present per academic year in official published data
YEAR_ROUND_REGISTRY: Dict[int, List[str]] = {
    2023: [ROUND_MOCK, ROUND_R1, ROUND_KKR_SPECIAL, ROUND_R2_PHASE2, ROUND_R3, ROUND_CONSOLIDATED_FINAL],
    2024: [ROUND_MOCK, ROUND_R1, ROUND_KKR_SPECIAL, ROUND_R2_PHASE2, ROUND_R3],
    2025: [ROUND_R4],  # Official consolidated final document ("After All Rounds", 637 records)
    2026: [ROUND_MOCK, ROUND_R1, ROUND_KKR_SPECIAL, ROUND_R3, ROUND_R4],
}

# Terminal/Final round per academic year representing terminal admission state
TERMINAL_ROUNDS_BY_YEAR: Dict[int, str] = {
    2023: ROUND_CONSOLIDATED_FINAL,
    2024: ROUND_R3,
    2025: ROUND_R4,
    2026: ROUND_R4,
}

# Within-year valid progression sequences (strictly sequential counselling stages)
WITHIN_YEAR_PROGRESSIONS: Dict[int, List[Tuple[str, str]]] = {
    2023: [
        (ROUND_R1, ROUND_R2_PHASE2),
        (ROUND_R2_PHASE2, ROUND_R3),
        (ROUND_R3, ROUND_CONSOLIDATED_FINAL),
    ],
    2024: [
        (ROUND_R1, ROUND_R2_PHASE2),
        (ROUND_R2_PHASE2, ROUND_R3),
    ],
    2025: [],  # 2025 has only terminal/consolidated data; no within-year intermediate rounds
    2026: [
        (ROUND_R1, ROUND_R3),
        (ROUND_R3, ROUND_R4),
    ],
}

# Standard reference years for 4-year longitudinal analysis
REFERENCE_YEARS: List[int] = [2023, 2024, 2025, 2026]


def get_round_comparability(
    year1: int,
    round1: str,
    year2: int,
    round2: str
) -> ComparabilityStatus:
    """Determine the explicit round comparability between two academic year round observations.

    Rules:
    1. KKR_SPECIAL cannot be compared with any general round (NONE).
    2. R1 compared with R1 across any years is DIRECT.
    3. MOCK compared with MOCK across any years is DIRECT.
    4. KKR_SPECIAL compared with KKR_SPECIAL across any years is DIRECT.
    5. Terminal rounds across years (2023 CONSOLIDATED_FINAL, 2024 R3, 2025 R4, 2026 R4)
       are PARTIAL due to differing counselling architectures.
    6. R2_PHASE2 between 2023 and 2024 is DIRECT (both were 2nd general round).
    7. R3 between 2023 and 2024 is DIRECT (both were terminal general round).
    8. R3 between 2024 and 2026 is PARTIAL (2024 R3 was final; 2026 R3 was intermediate).
    9. R4 between 2025 and 2026 is PARTIAL (2025 R4 was consolidated post-counselling; 2026 R4 was round 4).
    10. Any other cross-round comparison is NONE.
    """
    if round1 == ROUND_KKR_SPECIAL or round2 == ROUND_KKR_SPECIAL:
        if round1 == ROUND_KKR_SPECIAL and round2 == ROUND_KKR_SPECIAL:
            return ComparabilityStatus.DIRECT
        return ComparabilityStatus.NONE

    # Check terminal round match
    is_term1 = (TERMINAL_ROUNDS_BY_YEAR.get(year1) == round1)
    is_term2 = (TERMINAL_ROUNDS_BY_YEAR.get(year2) == round2)
    if is_term1 and is_term2:
        return ComparabilityStatus.PARTIAL

    if round1 == round2:
        if round1 in (ROUND_R1, ROUND_MOCK):
            return ComparabilityStatus.DIRECT
        if round1 == ROUND_R2_PHASE2:
            if {year1, year2} <= {2023, 2024}:
                return ComparabilityStatus.DIRECT
            return ComparabilityStatus.NONE
        if round1 == ROUND_R3:
            if {year1, year2} <= {2023, 2024}:
                return ComparabilityStatus.DIRECT
            return ComparabilityStatus.PARTIAL
        if round1 == ROUND_R4:
            return ComparabilityStatus.PARTIAL

    return ComparabilityStatus.NONE
