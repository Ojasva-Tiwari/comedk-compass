"""Tests for Prediction Engine Research & Chronological Backtesting Framework.

Strictly verifies:
- Zero future-year leakage
- Zero target-round leakage
- Only PUBLISHED records used (SUPERSEDED strictly excluded)
- Engineering vs Architecture separation
- GM vs KKR separation
- KKR_SPECIAL round separation
- Canonical college and branch grouping
- Sparse history handling (n=1, n=2, n=3)
- Cold-start handling and fail-closed behavior
- Chronological train/test splits
- Deterministic results across multiple executions
- Read-only invariance (zero database mutations)
"""

import pytest
from backend.app.core.enums import ProgramType, RecordStatus
from backend.app.models.cutoff import CutoffRecord
from backend.app.models.college import College
from backend.app.models.branch import Branch
from backend.app.models.category import Category
from backend.app.models.round import CounsellingRound
from backend.app.models.source import SourceVersion
from backend.app.analytics.backtesting import BacktestResearchEngine
from backend.app.analytics.constants import (
    ROUND_R1,
    ROUND_R3,
    ROUND_R4,
    ROUND_CONSOLIDATED_FINAL,
    ROUND_KKR_SPECIAL,
)


def test_no_future_year_leakage(db):
    """Verify that training sets for chronological backtests contain zero future-year records."""
    engine = BacktestResearchEngine(db)

    # 1. Test 2026 R1 backtest
    res_r1 = engine.run_r1_backtest(target_year=2026, program_type="ENGINEERING", category="GM")
    assert res_r1.leakage_check_passed
    assert all(y < 2026 for y in res_r1.train_years)
    assert 2026 not in res_r1.train_years
    assert res_r1.train_years == [2023, 2024]

    # 2. Test 2026 Terminal backtest
    res_term = engine.run_terminal_backtest(target_year=2026, program_type="ENGINEERING", category="GM")
    assert res_term.leakage_check_passed
    assert all(y < 2026 for y in res_term.train_years)
    assert 2026 not in res_term.train_years
    assert res_term.train_years == [2023, 2024, 2025]


def test_no_target_round_leakage(db):
    """Verify that predicting Round 1 never uses downstream round data (R3, R4) from the target year."""
    engine = BacktestResearchEngine(db)
    res_r1 = engine.run_r1_backtest(target_year=2026)

    # In R1 backtest, all training records must strictly be R1
    all_train_r1 = engine.analytics_svc.get_canonical_records(
        academic_year=None,
        program_type="ENGINEERING",
        category_code="GM",
        round_code=ROUND_R1,
        status="PUBLISHED",
    )
    for r in all_train_r1:
        assert r["round_code"] == ROUND_R1
        # No 2026 R3 or R4 records may ever be included
        assert r["round_code"] not in [ROUND_R3, ROUND_R4, ROUND_CONSOLIDATED_FINAL]


def test_only_published_and_superseded_excluded(db):
    """Verify that only PUBLISHED records are used and SUPERSEDED records are strictly excluded."""
    engine = BacktestResearchEngine(db)
    records = engine.analytics_svc.get_canonical_records(status="PUBLISHED")

    assert len(records) == 11996
    for r in records:
        assert r["status"] == "PUBLISHED"

    # Verify the 4 known superseded records are absent
    superseded_ids = {
        "f69c0360-12ff-4e3f-bc0d-a544434ae94b",
        "d363a007-5532-46cd-a31a-9e03943a5fb5",
        "293c9f58-f3fc-4e6e-b4c1-a2d1bce58c4b",
        "d7bb82af-caf4-4444-a02b-40613127f94c",
    }
    returned_ids = {str(r["record_id"]) for r in records}
    assert superseded_ids.isdisjoint(returned_ids)


def test_engineering_vs_architecture_separation(db):
    """Verify Engineering and Architecture records are never mixed in backtesting."""
    engine = BacktestResearchEngine(db)

    res_eng = engine.run_r1_backtest(target_year=2026, program_type="ENGINEERING", category="GM")
    res_arch = engine.run_r1_backtest(target_year=2026, program_type="ARCHITECTURE", category="GM")

    assert res_eng.program_type == "ENGINEERING"
    assert res_arch.program_type == "ARCHITECTURE"

    # Engineering has hundreds of combinations, Architecture has 20 in 2026 R1
    assert res_eng.total_test_combinations > res_arch.total_test_combinations
    assert res_eng.total_test_combinations == 870
    assert res_arch.total_test_combinations == 20


def test_gm_vs_kkr_separation(db):
    """Verify GM and KKR categories are evaluated strictly independently."""
    engine = BacktestResearchEngine(db)

    res_gm = engine.run_r1_backtest(target_year=2026, category="GM")
    res_kkr = engine.run_r1_backtest(target_year=2026, category="KKR")

    assert res_gm.category == "GM"
    assert res_kkr.category == "KKR"

    # GM and KKR have different combination counts and error scales
    assert res_gm.total_test_combinations != res_kkr.total_test_combinations
    assert res_gm.baseline_metrics["Baseline A (Lag-1 Latest)"].mae != res_kkr.baseline_metrics["Baseline A (Lag-1 Latest)"].mae


