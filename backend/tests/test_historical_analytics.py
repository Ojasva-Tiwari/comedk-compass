"""Unit and integration tests for Historical Analytics Service & API Endpoints.

Tests all analytical requirements:
- Coverage summary & observation depth
- Canonical branch grouping (aliases to canonical)
- GM / KKR category separation
- Program-type separation (Engineering vs Architecture)
- Round comparability (DIRECT, PARTIAL, NONE)
- YoY movement, absolute/relative movement, factual direction terminology
- Volatility statistics across n=1, n=2, n=3, n=4, MAD, CV, and quality flags
- Within-year round progression & backward movement detection
- Recency distance evidence
- Sparsity metadata
- Deterministic outputs
- Strictly read-only behavior (zero database mutations)
- API endpoint validation
"""

import pytest
from sqlalchemy import func
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.category import Category
from backend.app.models.round import CounsellingRound
from backend.app.models.source import SourceVersion
from backend.app.analytics.constants import (
    RankDirection,
    ComparabilityStatus,
    VolatilityDataQuality,
    AnomalyType,
    get_round_comparability,
    ROUND_R1,
    ROUND_MOCK,
    ROUND_KKR_SPECIAL,
    ROUND_R2_PHASE2,
    ROUND_R3,
    ROUND_R4,
    ROUND_CONSOLIDATED_FINAL,
)
from backend.app.analytics.service import (
    HistoricalAnalyticsService,
    _safe_mean,
    _safe_median,
    _sample_stddev,
    _median_absolute_deviation,
    _coefficient_of_variation,
)


def test_math_helpers_zero_and_edge_cases():
    """Verify statistical helper functions handle edge cases and zero division safely."""
    assert _safe_mean([]) is None
    assert _safe_median([]) is None
    assert _sample_stddev([]) is None
    assert _sample_stddev([100.0]) is None
    assert _median_absolute_deviation([]) is None
    assert _median_absolute_deviation([100.0]) is None
    assert _coefficient_of_variation([]) is None
    assert _coefficient_of_variation([100.0]) is None
    assert _coefficient_of_variation([0.0, 0.0]) is None

    # Test n = 2
    vals_2 = [100.0, 200.0]
    assert _safe_mean(vals_2) == 150.0
    assert _safe_median(vals_2) == 150.0
    assert round(_sample_stddev(vals_2), 4) == 70.7107
    assert round(_coefficient_of_variation(vals_2), 4) == round(70.7107 / 150.0, 4)
    assert _median_absolute_deviation(vals_2) == 50.0

    # Test n = 3
    vals_3 = [100.0, 150.0, 200.0]
    assert _safe_mean(vals_3) == 150.0
    assert _safe_median(vals_3) == 150.0
    assert _sample_stddev(vals_3) == 50.0
    assert round(_coefficient_of_variation(vals_3), 4) == round(50.0 / 150.0, 4)
    assert _median_absolute_deviation(vals_3) == 50.0


def test_round_comparability_rules():
    """Verify explicit round comparability semantics across all years."""
    # R1 across any years is DIRECT
    assert get_round_comparability(2023, ROUND_R1, 2024, ROUND_R1) == ComparabilityStatus.DIRECT
    assert get_round_comparability(2024, ROUND_R1, 2026, ROUND_R1) == ComparabilityStatus.DIRECT
    assert get_round_comparability(2023, ROUND_R1, 2026, ROUND_R1) == ComparabilityStatus.DIRECT

    # MOCK across any years is DIRECT
    assert get_round_comparability(2023, ROUND_MOCK, 2026, ROUND_MOCK) == ComparabilityStatus.DIRECT

    # KKR_SPECIAL across any years is DIRECT
    assert get_round_comparability(2023, ROUND_KKR_SPECIAL, 2026, ROUND_KKR_SPECIAL) == ComparabilityStatus.DIRECT

    # KKR_SPECIAL compared to general round is NONE
    assert get_round_comparability(2023, ROUND_KKR_SPECIAL, 2023, ROUND_R1) == ComparabilityStatus.NONE
    assert get_round_comparability(2024, ROUND_KKR_SPECIAL, 2024, ROUND_R2_PHASE2) == ComparabilityStatus.NONE

    # R2_PHASE2 between 2023 and 2024 is DIRECT
    assert get_round_comparability(2023, ROUND_R2_PHASE2, 2024, ROUND_R2_PHASE2) == ComparabilityStatus.DIRECT

    # R3 between 2023 and 2024 is DIRECT
    assert get_round_comparability(2023, ROUND_R3, 2024, ROUND_R3) == ComparabilityStatus.DIRECT

    # R3 between 2024 (terminal) and 2026 (intermediate) is PARTIAL
    assert get_round_comparability(2024, ROUND_R3, 2026, ROUND_R3) == ComparabilityStatus.PARTIAL

    # Terminal rounds across years are PARTIAL
    assert get_round_comparability(2023, ROUND_CONSOLIDATED_FINAL, 2024, ROUND_R3) == ComparabilityStatus.PARTIAL
    assert get_round_comparability(2024, ROUND_R3, 2025, ROUND_R4) == ComparabilityStatus.PARTIAL
    assert get_round_comparability(2025, ROUND_R4, 2026, ROUND_R4) == ComparabilityStatus.PARTIAL

    # 2025 R4 compared to R1 is NONE
    assert get_round_comparability(2025, ROUND_R4, 2024, ROUND_R1) == ComparabilityStatus.NONE
    assert get_round_comparability(2025, ROUND_R4, 2026, ROUND_R1) == ComparabilityStatus.NONE


