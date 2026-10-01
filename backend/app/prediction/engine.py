"""Closing Rank Prediction Engine for COMEDK Compass (Stage 3.3B).

Strict Principles:
1. Predicts CLOSING RANK, not admission probability.
   - Candidate eligibility semantics: candidate_rank <= predicted_closing_rank indicates
     the candidate rank is numerically within the predicted closing-rank boundary.
2. Zero Data Leakage:
   - Target-year target-round cutoff is NEVER used as an input feature.
   - Future-year data is NEVER used.
   - For intra-year prediction, ONLY preceding rounds within the target year may be queried.
3. Strict Partition Isolation:
   - ProgramType: Engineering vs Architecture.
   - Category: General Merit (GM) vs Karnataka Region (KKR).
   - Counselling Rounds: KKR_SPECIAL isolated; standard R2 is never invented; 2026 progression is R1 -> R3 -> R4.
4. Factual Data Immutability:
   - Only PUBLISHED records enter prediction features; SUPERSEDED records are strictly excluded.
   - Read-only execution: zero database mutations.
5. Fail-Closed Cold Start:
   - Unseen college, unseen branch, unseen combination, or insufficient historical observations
     return INSUFFICIENT_EVIDENCE with an explicit explanation of missing data.
"""

from collections import defaultdict
from datetime import datetime, timezone
import math
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from backend.app.core.enums import ProgramType, RecordStatus
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.category import Category
from backend.app.analytics.service import (
    HistoricalAnalyticsService,
    _safe_mean,
    _safe_median,
)
from backend.app.analytics.constants import (
    ROUND_R1,
    ROUND_R3,
    ROUND_R4,
    ROUND_CONSOLIDATED_FINAL,
    ROUND_KKR_SPECIAL,
    ROUND_R2_PHASE2,
    TERMINAL_ROUNDS_BY_YEAR,
)
from backend.app.prediction.schemas import (
    PredictionRequest,
    PredictionResult,
    PredictionInterval,
    EvidenceItem,
    EvidenceStrength,
    ColdStartReason,
    BaselineModelType,
    IntervalType,
)


