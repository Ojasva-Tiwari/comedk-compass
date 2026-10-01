"""Historical Analytics Service for COMEDK Compass.

Provides strictly read-only analytical aggregations and empirical metrics
over official published COMEDK cutoff data (2023-2026).

Zero mutations, zero predictions, zero arbitrary thresholds.
"""

import math
import statistics
import uuid
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.enums import RecordStatus, ProgramType
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.category import Category
from backend.app.models.round import CounsellingRound
from backend.app.analytics.constants import (
    RankDirection,
    ComparabilityStatus,
    VolatilityDataQuality,
    AnomalyType,
    ROUND_MOCK,
    ROUND_R1,
    ROUND_KKR_SPECIAL,
    ROUND_R2_PHASE2,
    ROUND_R3,
    ROUND_R4,
    ROUND_CONSOLIDATED_FINAL,
    YEAR_ROUND_REGISTRY,
    TERMINAL_ROUNDS_BY_YEAR,
    WITHIN_YEAR_PROGRESSIONS,
    REFERENCE_YEARS,
    get_round_comparability,
)
from backend.app.analytics.schemas import (
    CoverageSummary,
    ExcludedRecordDetail,
    YearMovementItem,
    YearMovementAggregate,
    VolatilityMetric,
    VolatilitySummary,
    RoundProgressionMetric,
    RecencyComparison,
    SparsityMetadata,
    HistoricalAnomaly,
    AnalyticsReport,
)


def _safe_mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _safe_median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return float(statistics.median(values))