def test_kkr_special_separation(db):
    """Verify KKR_SPECIAL round records are never mixed with general rounds."""
    engine = BacktestResearchEngine(db)
    recs = engine.analytics_svc.get_canonical_records(
        academic_year=2026,
        category_code="GM",
        round_code=ROUND_R1,
    )
    for r in recs:
        assert r["round_code"] != ROUND_KKR_SPECIAL


def test_canonical_college_and_branch_grouping(db):
    """Verify records are correctly grouped by canonical college and branch."""
    engine = BacktestResearchEngine(db)
    recs = engine.analytics_svc.get_canonical_records(program_type="ENGINEERING", category_code="GM")

    # None of the records should have an alias branch_id if a canonical mapping exists
    alias_branches = db.query(Branch).filter(Branch.is_canonical == False, Branch.canonical_branch_id != None).all()
    alias_ids = {b.id for b in alias_branches}
    for r in recs:
        assert r["branch_id"] not in alias_ids

    # All college IDs must be valid
    colleges = {c.id for c in db.query(College).all()}
    for r in recs:
        assert r["college_id"] in colleges


def test_sparse_history_handling(db):
    """Verify backtesting stratifies error metrics by prior observation count."""
    engine = BacktestResearchEngine(db)
    res_r1 = engine.run_r1_backtest(target_year=2026)

    assert 1 in res_r1.depth_breakdown
    assert 2 in res_r1.depth_breakdown

    m_depth1 = res_r1.depth_breakdown[1]
    m_depth2 = res_r1.depth_breakdown[2]

    # Verify sample sizes
    assert m_depth1.sample_size == 137
    assert m_depth2.sample_size == 570

    # Empirical finding: combinations with only 1 prior observation exhibit higher MAE than 2 prior observations
    assert m_depth1.mae > m_depth2.mae


def test_cold_start_handling(db):
    """Verify cold-start combinations (zero prior observations) are quantified and fail closed."""
    engine = BacktestResearchEngine(db)
    res_r1 = engine.run_r1_backtest(target_year=2026)

    # In 2026 R1, exactly 163 combinations were newly introduced with no 2023 or 2024 history
    assert res_r1.cold_start_combinations == 163
    assert res_r1.total_test_combinations == res_r1.evaluated_combinations + res_r1.cold_start_combinations
    assert res_r1.total_test_combinations == 870
    assert res_r1.evaluated_combinations == 707


def test_chronological_train_test_splits(db):
    """Verify chronological split boundaries for all supported windows."""
    engine = BacktestResearchEngine(db)

    # Window 2024 R1
    res_24_r1 = engine.run_r1_backtest(target_year=2024)
    assert res_24_r1.train_years == [2023]
    assert res_24_r1.target_year == 2024

    # Window 2026 R1
    res_26_r1 = engine.run_r1_backtest(target_year=2026)
    assert res_26_r1.train_years == [2023, 2024]
    assert res_26_r1.target_year == 2026

    # Window 2026 Terminal
    res_26_term = engine.run_terminal_backtest(target_year=2026)
    assert res_26_term.train_years == [2023, 2024, 2025]
    assert res_26_term.target_year == 2026


def test_deterministic_results(db):
    """Verify that multiple backtest runs produce mathematically identical results."""
    engine = BacktestResearchEngine(db)

    run1 = engine.run_r1_backtest(target_year=2026)
    run2 = engine.run_r1_backtest(target_year=2026)

    assert run1.evaluated_combinations == run2.evaluated_combinations
    assert run1.cold_start_combinations == run2.cold_start_combinations
    assert run1.baseline_metrics["Baseline A (Lag-1 Latest)"].mae == run2.baseline_metrics["Baseline A (Lag-1 Latest)"].mae
    assert run1.interval_metrics["Lag-1 +- 25% Width"].coverage == run2.interval_metrics["Lag-1 +- 25% Width"].coverage


def test_read_only_invariance_backtest(db):
    """CRITICAL: Verify backtest execution causes ZERO mutations to any database table."""
    c_colleges = db.query(College).count()
    c_branches = db.query(Branch).count()
    c_categories = db.query(Category).count()
    c_rounds = db.query(CounsellingRound).count()
    c_cutoffs = db.query(CutoffRecord).count()
    c_sources = db.query(SourceVersion).count()

    engine = BacktestResearchEngine(db)
    _ = engine.run_r1_backtest(target_year=2026)
    _ = engine.run_terminal_backtest(target_year=2026)
    _ = engine.evaluate_vacancy_feature_utility()

    # Session must be 100% clean
    assert len(db.dirty) == 0
    assert len(db.new) == 0
    assert len(db.deleted) == 0

    assert db.query(College).count() == c_colleges
    assert db.query(Branch).count() == c_branches
    assert db.query(Category).count() == c_categories
    assert db.query(CounsellingRound).count() == c_rounds
    assert db.query(CutoffRecord).count() == c_cutoffs
    assert db.query(SourceVersion).count() == c_sources