def test_coverage_summary(db):
    """Verify historical coverage summary matches official published dataset with exact record counts."""
    service = HistoricalAnalyticsService(db)
    cov = service.get_coverage_summary()

    # Exact expected years and totals
    assert cov.years_available == [2023, 2024, 2025, 2026]
    assert cov.total_records == 12000
    assert cov.published_records == 11996
    assert cov.superseded_records == 4

    # Exact published counts per year (sum == 11,996)
    assert cov.records_per_year[2023] == 4284
    assert cov.records_per_year[2024] == 3520
    assert cov.records_per_year[2025] == 637
    assert cov.records_per_year[2026] == 3555
    assert sum(cov.records_per_year.values()) == 11996

    # Exact total factual records per year in DB (sum == 12,000)
    assert cov.total_records_per_year[2023] == 4286
    assert cov.total_records_per_year[2024] == 3521
    assert cov.total_records_per_year[2025] == 637
    assert cov.total_records_per_year[2026] == 3556
    assert sum(cov.total_records_per_year.values()) == 12000

    # Superseded record counts per year (sum == 4)
    assert cov.superseded_records_per_year[2023] == 2
    assert cov.superseded_records_per_year[2024] == 1
    assert cov.superseded_records_per_year.get(2025, 0) == 0
    assert cov.superseded_records_per_year[2026] == 1
    assert sum(cov.superseded_records_per_year.values()) == 4

    # Exact 4 excluded records validation
    assert len(cov.excluded_records) == 4
    expected_excluded_ids = {
        "f69c0360-12ff-4e3f-bc0d-a544434ae94b",
        "d363a007-5532-46cd-a31a-9e03943a5fb5",
        "293c9f58-f3fc-4e6e-b4c1-a2d1bce58c4b",
        "d7bb82af-caf4-4444-a02b-40613127f94c",
    }
    actual_excluded_ids = {str(r.cutoff_id) for r in cov.excluded_records}
    assert actual_excluded_ids == expected_excluded_ids
    for ex in cov.excluded_records:
        assert ex.status == "SUPERSEDED"
        assert len(ex.exclusion_reason) > 0

    # Observation depth counts
    assert cov.observation_depth_counts[1] == 485
    assert cov.observation_depth_counts[2] == 371
    assert cov.observation_depth_counts[3] == 405
    assert cov.observation_depth_counts[4] == 495


def test_database_12000_record_preservation_and_status_handling(db):
    """Verify 12,000 factual database records are strictly preserved and separated by status."""
    total_db = db.query(CutoffRecord).count()
    published_db = db.query(CutoffRecord).filter(CutoffRecord.status == "PUBLISHED").count()
    superseded_db = db.query(CutoffRecord).filter(CutoffRecord.status == "SUPERSEDED").count()
    other_status_db = db.query(CutoffRecord).filter(~CutoffRecord.status.in_(["PUBLISHED", "SUPERSEDED"])).count()

    assert total_db == 12000
    assert published_db == 11996
    assert superseded_db == 4
    assert other_status_db == 0
    assert published_db + superseded_db == total_db

    # Year breakdown of published cutoffs
    year_pub = dict(db.query(CutoffRecord.academic_year, func.count(CutoffRecord.id))
                    .filter(CutoffRecord.status == "PUBLISHED")
                    .group_by(CutoffRecord.academic_year).all())
    assert year_pub[2023] == 4284
    assert year_pub[2024] == 3520
    assert year_pub[2025] == 637
    assert year_pub[2026] == 3555
    assert sum(year_pub.values()) == 11996

    # Year breakdown of total cutoffs
    year_all = dict(db.query(CutoffRecord.academic_year, func.count(CutoffRecord.id))
                    .group_by(CutoffRecord.academic_year).all())
    assert year_all[2023] == 4286
    assert year_all[2024] == 3521
    assert year_all[2025] == 637
    assert year_all[2026] == 3556
    assert sum(year_all.values()) == 12000

    # Ensure analytics queries strictly exclude SUPERSEDED records
    service = HistoricalAnalyticsService(db)
    pub_canonical = service.get_canonical_records(status="PUBLISHED")
    assert len(pub_canonical) == 11996
    for r in pub_canonical:
        assert r["status"] == "PUBLISHED"