def _sample_stddev(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    return float(statistics.stdev(values))


def _median_absolute_deviation(values: List[float]) -> Optional[float]:
    if not values or len(values) < 2:
        return None
    med = statistics.median(values)
    abs_deviations = [abs(x - med) for x in values]
    return float(statistics.median(abs_deviations))


def _coefficient_of_variation(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    mean_val = _safe_mean(values)
    if mean_val is None or mean_val == 0.0:
        return None
    std = _sample_stddev(values)
    if std is None:
        return None
    return std / mean_val


class HistoricalAnalyticsService:
    """Read-only service for historical cutoff analytics across 2023-2026."""

    def __init__(self, db: Session):
        self.db = db

    def get_canonical_records(
        self,
        academic_year: Optional[int] = None,
        program_type: Optional[str] = None,
        category_code: Optional[str] = None,
        round_code: Optional[str] = None,
        status: str = RecordStatus.PUBLISHED.value,
        college_id: Optional[uuid.UUID] = None,
        branch_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch cutoff records normalized to canonical college and branch grain.

        When college_id and/or branch_id are supplied, filtering is applied directly
        at the database SQL layer for optimal query execution and bounded memory usage.
        """
        # Load canonical branch map: branch_id -> (canonical_id, canonical_code, canonical_name)
        branches = self.db.query(Branch).all()
        branch_map = {}
        for b in branches:
            if not b.is_canonical and b.canonical_branch_id:
                canonical = next((x for x in branches if x.id == b.canonical_branch_id), b)
                branch_map[b.id] = (canonical.id, canonical.code, canonical.name, canonical.program_type)
            else:
                branch_map[b.id] = (b.id, b.code, b.name, b.program_type)

        query = (
            self.db.query(
                CutoffRecord.id,
                CutoffRecord.academic_year,
                CutoffRecord.closing_rank,
                CutoffRecord.opening_rank,
                CutoffRecord.status,
                CutoffRecord.source_version_id,
                College.id.label("college_id"),
                College.code.label("college_code"),
                College.name.label("college_name"),
                College.institution_type,
                CutoffRecord.branch_id,
                Category.code.label("category_code"),
                CounsellingRound.code.label("round_code"),
                CounsellingRound.round_number,
                CounsellingRound.is_general_round,
            )
            .join(College, CutoffRecord.college_id == College.id)
            .join(Category, CutoffRecord.category_id == Category.id)
            .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
        )

        if status is not None:
            query = query.filter(CutoffRecord.status == status)
        if academic_year is not None:
            query = query.filter(CutoffRecord.academic_year == academic_year)
        if category_code is not None:
            query = query.filter(Category.code == category_code)
        if round_code is not None:
            query = query.filter(CounsellingRound.code == round_code)
        if college_id is not None:
            query = query.filter(CutoffRecord.college_id == college_id)
        if branch_id is not None:
            # Map canonical and alias branch IDs associated with this branch
            target_branch_ids = [
                b_raw_id for b_raw_id, info in branch_map.items()
                if info[0] == branch_id or b_raw_id == branch_id
            ]
            if target_branch_ids:
                query = query.filter(CutoffRecord.branch_id.in_(target_branch_ids))
            else:
                query = query.filter(CutoffRecord.branch_id == branch_id)

        raw_rows = query.all()


        normalized_records = []
        for r in raw_rows:
            canon_id, canon_code, canon_name, b_prog_type = branch_map.get(
                r.branch_id, (r.branch_id, "UNKNOWN", "UNKNOWN", ProgramType.ENGINEERING.value)
            )

            if program_type is not None and b_prog_type != program_type:
                continue

            normalized_records.append({
                "record_id": r.id,
                "academic_year": r.academic_year,
                "closing_rank": r.closing_rank,
                "opening_rank": r.opening_rank,
                "college_id": r.college_id,
                "college_code": r.college_code,
                "college_name": r.college_name,
                "branch_id": canon_id,
                "branch_code": canon_code,
                "branch_name": canon_name,
                "program_type": b_prog_type,
                "category": r.category_code,
                "round_code": r.round_code,
                "round_number": r.round_number,
                "is_general_round": r.is_general_round,
                "source_version_id": r.source_version_id,
                "status": r.status,
            })

        return normalized_records

    def get_coverage_summary(self) -> CoverageSummary:
        """Calculate complete historical coverage, reconciliation, and observation depth across 2023-2026."""
        total_cutoff_count = self.db.query(CutoffRecord).count()
        published_records = self.get_canonical_records(status=RecordStatus.PUBLISHED.value)

        total_by_year = dict(
            self.db.query(CutoffRecord.academic_year, func.count(CutoffRecord.id))
            .group_by(CutoffRecord.academic_year)
            .all()
        )

        years_set = set(total_by_year.keys())
        records_per_year = defaultdict(int)
        records_per_round = defaultdict(lambda: defaultdict(int))
        records_per_category = defaultdict(int)
        records_per_program_type = defaultdict(int)
        colleges_per_year = defaultdict(set)
        branches_per_year = defaultdict(set)

        # Track unique combinations across years: key -> set of years observed
        combo_years = defaultdict(set)
        combo_program = {}

        for r in published_records:
            yr = r["academic_year"]
            records_per_year[yr] += 1
            records_per_round[yr][r["round_code"]] += 1
            records_per_category[r["category"]] += 1
            records_per_program_type[r["program_type"]] += 1
            colleges_per_year[yr].add(r["college_id"])
            branches_per_year[yr].add(r["branch_id"])

            combo_key = (r["college_id"], r["branch_id"], r["program_type"], r["category"])
            combo_years[combo_key].add(yr)
            combo_program[combo_key] = r["program_type"]

        # Observation depth
        observation_depth_counts = defaultdict(int)
        observation_depth_by_program = defaultdict(lambda: defaultdict(int))
        years_observed_patterns = defaultdict(int)

        for combo_key, yrs in combo_years.items():
            depth = len(yrs)
            prog = combo_program[combo_key]
            observation_depth_counts[depth] += 1
            observation_depth_by_program[prog][depth] += 1

            pattern_str = ",".join(str(y) for y in sorted(yrs))
            years_observed_patterns[pattern_str] += 1

        # Query superseded/non-published records with full provenance
        superseded_rows = (
            self.db.query(
                CutoffRecord.id,
                CutoffRecord.academic_year,
                CutoffRecord.closing_rank,
                CutoffRecord.status,
                CutoffRecord.source_version_id,
                College.code.label("college_code"),
                College.name.label("college_name"),
                Branch.code.label("branch_code"),
                Branch.program_type,
                Category.code.label("category_code"),
                CounsellingRound.code.label("round_code"),
            )
            .join(College, CutoffRecord.college_id == College.id)
            .join(Branch, CutoffRecord.branch_id == Branch.id)
            .join(Category, CutoffRecord.category_id == Category.id)
            .join(CounsellingRound, CutoffRecord.round_id == CounsellingRound.id)
            .filter(CutoffRecord.status != RecordStatus.PUBLISHED.value)
            .all()
        )

        excluded_details = []
        superseded_per_year = defaultdict(int)
        for s in superseded_rows:
            superseded_per_year[s.academic_year] += 1
            excluded_details.append(
                ExcludedRecordDetail(
                    cutoff_id=s.id,
                    academic_year=s.academic_year,
                    college_code=s.college_code,
                    college_name=s.college_name,
                    branch_code=s.branch_code,
                    program_type=s.program_type,
                    category=s.category_code,
                    round_code=s.round_code,
                    status=s.status,
                    closing_rank=s.closing_rank,
                    source_version_id=s.source_version_id,
                    exclusion_reason=(
                        "Historical record status is SUPERSEDED (non-published). Preserved in database "
                        "for source provenance and immutability."
                    ),
                )
            )

        return CoverageSummary(
            years_available=sorted(list(years_set)),
            total_records=total_cutoff_count,
            published_records=len(published_records),
            superseded_records=len(superseded_rows),
            records_per_year=dict(sorted(records_per_year.items())),
            total_records_per_year=dict(sorted(total_by_year.items())),
            superseded_records_per_year=dict(sorted(superseded_per_year.items())),
            records_per_round={y: dict(sorted(r.items())) for y, r in sorted(records_per_round.items())},
            records_per_category=dict(sorted(records_per_category.items())),
            records_per_program_type=dict(sorted(records_per_program_type.items())),
            colleges_per_year={y: len(c) for y, c in sorted(colleges_per_year.items())},
            branches_per_year={y: len(b) for y, b in sorted(branches_per_year.items())},
            observation_depth_counts=dict(sorted(observation_depth_counts.items())),
            observation_depth_by_program={p: dict(sorted(d.items())) for p, d in sorted(observation_depth_by_program.items())},
            years_observed_patterns=dict(sorted(years_observed_patterns.items(), key=lambda x: -x[1])),
            excluded_records=excluded_details,
        )

    def get_yoy_movement(
        self,
        from_year: int,
        to_year: int,
        round_scope: str = "R1",
        program_type: str = ProgramType.ENGINEERING.value,
        category: str = "GM",
    ) -> Tuple[List[YearMovementItem], Optional[YearMovementAggregate]]:
        """Calculate year-over-year cutoff movement between two academic years for a round scope."""
        if from_year >= to_year:
            raise ValueError(f"from_year ({from_year}) must be strictly less than to_year ({to_year})")

        # Resolve round codes per year
        if round_scope in ("TERMINAL", "TERMINAL_ALLOTMENT", "STRICT_TERMINAL"):
            round1 = TERMINAL_ROUNDS_BY_YEAR.get(from_year)
            round2 = TERMINAL_ROUNDS_BY_YEAR.get(to_year)
        else:
            round1 = round_scope
            round2 = round_scope

        if not round1 or not round2:
            return [], None

        comparability = get_round_comparability(from_year, round1, to_year, round2)
        if comparability == ComparabilityStatus.NONE:
            return [], None

        # Fetch records
        rec1 = self.get_canonical_records(
            academic_year=from_year,
            program_type=program_type,
            category_code=category,
            round_code=round1,
        )
        rec2 = self.get_canonical_records(
            academic_year=to_year,
            program_type=program_type,
            category_code=category,
            round_code=round2,
        )

        map1 = {(r["college_id"], r["branch_id"]): r for r in rec1}
        map2 = {(r["college_id"], r["branch_id"]): r for r in rec2}

        common_keys = sorted(set(map1.keys()) & set(map2.keys()))
        transition_str = f"{from_year}->{to_year}"

        items: List[YearMovementItem] = []
        abs_moves: List[float] = []
        rel_moves: List[float] = []
        earlier_count = 0
        later_count = 0
        unchanged_count = 0

        for k in common_keys:
            r1 = map1[k]
            r2 = map2[k]

            c1 = r1["closing_rank"]
            c2 = r2["closing_rank"]

            abs_diff = c2 - c1
            rel_diff = (c2 - c1) / float(c1) if c1 > 0 else 0.0

            if abs_diff < 0:
                direction = RankDirection.EARLIER_NUMERICALLY
                earlier_count += 1
            elif abs_diff > 0:
                direction = RankDirection.LATER_NUMERICALLY
                later_count += 1
            else:
                direction = RankDirection.UNCHANGED
                unchanged_count += 1

            abs_moves.append(abs_diff)
            rel_moves.append(rel_diff)

            items.append(
                YearMovementItem(
                    college_id=r1["college_id"],
                    college_code=r1["college_code"],
                    college_name=r1["college_name"],
                    branch_id=r1["branch_id"],
                    branch_code=r1["branch_code"],
                    branch_name=r1["branch_name"],
                    program_type=program_type,
                    category=category,
                    previous_year=from_year,
                    previous_round=round1,
                    previous_closing_rank=c1,
                    current_year=to_year,
                    current_round=round2,
                    current_closing_rank=c2,
                    absolute_movement=abs_diff,
                    relative_movement=rel_diff,
                    direction=direction,
                    comparability=comparability,
                    transition=transition_str,
                )
            )

        if not items:
            return [], None

        aggregate = YearMovementAggregate(
            transition=transition_str,
            from_round=round1,
            to_round=round2,
            program_type=program_type,
            category=category,
            comparability=comparability,
            matched_pairs=len(items),
            median_absolute_movement=_safe_median(abs_moves) or 0.0,
            mean_absolute_movement=_safe_mean(abs_moves) or 0.0,
            median_relative_movement=_safe_median(rel_moves) or 0.0,
            mean_relative_movement=_safe_mean(rel_moves) or 0.0,
            earlier_numerically_count=earlier_count,
            later_numerically_count=later_count,
            unchanged_count=unchanged_count,
        )

        return items, aggregate

    def get_volatility_metrics(
        self,
        round_scope: str = "TERMINAL",
        program_type: str = ProgramType.ENGINEERING.value,
        category: str = "GM",
        min_n: int = 1,
    ) -> List[VolatilityMetric]:
        """Calculate historical cutoff volatility across observed years for canonical combinations.

        Round scope definitions:
        - "TERMINAL" (default): Terminal admission state per branch (with fallback to last allotment
          round, e.g. R3 in 2026 or R3 in 2023, when a branch exhausted seats prior to R4).
          Evaluates all 527 combinations (n=2: 162, n=3: 133, n=4: 232).
        - "STRICT_TERMINAL": Strict nominal document only without fallback (CONSOLIDATED_FINAL, R3, R4, R4).
          Evaluates 461 combinations (n=2: 150, n=3: 95, n=4: 216).
        - Specific round code (e.g. "R1", "MOCK", "KKR_SPECIAL").
        """
        grouped = defaultdict(dict)
        meta_map = {}

        if round_scope in ("TERMINAL", "TERMINAL_ALLOTMENT"):
            # Terminal Admission State / Final Allotment (validated audit grain):
            # 2023: CONSOLIDATED_FINAL or fallback to R3
            # 2024: R3
            # 2025: R4
            # 2026: R4 or fallback to R3
            all_records = self.get_canonical_records(
                program_type=program_type,
                category_code=category,
            )
            by_year_rounds = defaultdict(lambda: defaultdict(dict))
            for r in all_records:
                key = (r["college_id"], r["branch_id"])
                by_year_rounds[key][r["academic_year"]][r["round_code"]] = r["closing_rank"]
                meta_map[key] = (r["college_code"], r["college_name"], r["branch_code"], r["branch_name"])

            for key, yr_map in by_year_rounds.items():
                if 2023 in yr_map:
                    c23 = yr_map[2023].get(ROUND_CONSOLIDATED_FINAL) or yr_map[2023].get(ROUND_R3)
                    if c23 is not None:
                        grouped[key][2023] = c23
                if 2024 in yr_map and ROUND_R3 in yr_map[2024]:
                    grouped[key][2024] = yr_map[2024][ROUND_R3]
                if 2025 in yr_map and ROUND_R4 in yr_map[2025]:
                    grouped[key][2025] = yr_map[2025][ROUND_R4]
                if 2026 in yr_map:
                    c26 = yr_map[2026].get(ROUND_R4) or yr_map[2026].get(ROUND_R3)
                    if c26 is not None:
                        grouped[key][2026] = c26

        elif round_scope == "STRICT_TERMINAL":
            # Strict nominal final round document only without fallback
            year_rounds = {
                2023: ROUND_CONSOLIDATED_FINAL,
                2024: ROUND_R3,
                2025: ROUND_R4,
                2026: ROUND_R4,
            }
            all_records = []
            for yr, rcode in year_rounds.items():
                recs = self.get_canonical_records(
                    academic_year=yr,
                    program_type=program_type,
                    category_code=category,
                    round_code=rcode,
                )
                all_records.extend(recs)
            for r in all_records:
                key = (r["college_id"], r["branch_id"])
                grouped[key][r["academic_year"]] = r["closing_rank"]
                meta_map[key] = (r["college_code"], r["college_name"], r["branch_code"], r["branch_name"])

        else:
            # Single round code (e.g. R1, MOCK)
            year_rounds = {
                yr: round_scope for yr in REFERENCE_YEARS if round_scope in YEAR_ROUND_REGISTRY.get(yr, [])
            }
            all_records = []
            for yr, rcode in year_rounds.items():
                recs = self.get_canonical_records(
                    academic_year=yr,
                    program_type=program_type,
                    category_code=category,
                    round_code=rcode,
                )
                all_records.extend(recs)
            for r in all_records:
                key = (r["college_id"], r["branch_id"])
                grouped[key][r["academic_year"]] = r["closing_rank"]
                meta_map[key] = (r["college_code"], r["college_name"], r["branch_code"], r["branch_name"])

        results: List[VolatilityMetric] = []

        for key, yr_ranks in grouped.items():
            obs_count = len(yr_ranks)
            if obs_count < min_n:
                continue

            sorted_years = sorted(yr_ranks.keys())
            ranks = [float(yr_ranks[y]) for y in sorted_years]
            missing_years = sorted(list(set(REFERENCE_YEARS) - set(sorted_years)))

            min_rank = int(min(ranks))
            max_rank = int(max(ranks))
            rank_range = max_rank - min_rank

            # Sequential movements
            seq_abs = []
            seq_rel = []
            for i in range(len(ranks) - 1):
                diff = int(ranks[i + 1] - ranks[i])
                r_diff = diff / ranks[i] if ranks[i] > 0 else 0.0
                seq_abs.append(diff)
                seq_rel.append(r_diff)

            col_id, br_id = key
            col_code, col_name, br_code, br_name = meta_map[key]

            if obs_count == 1:
                results.append(
                    VolatilityMetric(
                        college_id=col_id,
                        college_code=col_code,
                        college_name=col_name,
                        branch_id=br_id,
                        branch_code=br_code,
                        branch_name=br_name,
                        program_type=program_type,
                        category=category,
                        round_scope=round_scope,
                        observation_count=obs_count,
                        years_observed=sorted_years,
                        missing_years=missing_years,
                        mean=ranks[0],
                        median=ranks[0],
                        standard_deviation=None,
                        coefficient_of_variation=None,
                        mad=None,
                        min_rank=min_rank,
                        max_rank=max_rank,
                        rank_range=rank_range,
                        sequential_absolute_movements=[],
                        sequential_relative_movements=[],
                        volatility_data_quality=VolatilityDataQuality.INSUFFICIENT,
                    )
                )
            else:
                mean_val = _safe_mean(ranks)
                median_val = _safe_median(ranks)
                std_val = _sample_stddev(ranks)
                cv_val = _coefficient_of_variation(ranks)
                mad_val = _median_absolute_deviation(ranks)
                quality = (
                    VolatilityDataQuality.SPARSE
                    if obs_count == 2
                    else VolatilityDataQuality.OBSERVABLE
                )

                results.append(
                    VolatilityMetric(
                        college_id=col_id,
                        college_code=col_code,
                        college_name=col_name,
                        branch_id=br_id,
                        branch_code=br_code,
                        branch_name=br_name,
                        program_type=program_type,
                        category=category,
                        round_scope=round_scope,
                        observation_count=obs_count,
                        years_observed=sorted_years,
                        missing_years=missing_years,
                        mean=mean_val,
                        median=median_val,
                        standard_deviation=std_val,
                        coefficient_of_variation=cv_val,
                        mad=mad_val,
                        min_rank=min_rank,
                        max_rank=max_rank,
                        rank_range=rank_range,
                        sequential_absolute_movements=seq_abs,
                        sequential_relative_movements=seq_rel,
                        volatility_data_quality=quality,
                    )
                )

        return results

    def get_volatility_summary_by_n(
        self,
        round_scope: str = "TERMINAL",
        program_type: str = ProgramType.ENGINEERING.value,
        category: str = "GM",
    ) -> Dict[int, VolatilitySummary]:
        """Aggregate empirical volatility statistics stratified strictly by observation depth n."""
        metrics = self.get_volatility_metrics(
            round_scope=round_scope,
            program_type=program_type,
            category=category,
            min_n=2,
        )

        by_n = defaultdict(list)
        for m in metrics:
            by_n[m.observation_count].append(m)

        summaries = {}
        for n in sorted(by_n.keys()):
            items = by_n[n]
            cvs = [m.coefficient_of_variation for m in items if m.coefficient_of_variation is not None]
            all_abs = []
            all_rel = []
            for m in items:
                all_abs.extend([abs(x) for x in m.sequential_absolute_movements])
                all_rel.extend([abs(x) for x in m.sequential_relative_movements])

            quality = VolatilityDataQuality.SPARSE if n == 2 else VolatilityDataQuality.OBSERVABLE

            summaries[n] = VolatilitySummary(
                observation_count=n,
                combination_count=len(items),
                median_cv=_safe_median(cvs),
                mean_cv=_safe_mean(cvs),
                min_cv=min(cvs) if cvs else None,
                max_cv=max(cvs) if cvs else None,
                median_absolute_movement=_safe_median(all_abs),
                median_relative_movement=_safe_median(all_rel),
                volatility_data_quality=quality,
            )

        return summaries

    def get_round_progression(
        self,
        academic_year: Optional[int] = None,
        program_type: str = ProgramType.ENGINEERING.value,
        category: str = "GM",
    ) -> List[RoundProgressionMetric]:
        """Calculate within-year round progression statistics for sequential counselling rounds."""
        years_to_check = [academic_year] if academic_year else [2023, 2024, 2026]
        progressions: List[RoundProgressionMetric] = []

        for yr in years_to_check:
            pairs = WITHIN_YEAR_PROGRESSIONS.get(yr, [])
            for r_from, r_to in pairs:
                rec_from = self.get_canonical_records(
                    academic_year=yr,
                    program_type=program_type,
                    category_code=category,
                    round_code=r_from,
                )
                rec_to = self.get_canonical_records(
                    academic_year=yr,
                    program_type=program_type,
                    category_code=category,
                    round_code=r_to,
                )

                map_from = {(r["college_id"], r["branch_id"]): r["closing_rank"] for r in rec_from}
                map_to = {(r["college_id"], r["branch_id"]): r["closing_rank"] for r in rec_to}

                common_keys = sorted(set(map_from.keys()) & set(map_to.keys()))
                if not common_keys:
                    continue

                abs_moves = []
                rel_moves = []
                earlier_count = 0
                later_count = 0
                unchanged_count = 0

                for k in common_keys:
                    c_from = map_from[k]
                    c_to = map_to[k]
                    diff = c_to - c_from
                    r_diff = diff / float(c_from) if c_from > 0 else 0.0

                    if diff < 0:
                        earlier_count += 1
                    elif diff > 0:
                        later_count += 1
                    else:
                        unchanged_count += 1

                    abs_moves.append(diff)
                    rel_moves.append(r_diff)

                progressions.append(
                    RoundProgressionMetric(
                        academic_year=yr,
                        from_round=r_from,
                        to_round=r_to,
                        program_type=program_type,
                        category=category,
                        matched_pairs=len(common_keys),
                        median_absolute_movement=_safe_median(abs_moves) or 0.0,
                        mean_absolute_movement=_safe_mean(abs_moves) or 0.0,
                        median_relative_movement=_safe_median(rel_moves) or 0.0,
                        mean_relative_movement=_safe_mean(rel_moves) or 0.0,
                        earlier_numerically_count=earlier_count,
                        later_numerically_count=later_count,
                        unchanged_count=unchanged_count,
                    )
                )

        return progressions

    def get_recency_evidence(
        self,
        anchor_year: int = 2026,
        round_scope: str = "R1",
        program_type: str = ProgramType.ENGINEERING.value,
        category: str = "GM",
    ) -> List[RecencyComparison]:
        """Empirically test whether recent historical observations are closer to the anchor year."""
        if round_scope == "R1":
            recent_year = 2024
            older_year = 2023
            r_anchor = ROUND_R1
            r_recent = ROUND_R1
            r_older = ROUND_R1
        elif round_scope in ("TERMINAL", "TERMINAL_ALLOTMENT", "STRICT_TERMINAL"):
            recent_year = 2025
            older_year = 2023
            r_anchor = TERMINAL_ROUNDS_BY_YEAR[anchor_year]
            r_recent = TERMINAL_ROUNDS_BY_YEAR[recent_year]
            r_older = TERMINAL_ROUNDS_BY_YEAR[older_year]
        else:
            return []

        rec_anchor = self.get_canonical_records(academic_year=anchor_year, program_type=program_type, category_code=category, round_code=r_anchor)
        rec_recent = self.get_canonical_records(academic_year=recent_year, program_type=program_type, category_code=category, round_code=r_recent)
        rec_older = self.get_canonical_records(academic_year=older_year, program_type=program_type, category_code=category, round_code=r_older)

        map_anchor = {(r["college_id"], r["branch_id"]): r["closing_rank"] for r in rec_anchor}
        map_recent = {(r["college_id"], r["branch_id"]): r["closing_rank"] for r in rec_recent}
        map_older = {(r["college_id"], r["branch_id"]): r["closing_rank"] for r in rec_older}

        common_keys = sorted(set(map_anchor.keys()) & set(map_recent.keys()) & set(map_older.keys()))
        if not common_keys:
            return []

        recent_closer = 0
        older_closer = 0
        equal_count = 0

        recent_abs_dists = []
        older_abs_dists = []
        recent_rel_dists = []
        older_rel_dists = []

        for k in common_keys:
            c_anchor = map_anchor[k]
            c_recent = map_recent[k]
            c_older = map_older[k]

            dist_recent = abs(c_anchor - c_recent)
            dist_older = abs(c_anchor - c_older)

            recent_abs_dists.append(dist_recent)
            older_abs_dists.append(dist_older)

            recent_rel_dists.append(dist_recent / float(c_recent) if c_recent > 0 else 0.0)
            older_rel_dists.append(dist_older / float(c_older) if c_older > 0 else 0.0)

            if dist_recent < dist_older:
                recent_closer += 1
            elif dist_older < dist_recent:
                older_closer += 1
            else:
                equal_count += 1

        pct_recent_closer = (recent_closer / len(common_keys)) * 100.0 if common_keys else 0.0

        return [
            RecencyComparison(
                anchor_year=anchor_year,
                comparison_round=round_scope,
                program_type=program_type,
                category=category,
                evaluated_triples=len(common_keys),
                recent_year=recent_year,
                older_year=older_year,
                recent_closer_count=recent_closer,
                older_closer_count=older_closer,
                equal_distance_count=equal_count,
                recent_closer_percentage=pct_recent_closer,
                recent_median_absolute_distance=_safe_median(recent_abs_dists) or 0.0,
                older_median_absolute_distance=_safe_median(older_abs_dists) or 0.0,
                recent_median_relative_distance=_safe_median(recent_rel_dists) or 0.0,
                older_median_relative_distance=_safe_median(older_rel_dists) or 0.0,
            )
        ]

    def get_sparsity_metadata(
        self,
        program_type: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[SparsityMetadata]:
        """Evaluate observation depth and longitudinal continuity for every canonical combination."""
        records = self.get_canonical_records(program_type=program_type, category_code=category)

        grouped = defaultdict(set)
        meta = {}

        for r in records:
            key = (r["college_id"], r["branch_id"], r["program_type"], r["category"])
            grouped[key].add(r["academic_year"])
            meta[key] = (r["college_code"], r["branch_code"])

        results = []
        for key, yrs in grouped.items():
            col_id, br_id, prog, cat = key
            col_code, br_code = meta[key]

            sorted_yrs = sorted(list(yrs))
            obs_count = len(sorted_yrs)
            missing = sorted(list(set(REFERENCE_YEARS) - set(sorted_yrs)))

            # Consecutive transitions count
            consec_count = 0
            for i in range(len(sorted_yrs) - 1):
                if sorted_yrs[i + 1] == sorted_yrs[i] + 1:
                    consec_count += 1

            results.append(
                SparsityMetadata(
                    college_id=col_id,
                    college_code=col_code,
                    branch_id=br_id,
                    branch_code=br_code,
                    program_type=prog,
                    category=cat,
                    observation_count=obs_count,
                    years_observed=sorted_yrs,
                    missing_years=missing,
                    consecutive_transition_count=consec_count,
                    latest_observation_year=max(sorted_yrs),
                    is_sparse=(obs_count < 3),
                )
            )

        return sorted(results, key=lambda x: (x.college_code, x.branch_code))

    def get_anomalies(self) -> List[HistoricalAnomaly]:
        """Detect and expose factual anomalies from published cutoff records without causal speculation."""
        anomalies: List[HistoricalAnomaly] = []

        # 1. Backward round movement in within-year progressions
        for yr in [2023, 2024, 2026]:
            pairs = WITHIN_YEAR_PROGRESSIONS.get(yr, [])
            for r_from, r_to in pairs:
                for prog in [ProgramType.ENGINEERING.value, ProgramType.ARCHITECTURE.value]:
                    for cat in ["GM", "KKR"]:
                        rec_from = self.get_canonical_records(academic_year=yr, program_type=prog, category_code=cat, round_code=r_from)
                        rec_to = self.get_canonical_records(academic_year=yr, program_type=prog, category_code=cat, round_code=r_to)

                        map_from = {(r["college_id"], r["branch_id"]): r for r in rec_from}
                        map_to = {(r["college_id"], r["branch_id"]): r for r in rec_to}

                        common_keys = set(map_from.keys()) & set(map_to.keys())
                        for k in common_keys:
                            rf = map_from[k]
                            rt = map_to[k]
                            if rt["closing_rank"] < rf["closing_rank"]:
                                rank_delta = rt["closing_rank"] - rf["closing_rank"]
                                anomalies.append(
                                    HistoricalAnomaly(
                                        anomaly_type=AnomalyType.BACKWARD_ROUND_MOVEMENT,
                                        academic_year=yr,
                                        college_code=rf["college_code"],
                                        branch_code=rf["branch_code"],
                                        program_type=prog,
                                        category=cat,
                                        from_round=r_from,
                                        to_round=r_to,
                                        from_rank=rf["closing_rank"],
                                        to_rank=rt["closing_rank"],
                                        rank_delta=rank_delta,
                                        direction=RankDirection.EARLIER_NUMERICALLY,
                                        cause="NOT_DETERMINABLE_FROM_AVAILABLE_DATA",
                                        description="Observed closing rank decreased numerically between rounds.",
                                        details=(
                                            f"Observed closing rank decreased numerically from {rf['closing_rank']} "
                                            f"in {r_from} to {rt['closing_rank']} in {r_to} (delta: {rank_delta}). "
                                            f"Direction: EARLIER_NUMERICALLY. Cause: NOT_DETERMINABLE_FROM_AVAILABLE_DATA."
                                        ),
                                    )
                                )

        # 2. Check for invalid rank values
        all_recs = self.get_canonical_records()
        for r in all_recs:
            if r["closing_rank"] <= 0:
                anomalies.append(
                    HistoricalAnomaly(
                        anomaly_type=AnomalyType.INVALID_RANK_VALUE,
                        academic_year=r["academic_year"],
                        college_code=r["college_code"],
                        branch_code=r["branch_code"],
                        program_type=r["program_type"],
                        category=r["category"],
                        from_round=r["round_code"],
                        to_rank=r["closing_rank"],
                        cause="DATA_VALIDATION_FAILURE",
                        description="Closing rank must be strictly positive.",
                        details=f"Non-positive closing rank: {r['closing_rank']}",
                    )
                )
            if r["opening_rank"] and r["opening_rank"] > r["closing_rank"]:
                anomalies.append(
                    HistoricalAnomaly(
                        anomaly_type=AnomalyType.INVALID_RANK_VALUE,
                        academic_year=r["academic_year"],
                        college_code=r["college_code"],
                        branch_code=r["branch_code"],
                        program_type=r["program_type"],
                        category=r["category"],
                        from_round=r["round_code"],
                        from_rank=r["opening_rank"],
                        to_rank=r["closing_rank"],
                        cause="DATA_VALIDATION_FAILURE",
                        description="Opening rank exceeds closing rank.",
                        details=f"Opening rank ({r['opening_rank']}) greater than closing rank ({r['closing_rank']})",
                    )
                )

        # 3. Missing source version / provenance
        for r in all_recs:
            if not r["source_version_id"]:
                anomalies.append(
                    HistoricalAnomaly(
                        anomaly_type=AnomalyType.MISSING_PROVENANCE,
                        academic_year=r["academic_year"],
                        college_code=r["college_code"],
                        branch_code=r["branch_code"],
                        cause="DATA_VALIDATION_FAILURE",
                        description="Missing source version linkage.",
                        details="Cutoff record has null source_version_id",
                    )
                )

        return anomalies

    def generate_report(self) -> AnalyticsReport:
        """Produce the comprehensive consolidated analytical report across all modules."""
        coverage = self.get_coverage_summary()
        volatility_by_n = self.get_volatility_summary_by_n(round_scope="TERMINAL")
        round_progressions = self.get_round_progression()

        # YoY movements for primary transitions
        yoy_movements = []
        for f_yr, t_yr in [(2023, 2024), (2024, 2026), (2023, 2026)]:
            _, agg = self.get_yoy_movement(from_year=f_yr, to_year=t_yr, round_scope="R1")
            if agg:
                yoy_movements.append(agg)

        recency_evidence = self.get_recency_evidence(anchor_year=2026, round_scope="R1")
        anomalies = self.get_anomalies()

        anomaly_summary = defaultdict(int)
        for a in anomalies:
            anomaly_summary[a.anomaly_type.value] += 1

        return AnalyticsReport(
            coverage=coverage,
            volatility_by_n=volatility_by_n,
            round_progressions=round_progressions,
            yoy_movements=yoy_movements,
            recency_evidence=recency_evidence,
            anomaly_summary=dict(anomaly_summary),
        )