class ClosingRankPredictionEngine:
    """Evidence-grounded Closing Rank Prediction Engine."""

    def __init__(
        self,
        db: Session,
        model_version: str = "v1.0-research",
        dataset_version: str = "2023-2026-v1",
        feature_definition_version: str = "v1.0",
    ):
        self.db = db
        self.analytics_svc = HistoricalAnalyticsService(db)
        self.model_version = model_version
        self.dataset_version = dataset_version
        self.feature_definition_version = feature_definition_version

    def predict(self, request: PredictionRequest) -> PredictionResult:
        """Main prediction entrypoint dispatching across prediction states."""
        # 1. Resolve canonical identities and validate entities
        college = self.db.query(College).filter(College.id == request.college_id).first()
        if not college:
            return self._fail_closed(request, ColdStartReason.UNKNOWN_COLLEGE, "College ID not found in database.")

        branch = self.db.query(Branch).filter(Branch.id == request.branch_id).first()
        if not branch:
            return self._fail_closed(request, ColdStartReason.UNKNOWN_BRANCH, "Branch ID not found in database.")

        canonical_branch_id = branch.canonical_branch_id if (not branch.is_canonical and branch.canonical_branch_id) else branch.id

        # Validate category
        if request.category not in ["GM", "KKR"]:
            return self._fail_closed(
                request,
                ColdStartReason.UNKNOWN_CATEGORY,
                f"Unsupported category '{request.category}'.",
                canonical_branch_id=canonical_branch_id,
            )

        # 2. Dispatch to state-specific prediction method
        target_round = request.round.upper()
        if target_round == "R1":
            return self._predict_r1(request, college.id, canonical_branch_id)
        elif target_round == "R3":
            return self._predict_r3(request, college.id, canonical_branch_id)
        elif target_round in ["R4", "TERMINAL"]:
            return self._predict_terminal(request, college.id, canonical_branch_id)
        else:
            return self._fail_closed(
                request,
                ColdStartReason.NO_HISTORICAL_RECORDS,
                f"Unsupported counselling round '{target_round}' for prediction.",
                canonical_branch_id=canonical_branch_id,
            )

    # -------------------------------------------------------------------------
    # STATE A: ROUND 1 PREDICTION (Opening round - Cross-year evidence only)
    # -------------------------------------------------------------------------
    def _predict_r1(self, request: PredictionRequest, college_id: UUID, branch_id: UUID) -> PredictionResult:
        """Predict Round 1 closing rank using strictly prior years' Round 1 cutoffs."""
        target_year = request.academic_year

        # Query all historical PUBLISHED R1 cutoffs strictly prior to target_year
        records = self.analytics_svc.get_canonical_records(
            program_type=request.program_type,
            category_code=request.category,
            round_code=ROUND_R1,
            status=RecordStatus.PUBLISHED.value,
        )

        # Filter strictly for target college & branch, strictly prior to target_year
        prior_cutoffs: Dict[int, float] = {}
        for r in records:
            if (
                r["college_id"] == college_id
                and r["branch_id"] == branch_id
                and r["academic_year"] < target_year
            ):
                prior_cutoffs[r["academic_year"]] = float(r["closing_rank"])

        n_obs = len(prior_cutoffs)
        if n_obs == 0:
            return self._fail_closed(
                request,
                ColdStartReason.NO_HISTORICAL_RECORDS,
                f"No prior published Round 1 cutoffs found for college {college_id} and branch {branch_id} before year {target_year}.",
                canonical_branch_id=branch_id,
            )

        sorted_years = sorted(prior_cutoffs.keys())
        prior_values = [prior_cutoffs[y] for y in sorted_years]
        latest_year = sorted_years[-1]
        latest_cutoff = prior_cutoffs[latest_year]

        # Determine model
        model_type = request.model_type or BaselineModelType.MODEL_A_LATEST_HISTORICAL
        predicted_rank: Optional[float] = None
        model_name = "Model A (Latest Historical R1)"

        if model_type == BaselineModelType.MODEL_B_PREVIOUS_YEAR:
            prev_year = target_year - 1
            if prev_year in prior_cutoffs:
                predicted_rank = prior_cutoffs[prev_year]
                model_name = f"Model B (Previous Year {prev_year} R1)"
            else:
                return self._fail_closed(
                    request,
                    ColdStartReason.NO_HISTORICAL_RECORDS,
                    f"Model B requires strict T-1 data, but academic year {prev_year} has no official Round 1 cutoff records.",
                    canonical_branch_id=branch_id,
                )
        elif model_type == BaselineModelType.MODEL_C_HISTORICAL_MEAN:
            predicted_rank = sum(prior_values) / len(prior_values)
            model_name = "Model C (Historical Mean R1)"
        elif model_type == BaselineModelType.MODEL_D_HISTORICAL_MEDIAN:
            predicted_rank = _safe_median(prior_values)
            model_name = "Model D (Historical Median R1)"
        elif model_type == BaselineModelType.MODEL_E_RECENT_MEDIAN:
            recent_vals = [prior_cutoffs[y] for y in sorted_years[-2:]]
            predicted_rank = _safe_median(recent_vals)
            model_name = "Model E (Recent 2-Year Median R1)"
        else:
            # Model A (Default - validated optimal in Stage 3.3A backtesting for R1)
            predicted_rank = latest_cutoff
            model_name = f"Model A (Latest Historical R1 - {latest_year})"

        # Evidence strength
        strength = self._assess_evidence_strength(n_obs, has_preceding_round=False)

        # Calibrate interval: Asymmetric Empirical Relative [-15%, +55%]
        interval = self._calculate_interval(predicted_rank, interval_type=IntervalType.ASYMMETRIC_RELATIVE_EMPIRICAL)

        # Build evidence trail
        evidence_trail = [
            EvidenceItem(
                source_type="HISTORICAL_CUTOFF",
                academic_year=y,
                round_code=ROUND_R1,
                closing_rank=prior_cutoffs[y],
                weight=1.0 if y == latest_year and model_type == BaselineModelType.MODEL_A_LATEST_HISTORICAL else None,
                description=f"{y} Round 1 official published closing rank: {prior_cutoffs[y]:,.0f}",
            )
            for y in sorted_years
        ]

        explanation = [
            f"Round 1 prediction is based on {n_obs} prior comparable observation(s) ({', '.join(str(y) for y in sorted_years)}).",
            f"Primary baseline ({model_name}) estimates a closing rank of {predicted_rank:,.0f}.",
            f"Latest available comparable Round 1 cutoff was in {latest_year} at rank {latest_cutoff:,.0f}.",
            f"Calibrated prediction interval: [{interval.lower_bound:,.0f} to {interval.upper_bound:,.0f}] (relative span -15% to +55% reflecting secular expansion).",
        ]

        return PredictionResult(
            academic_year=target_year,
            college_id=college_id,
            branch_id=branch_id,
            category=request.category,
            round=ROUND_R1,
            program_type=request.program_type,
            status="SUCCESS",
            predicted_closing_rank=round(predicted_rank, 1),
            prediction_interval=interval,
            lower_bound=interval.lower_bound,
            upper_bound=interval.upper_bound,
            evidence_strength=strength,
            observation_count=n_obs,
            latest_comparable_year=latest_year,
            cold_start_reason=ColdStartReason.NONE,
            model_name=model_name,
            model_version=self.model_version,
            dataset_version=self.dataset_version,
            feature_definition_version=self.feature_definition_version,
            input_parameters=request.model_dump(mode="json"),
            evidence_trail=evidence_trail,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # STATE B: ROUND 3 PREDICTION (Intra-year R1 + Cross-year R3 evidence)
    # -------------------------------------------------------------------------
    def _predict_r3(self, request: PredictionRequest, college_id: UUID, branch_id: UUID) -> PredictionResult:
        """Predict Round 3 closing rank using current-year R1 and historical R1->R3 progression."""
        target_year = request.academic_year

        # 1. Check for current-year Round 1 cutoff (strictly preceding round)
        r1_records = self.analytics_svc.get_canonical_records(
            academic_year=target_year,
            program_type=request.program_type,
            category_code=request.category,
            round_code=ROUND_R1,
            status=RecordStatus.PUBLISHED.value,
        )
        current_r1: Optional[float] = None
        for r in r1_records:
            if r["college_id"] == college_id and r["branch_id"] == branch_id:
                current_r1 = float(r["closing_rank"])
                break

        # 2. Query historical R3 cutoffs from prior years (< target_year)
        hist_r3_records = self.analytics_svc.get_canonical_records(
            program_type=request.program_type,
            category_code=request.category,
            round_code=ROUND_R3,
            status=RecordStatus.PUBLISHED.value,
        )
        prior_r3: Dict[int, float] = {}
        for r in hist_r3_records:
            if r["college_id"] == college_id and r["branch_id"] == branch_id and r["academic_year"] < target_year:
                prior_r3[r["academic_year"]] = float(r["closing_rank"])

        # 3. Check cold-start condition
        if current_r1 is None and len(prior_r3) == 0:
            return self._fail_closed(
                request,
                ColdStartReason.NO_HISTORICAL_RECORDS,
                f"Neither current-year {target_year} Round 1 nor prior historical Round 3 cutoffs exist for this combination.",
                canonical_branch_id=branch_id,
            )

        # 4. Compute learned historical median R1 -> R3 movement from prior training years
        med_move, med_rel_move = self._learn_historical_movement(
            from_round=ROUND_R1, to_round=ROUND_R3, target_year=target_year, program_type=request.program_type, category=request.category
        )

        # Model selection
        model_type = request.model_type or (
            BaselineModelType.MODEL_G1_ADDITIVE_MOVEMENT if current_r1 is not None else BaselineModelType.MODEL_A_LATEST_HISTORICAL
        )
        predicted_rank: Optional[float] = None
        model_name = ""
        evidence_trail: List[EvidenceItem] = []
        explanation: List[str] = []

        if current_r1 is not None and model_type in [
            BaselineModelType.MODEL_G1_ADDITIVE_MOVEMENT,
            BaselineModelType.MODEL_F_PRECEDING_ROUND,
            BaselineModelType.MODEL_G2_MULTIPLICATIVE_MOVEMENT,
            BaselineModelType.MODEL_H_HYBRID,
        ]:
            evidence_trail.append(
                EvidenceItem(
                    source_type="PRECEDING_ROUND",
                    academic_year=target_year,
                    round_code=ROUND_R1,
                    closing_rank=current_r1,
                    description=f"{target_year} Round 1 preceding closing rank: {current_r1:,.0f}",
                )
            )

            if model_type == BaselineModelType.MODEL_F_PRECEDING_ROUND:
                predicted_rank = current_r1
                model_name = f"Model F (Within-Year Preceding R1 Alone)"
            elif model_type == BaselineModelType.MODEL_G2_MULTIPLICATIVE_MOVEMENT:
                predicted_rank = current_r1 * (1.0 + med_rel_move)
                model_name = f"Model G2 (Preceding R1 * [1 + {med_rel_move:.1%} Relative Movement])"
            elif model_type == BaselineModelType.MODEL_H_HYBRID and len(prior_r3) > 0:
                latest_r3_val = prior_r3[max(prior_r3.keys())]
                g1_val = current_r1 + med_move
                predicted_rank = 0.7 * g1_val + 0.3 * latest_r3_val
                model_name = f"Model H (Hybrid: 70% Intra-Year Movement + 30% Historical R3)"
            else:
                # Model G1 (Additive movement - default validated)
                predicted_rank = current_r1 + med_move
                model_name = f"Model G1 (Preceding R1 + Additive Movement [+{med_move:,.0f} ranks])"
                evidence_trail.append(
                    EvidenceItem(
                        source_type="HISTORICAL_MOVEMENT",
                        round_code="R1_TO_R3",
                        closing_rank=med_move,
                        description=f"Median R1->R3 expansion learned from prior years: +{med_move:,.0f} ranks",
                    )
                )
        else:
            # Fall back to cross-year historical R3
            if len(prior_r3) == 0:
                return self._fail_closed(
                    request,
                    ColdStartReason.NO_HISTORICAL_RECORDS,
                    f"Current {target_year} R1 is unavailable and no historical R3 records exist.",
                    canonical_branch_id=branch_id,
                )
            latest_r3_yr = max(prior_r3.keys())
            predicted_rank = prior_r3[latest_r3_yr]
            model_name = f"Model A (Latest Historical R3 - {latest_r3_yr})"
            evidence_trail.append(
                EvidenceItem(
                    source_type="HISTORICAL_CUTOFF",
                    academic_year=latest_r3_yr,
                    round_code=ROUND_R3,
                    closing_rank=predicted_rank,
                    description=f"{latest_r3_yr} Round 3 official closing rank: {predicted_rank:,.0f}",
                )
            )

        # Interval calibration
        interval = self._calculate_interval(predicted_rank, interval_type=IntervalType.ASYMMETRIC_RELATIVE_EMPIRICAL)
        strength = self._assess_evidence_strength(len(prior_r3), has_preceding_round=(current_r1 is not None))

        explanation.append(f"Round 3 prediction generated via {model_name}.")
        if current_r1 is not None:
            explanation.append(f"Current {target_year} Round 1 closing rank established baseline at {current_r1:,.0f}.")
            explanation.append(f"Historical R1->R3 progression indicates a median expansion of +{med_move:,.0f} ranks.")
        if prior_r3:
            explanation.append(f"Supported by historical Round 3 data from years: {', '.join(str(y) for y in sorted(prior_r3.keys()))}.")

        return PredictionResult(
            academic_year=target_year,
            college_id=college_id,
            branch_id=branch_id,
            category=request.category,
            round=ROUND_R3,
            program_type=request.program_type,
            status="SUCCESS",
            predicted_closing_rank=round(predicted_rank, 1),
            prediction_interval=interval,
            lower_bound=interval.lower_bound,
            upper_bound=interval.upper_bound,
            evidence_strength=strength,
            observation_count=len(prior_r3) + (1 if current_r1 is not None else 0),
            latest_comparable_year=max(prior_r3.keys()) if prior_r3 else target_year,
            cold_start_reason=ColdStartReason.NONE,
            model_name=model_name,
            model_version=self.model_version,
            dataset_version=self.dataset_version,
            feature_definition_version=self.feature_definition_version,
            input_parameters=request.model_dump(mode="json"),
            evidence_trail=evidence_trail,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # STATE C: ROUND 4 / TERMINAL PREDICTION (Final allotment)
    # -------------------------------------------------------------------------
    def _predict_terminal(self, request: PredictionRequest, college_id: UUID, branch_id: UUID) -> PredictionResult:
        """Predict Terminal (Round 4) closing rank using preceding R3 and historical terminal data."""
        target_year = request.academic_year

        # 1. Query current-year Round 3 cutoff if available (for 2026 progression: R1 -> R3 -> R4)
        r3_records = self.analytics_svc.get_canonical_records(
            academic_year=target_year,
            program_type=request.program_type,
            category_code=request.category,
            round_code=ROUND_R3,
            status=RecordStatus.PUBLISHED.value,
        )
        current_r3: Optional[float] = None
        for r in r3_records:
            if r["college_id"] == college_id and r["branch_id"] == branch_id:
                current_r3 = float(r["closing_rank"])
                break

        # 2. Query historical terminal cutoffs strictly prior to target_year
        prior_term = self._get_historical_terminal_cutoffs(
            college_id, branch_id, target_year, request.program_type, request.category
        )

        if current_r3 is None and len(prior_term) == 0:
            return self._fail_closed(
                request,
                ColdStartReason.NO_HISTORICAL_RECORDS,
                f"Neither current {target_year} Round 3 nor prior terminal cutoffs exist for this combination.",
                canonical_branch_id=branch_id,
            )

        model_type = request.model_type or (
            BaselineModelType.MODEL_F_PRECEDING_ROUND if current_r3 is not None else BaselineModelType.MODEL_D_HISTORICAL_MEDIAN
        )
        predicted_rank: Optional[float] = None
        model_name = ""
        evidence_trail: List[EvidenceItem] = []
        explanation: List[str] = []

        if current_r3 is not None:
            evidence_trail.append(
                EvidenceItem(
                    source_type="PRECEDING_ROUND",
                    academic_year=target_year,
                    round_code=ROUND_R3,
                    closing_rank=current_r3,
                    description=f"{target_year} Round 3 preceding closing rank: {current_r3:,.0f}",
                )
            )
            if model_type == BaselineModelType.MODEL_G1_ADDITIVE_MOVEMENT:
                # Intra-year expansion shift (median ~3,800 ranks)
                shift = 3800.0
                predicted_rank = current_r3 + shift
                model_name = f"Model G1 (Preceding R3 + Additive Expansion [+{shift:,.0f} ranks])"
            elif model_type == BaselineModelType.MODEL_H_HYBRID and len(prior_term) > 0:
                hist_med = _safe_median(list(prior_term.values()))
                predicted_rank = 0.7 * current_r3 + 0.3 * hist_med
                model_name = "Model H (Hybrid: 70% Preceding R3 + 30% Historical Median Terminal)"
            else:
                # Model F: Preceding R3 alone (proven lowest MAE 11,172 ranks in Stage 3.3A Window 6)
                predicted_rank = current_r3
                model_name = f"Model F (Within-Year Preceding R3 Alone)"
        else:
            # Cross-year terminal models
            sorted_t_years = sorted(prior_term.keys())
            t_values = [prior_term[y] for y in sorted_t_years]
            latest_t_year = sorted_t_years[-1]
            latest_t_val = prior_term[latest_t_year]

            if model_type == BaselineModelType.MODEL_A_LATEST_HISTORICAL:
                predicted_rank = latest_t_val
                model_name = f"Model A (Latest Historical Terminal - {latest_t_year})"
            elif model_type == BaselineModelType.MODEL_B_PREVIOUS_YEAR:
                prev_y = target_year - 1
                if prev_y in prior_term:
                    predicted_rank = prior_term[prev_y]
                    model_name = f"Model B (Strict Previous Year {prev_y} Terminal)"
                else:
                    return self._fail_closed(
                        request,
                        ColdStartReason.NO_HISTORICAL_RECORDS,
                        f"Model B requires strict T-1 data, but academic year {prev_y} terminal cutoff is missing.",
                        canonical_branch_id=branch_id,
                    )
            elif model_type == BaselineModelType.MODEL_C_HISTORICAL_MEAN:
                predicted_rank = sum(t_values) / len(t_values)
                model_name = "Model C (Historical Mean Terminal)"
            else:
                # Model D (Historical Median Terminal - robust against single-year reporting anomalies)
                predicted_rank = _safe_median(t_values)
                model_name = "Model D (Historical Median Terminal)"

            for y in sorted_t_years:
                evidence_trail.append(
                    EvidenceItem(
                        source_type="HISTORICAL_CUTOFF",
                        academic_year=y,
                        round_code="TERMINAL",
                        closing_rank=prior_term[y],
                        description=f"{y} terminal official closing rank: {prior_term[y]:,.0f}",
                    )
                )

        interval = self._calculate_interval(predicted_rank, interval_type=IntervalType.VOLATILITY_ADAPTIVE_WIDE)
        strength = self._assess_evidence_strength(len(prior_term), has_preceding_round=(current_r3 is not None))

        explanation.append(f"Terminal closing rank prediction generated via {model_name}.")
        if current_r3 is not None:
            explanation.append(f"Preceding Round 3 established the intra-year floor at {current_r3:,.0f}.")
        if prior_term:
            explanation.append(
                f"Grounded by {len(prior_term)} historical terminal observation(s) from: {', '.join(str(y) for y in sorted(prior_term.keys()))}."
            )
        explanation.append(
            f"Calibrated wide uncertainty interval [{interval.lower_bound:,.0f} to {interval.upper_bound:,.0f}] reflects empirical R3->R4 rank volatility."
        )

        return PredictionResult(
            academic_year=target_year,
            college_id=college_id,
            branch_id=branch_id,
            category=request.category,
            round="TERMINAL",
            program_type=request.program_type,
            status="SUCCESS",
            predicted_closing_rank=round(predicted_rank, 1),
            prediction_interval=interval,
            lower_bound=interval.lower_bound,
            upper_bound=interval.upper_bound,
            evidence_strength=strength,
            observation_count=len(prior_term) + (1 if current_r3 is not None else 0),
            latest_comparable_year=max(prior_term.keys()) if prior_term else target_year,
            cold_start_reason=ColdStartReason.NONE,
            model_name=model_name,
            model_version=self.model_version,
            dataset_version=self.dataset_version,
            feature_definition_version=self.feature_definition_version,
            input_parameters=request.model_dump(mode="json"),
            evidence_trail=evidence_trail,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # HELPER & CALIBRATION METHODS
    # -------------------------------------------------------------------------
    def _learn_historical_movement(
        self, from_round: str, to_round: str, target_year: int, program_type: str, category: str
    ) -> Tuple[float, float]:
        """Learn median absolute and relative round-to-round movement from prior training years."""
        recs = self.analytics_svc.get_canonical_records(
            program_type=program_type,
            category_code=category,
            status=RecordStatus.PUBLISHED.value,
        )
        by_yr = defaultdict(lambda: defaultdict(dict))
        for r in recs:
            if r["academic_year"] < target_year:
                by_yr[(r["college_id"], r["branch_id"])][r["academic_year"]][r["round_code"]] = r["closing_rank"]

        moves: List[float] = []
        rel_moves: List[float] = []
        for k, y_map in by_yr.items():
            for yr, r_map in y_map.items():
                if from_round in r_map and to_round in r_map:
                    diff = r_map[to_round] - r_map[from_round]
                    moves.append(diff)
                    rel_moves.append(diff / r_map[from_round])

        med_abs = _safe_median(moves) if moves else 0.0
        med_rel = _safe_median(rel_moves) if rel_moves else 0.0
        return med_abs, med_rel

    def _get_historical_terminal_cutoffs(
        self, college_id: UUID, branch_id: UUID, target_year: int, program_type: str, category: str
    ) -> Dict[int, float]:
        """Extract terminal cutoffs strictly prior to target_year."""
        recs = self.analytics_svc.get_canonical_records(
            program_type=program_type,
            category_code=category,
            status=RecordStatus.PUBLISHED.value,
        )
        prior_term: Dict[int, float] = {}
        for r in recs:
            y = r["academic_year"]
            if r["college_id"] == college_id and r["branch_id"] == branch_id and y < target_year:
                rc = r["round_code"]
                # Determine if this record matches the terminal round of year y
                if y == 2023 and rc in [ROUND_CONSOLIDATED_FINAL, ROUND_R3]:
                    prior_term[y] = float(r["closing_rank"])
                elif y == 2024 and rc == ROUND_R3:
                    prior_term[y] = float(r["closing_rank"])
                elif y == 2025 and rc == ROUND_R4:
                    prior_term[y] = float(r["closing_rank"])
                elif y == 2026 and rc in [ROUND_R4, ROUND_R3]:
                    prior_term[y] = float(r["closing_rank"])
        return prior_term

    def _calculate_interval(self, predicted_rank: float, interval_type: IntervalType) -> PredictionInterval:
        """Calculate calibrated prediction interval based on empirical residual characteristics."""
        if interval_type == IntervalType.VOLATILITY_ADAPTIVE_WIDE:
            # Derived from empirical R3->R4 audit:
            # Programs with low cutoffs (<10k) experience tight movement (median +1.2k, p90 +3.3k).
            # Programs with high cutoffs (>25k) experience massive expansion (up to +57k ranks).
            if predicted_rank < 10000:
                lb = max(1.0, predicted_rank * 0.90)
                ub = predicted_rank + 4000.0
            elif predicted_rank < 25000:
                lb = max(1.0, predicted_rank * 0.85)
                ub = predicted_rank + 12000.0
            else:
                lb = max(1.0, predicted_rank * 0.70)
                ub = min(120000.0, max(predicted_rank * 1.55, predicted_rank + 45000.0))
            coverage = 0.90
        elif interval_type == IntervalType.ASYMMETRIC_RELATIVE_EMPIRICAL:
            # Derived from Stage 3.3A empirical residual distribution:
            # Skewed higher to reflect secular expansion: -15% lower bound, +55% upper bound
            lb = max(1.0, predicted_rank * 0.85)
            ub = predicted_rank * 1.55
            coverage = 0.70
        elif interval_type == IntervalType.ADDITIVE_EMPIRICAL:
            lb = max(1.0, predicted_rank - 5000.0)
            ub = predicted_rank + 20000.0
            coverage = 0.65
        else:
            # Symmetric relative +/- 25%
            lb = max(1.0, predicted_rank * 0.75)
            ub = predicted_rank * 1.25
            coverage = 0.48

        width = ub - lb
        rel_width = width / predicted_rank if predicted_rank > 0 else 0.0

        return PredictionInterval(
            lower_bound=round(lb, 1),
            upper_bound=round(ub, 1),
            interval_type=interval_type,
            target_coverage=coverage,
            interval_width=round(width, 1),
            relative_width=round(rel_width, 4),
        )

    def _assess_evidence_strength(self, n_observations: int, has_preceding_round: bool) -> EvidenceStrength:
        """Evaluate evidence strength based on observation depth and intra-year preceding availability."""
        if has_preceding_round:
            return EvidenceStrength.STRONG
        if n_observations >= 3:
            return EvidenceStrength.STRONG
        elif n_observations == 2:
            return EvidenceStrength.MODERATE
        elif n_observations == 1:
            return EvidenceStrength.SPARSE
        else:
            return EvidenceStrength.INSUFFICIENT_EVIDENCE

    def _fail_closed(
        self,
        request: PredictionRequest,
        reason: ColdStartReason,
        explanation: str,
        canonical_branch_id: Optional[UUID] = None,
    ) -> PredictionResult:
        """Standardized fail-closed handler returning INSUFFICIENT_EVIDENCE."""
        return PredictionResult(
            academic_year=request.academic_year,
            college_id=request.college_id,
            branch_id=canonical_branch_id or request.branch_id,
            category=request.category,
            round=request.round,
            program_type=request.program_type,
            status="INSUFFICIENT_EVIDENCE",
            predicted_closing_rank=None,
            prediction_interval=None,
            lower_bound=None,
            upper_bound=None,
            evidence_strength=EvidenceStrength.INSUFFICIENT_EVIDENCE,
            observation_count=0,
            latest_comparable_year=None,
            cold_start_reason=reason,
            model_name="FAIL_CLOSED_HANDLER",
            model_version=self.model_version,
            dataset_version=self.dataset_version,
            feature_definition_version=self.feature_definition_version,
            input_parameters=request.model_dump(mode="json"),
            evidence_trail=[],
            explanation=[explanation],
        )