def test_canonical_grouping(db):
    """Verify branch aliases and colleges are properly mapped to canonical entities."""
    service = HistoricalAnalyticsService(db)
    recs = service.get_canonical_records()

    # 1. Verify branch canonicalization
    alias_branches = db.query(Branch).filter(Branch.is_canonical == False, Branch.canonical_branch_id != None).all()
    alias_ids = {b.id for b in alias_branches}

    # None of the returned canonical records should have an alias branch_id
    for r in recs:
        assert r["branch_id"] not in alias_ids

    # 2. Verify college consistency
    colleges = {c.id: c.code for c in db.query(College).all()}
    for r in recs:
        assert r["college_id"] in colleges
        assert r["college_code"] == colleges[r["college_id"]]


def test_gm_kkr_separation(db):
    """Verify GM and KKR records are never aggregated together."""
    service = HistoricalAnalyticsService(db)

    items_gm, agg_gm = service.get_yoy_movement(
        from_year=2024, to_year=2026, round_scope="R1", category="GM"
    )
    assert agg_gm is not None
    assert agg_gm.category == "GM"
    for it in items_gm:
        assert it.category == "GM"

    items_kkr, agg_kkr = service.get_yoy_movement(
        from_year=2024, to_year=2026, round_scope="R1", category="KKR"
    )
    assert agg_kkr is not None
    assert agg_kkr.category == "KKR"
    for it in items_kkr:
        assert it.category == "KKR"

    # GM and KKR counts must be independent
    assert len(items_gm) != len(items_kkr)


def test_program_type_separation(db):
    """Verify Engineering and Architecture records are never mixed."""
    service = HistoricalAnalyticsService(db)

    items_eng, agg_eng = service.get_yoy_movement(
        from_year=2024, to_year=2026, round_scope="R1", program_type="ENGINEERING"
    )
    assert agg_eng is not None
    assert agg_eng.program_type == "ENGINEERING"
    for it in items_eng:
        assert it.program_type == "ENGINEERING"

    items_arch, agg_arch = service.get_yoy_movement(
        from_year=2024, to_year=2026, round_scope="R1", program_type="ARCHITECTURE"
    )
    if agg_arch:
        assert agg_arch.program_type == "ARCHITECTURE"
        for it in items_arch:
            assert it.program_type == "ARCHITECTURE"


def test_yoy_movement_factual_direction(db):
    """Verify YoY movement calculations and strict factual direction terminology."""
    service = HistoricalAnalyticsService(db)
    items, agg = service.get_yoy_movement(from_year=2024, to_year=2026, round_scope="R1")

    assert agg is not None
    assert agg.matched_pairs == len(items)
    assert agg.comparability == ComparabilityStatus.DIRECT

    for it in items:
        expected_diff = it.current_closing_rank - it.previous_closing_rank
        expected_rel = expected_diff / float(it.previous_closing_rank)

        assert it.absolute_movement == expected_diff
        assert round(it.relative_movement, 6) == round(expected_rel, 6)

        if expected_diff < 0:
            assert it.direction == RankDirection.EARLIER_NUMERICALLY
        elif expected_diff > 0:
            assert it.direction == RankDirection.LATER_NUMERICALLY
        else:
            assert it.direction == RankDirection.UNCHANGED


def test_volatility_depth_and_data_quality(db):
    """Verify historical volatility statistics across n=1, n=2, n>=3 and quality flags."""
    service = HistoricalAnalyticsService(db)

    # All combinations including n=1
    all_metrics = service.get_volatility_metrics(round_scope="TERMINAL", min_n=1)

    n1_items = [m for m in all_metrics if m.observation_count == 1]
    n2_items = [m for m in all_metrics if m.observation_count == 2]
    n3_plus_items = [m for m in all_metrics if m.observation_count >= 3]

    assert len(n1_items) > 0
    for m in n1_items:
        assert m.volatility_data_quality == VolatilityDataQuality.INSUFFICIENT
        assert m.standard_deviation is None
        assert m.coefficient_of_variation is None
        assert m.mad is None
        assert m.mean == float(m.min_rank)
        assert m.rank_range == 0

    assert len(n2_items) > 0
    for m in n2_items:
        assert m.volatility_data_quality == VolatilityDataQuality.SPARSE
        assert m.standard_deviation is not None
        assert m.coefficient_of_variation is not None
        assert m.mad is not None
        assert len(m.sequential_absolute_movements) == 1

    assert len(n3_plus_items) > 0
    for m in n3_plus_items:
        assert m.volatility_data_quality == VolatilityDataQuality.OBSERVABLE
        assert m.standard_deviation is not None
        assert m.coefficient_of_variation is not None
        assert m.mad is not None
        assert len(m.sequential_absolute_movements) >= 2


def test_round_progression_within_year(db):
    """Verify within-year round progressions and detection of backward round movements."""
    service = HistoricalAnalyticsService(db)
    prog_2026 = service.get_round_progression(academic_year=2026)

    # 2026 has R1 -> R3 and R3 -> R4
    transitions = {(p.from_round, p.to_round) for p in prog_2026}
    assert ("R1", "R3") in transitions
    assert ("R3", "R4") in transitions

    for p in prog_2026:
        assert p.matched_pairs > 0
        assert p.earlier_numerically_count + p.later_numerically_count + p.unchanged_count == p.matched_pairs
        # In 2026 R3->R4, backward round movements (earlier ranks) occur in 64 cases
        if p.from_round == "R3" and p.to_round == "R4":
            assert p.earlier_numerically_count == 64


def test_recency_evidence_accuracy(db):
    """Verify recency distance comparisons between recent (2024) and older (2023) against anchor (2026)."""
    service = HistoricalAnalyticsService(db)
    recs = service.get_recency_evidence(anchor_year=2026, round_scope="R1")

    assert len(recs) == 1
    r = recs[0]
    assert r.anchor_year == 2026
    assert r.recent_year == 2024
    assert r.older_year == 2023
    assert r.evaluated_triples == 570
    assert r.recent_closer_count == 422
    assert r.older_closer_count == 148
    assert round(r.recent_closer_percentage, 1) == 74.0
    assert r.recent_median_absolute_distance == 9861.5
    assert r.older_median_absolute_distance == 16303.0


def test_sparsity_metadata(db):
    """Verify sparsity metadata flags combinations with n < 3."""
    service = HistoricalAnalyticsService(db)
    sparsity_list = service.get_sparsity_metadata(program_type="ENGINEERING", category="GM")

    assert len(sparsity_list) > 0
    for s in sparsity_list:
        assert s.observation_count == len(s.years_observed)
        assert s.is_sparse == (s.observation_count < 3)
        assert set(s.years_observed) & set(s.missing_years) == set()
        assert set(s.years_observed) | set(s.missing_years) == {2023, 2024, 2025, 2026}


def test_anomalies_reporting_and_no_causal_language(db):
    """Verify factual data anomalies reporting and assert zero unsupported causal claims."""
    service = HistoricalAnalyticsService(db)
    anomalies = service.get_anomalies()

    backward_cases = [a for a in anomalies if a.anomaly_type == AnomalyType.BACKWARD_ROUND_MOVEMENT]
    assert len(backward_cases) > 0

    # Ensure all backward cases have negative delta, earlier numerically direction, and NO causal wording
    forbidden_causal_terms = [
        "surrender", "surrendered", "upgrade", "upgraded", "upstream",
        "unallocated", "candidate behavior", "candidate behaviour", "seat blocking"
    ]

    for b in backward_cases:
        assert b.rank_delta < 0
        assert b.direction == RankDirection.EARLIER_NUMERICALLY
        assert b.from_rank > b.to_rank
        assert b.cause == "NOT_DETERMINABLE_FROM_AVAILABLE_DATA"
        assert b.description == "Observed closing rank decreased numerically between rounds."

        # Strict assertion: no causal inference in any anomaly string fields
        for term in forbidden_causal_terms:
            assert term not in b.cause.lower(), f"Forbidden causal term '{term}' found in cause"
            assert term not in b.description.lower(), f"Forbidden causal term '{term}' found in description"
            assert term not in b.details.lower(), f"Forbidden causal term '{term}' found in details"


def test_volatility_reconciliation_terminal_vs_strict(db):
    """Verify and reconcile terminal volatility counts between TERMINAL (n=527) and STRICT_TERMINAL (n=461)."""
    service = HistoricalAnalyticsService(db)

    # 1. TERMINAL: Terminal Admission State / Final Allotment (validated audit grain with exhausted seat fallback)
    term_summary = service.get_volatility_summary_by_n(round_scope="TERMINAL")
    assert term_summary[2].combination_count == 162
    assert term_summary[3].combination_count == 133
    assert term_summary[4].combination_count == 232
    term_total = sum(term_summary[n].combination_count for n in (2, 3, 4))
    assert term_total == 527

    # 2. STRICT_TERMINAL: Strict Nominal Document Match (CONSOLIDATED_FINAL, R3, R4, R4 without fallback)
    strict_summary = service.get_volatility_summary_by_n(round_scope="STRICT_TERMINAL")
    assert strict_summary[2].combination_count == 150
    assert strict_summary[3].combination_count == 95
    assert strict_summary[4].combination_count == 216
    strict_total = sum(strict_summary[n].combination_count for n in (2, 3, 4))
    assert strict_total == 461

    # 3. Mathematical reconciliation of the 66 combination difference
    assert term_total - strict_total == 66
    assert term_summary[4].combination_count - strict_summary[4].combination_count == 16
    assert term_summary[3].combination_count - strict_summary[3].combination_count == 38
    assert term_summary[2].combination_count - strict_summary[2].combination_count == 12



def test_read_only_invariance(db):
    """CRITICAL: Verify service operations never mutate database records or row counts."""
    # Count rows before
    c_colleges = db.query(College).count()
    c_branches = db.query(Branch).count()
    c_categories = db.query(Category).count()
    c_rounds = db.query(CounsellingRound).count()
    c_cutoffs = db.query(CutoffRecord).count()
    c_sources = db.query(SourceVersion).count()

    service = HistoricalAnalyticsService(db)

    # Execute all analytical functions
    _ = service.get_coverage_summary()
    _ = service.get_yoy_movement(from_year=2024, to_year=2026, round_scope="R1")
    _ = service.get_volatility_metrics(round_scope="TERMINAL")
    _ = service.get_volatility_summary_by_n(round_scope="TERMINAL")
    _ = service.get_round_progression()
    _ = service.get_recency_evidence()
    _ = service.get_sparsity_metadata()
    _ = service.get_anomalies()
    _ = service.generate_report()

    # Session must be completely clean (no dirty objects, no pending changes)
    assert len(db.dirty) == 0
    assert len(db.new) == 0
    assert len(db.deleted) == 0

    # Verify counts after
    assert db.query(College).count() == c_colleges
    assert db.query(Branch).count() == c_branches
    assert db.query(Category).count() == c_categories
    assert db.query(CounsellingRound).count() == c_rounds
    assert db.query(CutoffRecord).count() == c_cutoffs
    assert db.query(SourceVersion).count() == c_sources


def test_api_analytics_endpoints(client):
    """Verify HTTP API endpoints for historical analytics return valid status and schema."""
    resp_cov = client.get("/api/v1/analytics/coverage")
    assert resp_cov.status_code == 200
    data_cov = resp_cov.json()
    assert data_cov["years_available"] == [2023, 2024, 2025, 2026]

    resp_move = client.get("/api/v1/analytics/movement?from_year=2024&to_year=2026&round_scope=R1")
    assert resp_move.status_code == 200
    data_move = resp_move.json()
    assert data_move["aggregate"]["comparability"] == "DIRECT"

    resp_vol = client.get("/api/v1/analytics/volatility/summary?round_scope=TERMINAL")
    assert resp_vol.status_code == 200
    data_vol = resp_vol.json()
    assert "2" in data_vol
    assert "4" in data_vol

    resp_prog = client.get("/api/v1/analytics/progression?academic_year=2026")
    assert resp_prog.status_code == 200

    resp_rec = client.get("/api/v1/analytics/recency?anchor_year=2026&round_scope=R1")
    assert resp_rec.status_code == 200
    data_rec = resp_rec.json()
    assert len(data_rec) == 1
    assert round(data_rec[0]["recent_closer_percentage"], 1) == 74.0

    resp_anom = client.get("/api/v1/analytics/anomalies?limit=10")
    assert resp_anom.status_code == 200

    resp_rep = client.get("/api/v1/analytics/report")
    assert resp_rep.status_code == 200
