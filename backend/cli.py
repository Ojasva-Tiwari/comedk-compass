import argparse
import asyncio
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database import SessionLocal
from backend.app.ingestion.source_registry import SourceRegistryService, OFFICIAL_COMEDK_SOURCES
from backend.app.ingestion.discovery import OfficialSourceDiscovery
from backend.app.ingestion.downloader import DocumentDownloader
from backend.app.ingestion.health import SourceHealthService
from backend.app.ingestion.review_queue import ReviewQueueService
from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.core.enums import ReviewStatus

def cmd_sources(args):
    """List or synchronize registered COMEDK sources."""
    db = SessionLocal()
    try:
        service = SourceRegistryService(db)
        if args.sync:
            print("Synchronizing registered official sources into database...")
            synced = service.sync_registered_sources()
            print(f"Successfully synchronized {len(synced)} official sources.")

        active_sources = service.get_active_sources()
        print("\n" + "=" * 90)
        print(f"{'SOURCE CODE':<32} {'TYPE':<22} {'AUTHORITY':<18} {'FREQUENCY':<10}")
        print("=" * 90)
        for s in active_sources:
            code = s.source_code or s.title[:30]
            print(f"{code:<32} {s.source_type:<22} {s.authority_level:<18} {s.check_frequency_hours}h")
        print("=" * 90)
        print(f"Total Active Sources: {len(active_sources)}\n")
    finally:
        db.close()

async def cmd_discover(args):
    """Discover documents from official COMEDK sources."""
    discovery = OfficialSourceDiscovery(academic_year=args.year)
    print(f"Discovering documents for Academic Year {args.year}...")
    sources = await discovery.discover_all()
    print(f"Discovered {len(sources)} documents across official sources:\n")
    print(f"{'TYPE':<25} {'ROUND':<8} {'TITLE':<45} {'URL'}")
    print("-" * 110)
    for s in sources:
        r = s.counselling_round or "-"
        print(f"{s.document_type:<25} {r:<8} {s.title[:43]:<45} {s.url}")
    print("-" * 110)

async def cmd_download(args):
    """Download and archive a specific document URL or all discovered documents."""
    downloader = DocumentDownloader()
    if args.url:
        print(f"Downloading and archiving {args.url} (Year: {args.year}, Type: {args.type})...")
        try:
            content, chash, lpath, size, ctype = await downloader.download_and_archive(
                url=args.url,
                academic_year=args.year,
                document_type=args.type
            )
            print("Download and Archive Successful:")
            print(f"  SHA-256 Hash: {chash}")
            print(f"  Local Path:   {lpath}")
            print(f"  Size:         {size:,} bytes")
            print(f"  Content-Type: {ctype}")
        except Exception as e:
            print(f"Download failed: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        discovery = OfficialSourceDiscovery(academic_year=args.year)
        sources = await discovery.discover_all()
        print(f"Discovered {len(sources)} documents. Archiving...")
        downloaded = 0
        failed = 0
        for s in sources:
            try:
                _, chash, lpath, size, _ = await downloader.download_and_archive(
                    url=s.url,
                    academic_year=s.academic_year,
                    document_type=s.document_type
                )
                print(f"[OK] {s.document_type:<22} -> {lpath.name} ({chash[:12]}...)")
                downloaded += 1
            except Exception as e:
                print(f"[FAIL] {s.url}: {e}", file=sys.stderr)
                failed += 1
        print(f"\nCompleted: {downloaded} downloaded/verified, {failed} failed.")

def cmd_health(args):
    """Check source freshness and ingestion health telemetry."""
    db = SessionLocal()
    try:
        health_service = SourceHealthService(db)
        report = health_service.get_source_freshness_report()

        print("\n" + "=" * 105)
        print("COMEDK COMPASS - SOURCE FRESHNESS & INGESTION HEALTH REPORT")
        print("=" * 105)
        print(f"{'SOURCE CODE':<32} {'STATUS':<16} {'VERSIONS':<10} {'PENDING':<10} {'LAST CHECKED':<22}")
        print("-" * 105)
        for s in report["sources"]:
            last_chk = s["last_checked_at"][:19] if s["last_checked_at"] else "Never"
            print(f"{s['source_code']:<32} {s['status']:<16} {s['total_versions']:<10} {s['pending_review_count']:<10} {last_chk:<22}")
        print("-" * 105)
        print(f"Total Registered Sources: {report['sources_count']}")
        print(f"Total Pending Review Items: {report['total_pending_reviews']}")
        if report.get("latest_run"):
            lr = report["latest_run"]
            print(f"Latest Ingestion Run: {lr['id']} | Status: {lr['status']} | Published: {lr['published_count']} | Needs Review: {lr['needs_review_count']}")
        print("=" * 105 + "\n")
    finally:
        db.close()

def cmd_review(args):
    """Inspect or manage the review queue for failed/suspicious ingestions."""
    db = SessionLocal()
    try:
        queue = ReviewQueueService(db)
        if args.approve or args.reject:
            target_id = args.approve or args.reject
            new_status = ReviewStatus.APPROVED.value if args.approve else ReviewStatus.REJECTED.value
            item = queue.update_item_status(
                item_id=uuid.UUID(target_id),
                new_status=new_status,
                reviewed_by=args.by or "CLI_OPERATOR",
                notes=args.notes
            )
            if item:
                print(f"Updated item {target_id} status to: {new_status}")
            else:
                print(f"Item {target_id} not found", file=sys.stderr)
                sys.exit(1)
            return

        pending = queue.get_pending_items(limit=args.limit)
        counts = queue.count_by_status()

        print("\n" + "=" * 110)
        print("COMEDK COMPASS - INGESTION REVIEW QUEUE")
        print("=" * 110)
        print(f"Queue Status Summary: {counts}\n")
        if not pending:
            print("No items currently pending review. Pipeline is healthy!\n")
            return

        print(f"{'ID':<38} {'FAILURE REASON':<25} {'DOC TYPE':<22} {'DOCUMENT URL'}")
        print("-" * 110)
        for item in pending:
            print(f"{str(item.id):<38} {item.failure_reason:<25} {item.document_type:<22} {item.document_url[:40]}")
            if item.review_notes:
                print(f"   Notes: {item.review_notes}")
            if item.validation_errors:
                print(f"   Errors: {item.validation_errors[:2]}")
        print("=" * 110 + "\n")
    finally:
        db.close()

async def cmd_run(args):
    """Execute the complete end-to-end safe automated acquisition and publishing pipeline."""
    db = SessionLocal()
    try:
        pipeline = IngestionPipeline(db=db, academic_year=args.year)
        if args.source_version:
            sv_uuid = uuid.UUID(args.source_version)
            print(f"Ingesting specific SourceVersion document: {sv_uuid}...")
            report = pipeline.ingest_source_version(sv_uuid)
            print("\n" + "=" * 60)
            print("SOURCE VERSION INGESTION SUMMARY")
            print("=" * 60)
            for k, v in report.items():
                print(f"  {k:<28}: {v}")
            print("=" * 60)
            return

        print(f"Starting Safe Acquisition & Ingestion Pipeline for Academic Year {args.year}...")
        stats = await pipeline.run(max_cutoff_docs=args.max_docs)
        print("\n" + "=" * 60)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Documents Discovered:      {stats['documents_discovered']}")
        print(f"Documents Downloaded:      {stats['documents_downloaded']}")
        print(f"Documents Already In DB:   {stats['documents_already_archived']}")
        print(f"Documents Parsed:          {stats['documents_parsed']}")
        print(f"Documents Queued Review:   {stats['documents_needs_review']}")
        print(f"Records Parsed:            {stats['records_parsed']}")
        print(f"Records Validated:         {stats['records_validated']}")
        print(f"Records Published:         {stats['records_published']}")
        print(f"Records Queued Review:     {stats['records_needs_review']}")
        print(f"Validation Errors:         {stats['validation_errors']}")
        print(f"Anomalies Flagged:         {stats['anomalies']}")
        print("=" * 60)
    finally:
        db.close()

def cmd_historical_analysis(args):
    """Execute read-only historical cutoff analytics across 2023-2026."""
    from backend.app.analytics.service import HistoricalAnalyticsService
    db = SessionLocal()
    try:
        service = HistoricalAnalyticsService(db)
        sub = args.subcommand or "report"

        if sub == "coverage":
            cov = service.get_coverage_summary()
            print("\n" + "=" * 95)
            print("COMEDK COMPASS - HISTORICAL COVERAGE & RECONCILIATION SUMMARY (2023-2026)")
            print("=" * 95)
            print(f"Academic Years Available:     {cov.years_available}")
            print(f"Total Cutoff Records in DB:    {cov.total_records:,}")
            print(f"Active Published Records:     {cov.published_records:,}")
            print(f"Superseded Historical Records: {cov.superseded_records:,}")
            print("\nRecords by Academic Year (Published vs Total):")
            for yr in cov.years_available:
                pub = cov.records_per_year.get(yr, 0)
                tot = cov.total_records_per_year.get(yr, 0)
                sup = cov.superseded_records_per_year.get(yr, 0)
                colls = cov.colleges_per_year.get(yr, 0)
                brs = cov.branches_per_year.get(yr, 0)
                print(f"  {yr}: {pub:>5} published | {tot:>5} total ({sup} superseded) | {colls:>3} colleges | {brs:>2} branches")

            if cov.excluded_records:
                print(f"\nExact Excluded Records (SUPERSEDED Status, n={len(cov.excluded_records)}):")
                print(f"  {'CUTOFF ID':<38} {'YEAR':<6} {'COLLEGE':<8} {'BRANCH':<8} {'ROUND':<8} {'STATUS':<12} {'RANK'}")
                print("  " + "-" * 90)
                for ex in cov.excluded_records:
                    print(f"  {str(ex.cutoff_id):<38} {ex.academic_year:<6} {ex.college_code:<8} {ex.branch_code:<8} {ex.round_code:<8} {ex.status:<12} {ex.closing_rank}")

            print("\nRecords by Category (Published):")
            for cat, count in cov.records_per_category.items():
                print(f"  {cat:<10}: {count:>6} cutoffs")

            print("\nRecords by Program Type (Published):")
            for prog, count in cov.records_per_program_type.items():
                print(f"  {prog:<15}: {count:>6} cutoffs")

            print("\nLongitudinal Observation Depth (Unique Canonical Combinations):")
            for depth, count in cov.observation_depth_counts.items():
                print(f"  n = {depth}: {count:>5} combinations")

            print("\nTop Observed Year Patterns:")
            for pattern, count in list(cov.years_observed_patterns.items())[:6]:
                print(f"  [{pattern}]: {count:>4} combinations")
            print("=" * 95 + "\n")

        elif sub == "movement":
            items, agg = service.get_yoy_movement(
                from_year=args.from_year,
                to_year=args.to_year,
                round_scope=args.scope,
                program_type=args.program,
                category=args.category,
            )
            print("\n" + "=" * 105)
            print(f"COMEDK COMPASS - YEAR-OVER-YEAR CUTOFF MOVEMENT ({args.from_year} -> {args.to_year})")
            print("=" * 105)
            if not agg:
                print(f"No comparable data found for transition {args.from_year} -> {args.to_year} (Scope: {args.scope})\n")
                return

            print(f"Round Scope:     {args.scope} ({agg.from_round} -> {agg.to_round})")
            print(f"Program Type:    {args.program} | Category: {args.category}")
            print(f"Comparability:   {agg.comparability.value}")
            print(f"Matched Pairs:   {agg.matched_pairs:,}")
            print(f"Median Abs Move: {agg.median_absolute_movement:+.1f} ranks")
            print(f"Mean Abs Move:   {agg.mean_absolute_movement:+.1f} ranks")
            print(f"Median Rel Move: {agg.median_relative_movement:+.2%}")
            print(f"Mean Rel Move:   {agg.mean_relative_movement:+.2%}")
            print(f"Earlier Ranks:   {agg.earlier_numerically_count} (strengthened numerically)")
            print(f"Later Ranks:     {agg.later_numerically_count} (relaxed numerically)")
            print(f"Unchanged:       {agg.unchanged_count}")
            print("-" * 105)
            print(f"{'COLLEGE':<10} {'BRANCH':<10} {'PREV RANK':<12} {'CURR RANK':<12} {'ABS DIFF':<12} {'REL DIFF':<12} {'DIRECTION'}")
            print("-" * 105)
            for it in items[:15]:
                print(f"{it.college_code:<10} {it.branch_code:<10} {it.previous_closing_rank:<12} {it.current_closing_rank:<12} {it.absolute_movement:<+12} {it.relative_movement:<+11.2%} {it.direction.value}")
            if len(items) > 15:
                print(f"  ... and {len(items) - 15} more matched combinations.")
            print("=" * 105 + "\n")

        elif sub == "volatility":
            summaries = service.get_volatility_summary_by_n(
                round_scope=args.scope,
                program_type=args.program,
                category=args.category,
            )
            print("\n" + "=" * 105)
            print(f"COMEDK COMPASS - HISTORICAL VOLATILITY STRATIFIED BY OBSERVATION COUNT (n)")
            print("=" * 105)
            print(f"Scope: {args.scope} | Program: {args.program} | Category: {args.category}")
            print("-" * 105)
            print(f"{'OBS (n)':<10} {'COMBOS':<10} {'MEDIAN CV':<14} {'MEAN CV':<14} {'CV RANGE':<22} {'MEDIAN ABS':<14} {'DATA QUALITY'}")
            print("-" * 105)
            for n, s in summaries.items():
                med_cv = f"{s.median_cv:.2%}" if s.median_cv is not None else "N/A"
                mean_cv = f"{s.mean_cv:.2%}" if s.mean_cv is not None else "N/A"
                cv_range = f"[{s.min_cv:.1%} - {s.max_cv:.1%}]" if s.min_cv is not None and s.max_cv is not None else "N/A"
                med_abs = f"{s.median_absolute_movement:.1f}" if s.median_absolute_movement is not None else "N/A"
                print(f"{n:<10} {s.combination_count:<10} {med_cv:<14} {mean_cv:<14} {cv_range:<22} {med_abs:<14} {s.volatility_data_quality.value}")
            print("=" * 105 + "\n")

        elif sub == "progression":
            progressions = service.get_round_progression(
                academic_year=args.year,
                program_type=args.program,
                category=args.category,
            )
            print("\n" + "=" * 110)
            print(f"COMEDK COMPASS - WITHIN-YEAR ROUND PROGRESSION ({args.year if args.year else 'ALL YEARS'})")
            print("=" * 110)
            print(f"{'YEAR':<6} {'TRANSITION':<22} {'PAIRS':<8} {'MEDIAN ABS':<14} {'MEDIAN REL':<14} {'EARLIER':<10} {'LATER':<10} {'UNCHANGED'}")
            print("-" * 110)
            for p in progressions:
                trans = f"{p.from_round} -> {p.to_round}"
                print(f"{p.academic_year:<6} {trans:<22} {p.matched_pairs:<8} {p.median_absolute_movement:<+14.1f} {p.median_relative_movement:<+14.2%} {p.earlier_numerically_count:<10} {p.later_numerically_count:<10} {p.unchanged_count}")
            print("=" * 110 + "\n")

        elif sub == "recency":
            comparisons = service.get_recency_evidence(
                anchor_year=2026,
                round_scope=args.scope,
                program_type=args.program,
                category=args.category,
            )
            print("\n" + "=" * 110)
            print(f"COMEDK COMPASS - RECENCY DISTANCE EVIDENCE (Anchor Year: 2026, Scope: {args.scope})")
            print("=" * 110)
            for c in comparisons:
                print(f"Program: {c.program_type} | Category: {c.category} | Triples Evaluated: {c.evaluated_triples}")
                print(f"Recent Year: {c.recent_year} | Older Year: {c.older_year}")
                print(f"Recent Closer Count:      {c.recent_closer_count} ({c.recent_closer_percentage:.1f}%)")
                print(f"Older Closer Count:       {c.older_closer_count}")
                print(f"Equal Distance Count:     {c.equal_distance_count}")
                print(f"Recent Median Abs Dist:   {c.recent_median_absolute_distance:.1f} ranks ({c.recent_median_relative_distance:.1%})")
                print(f"Older Median Abs Dist:    {c.older_median_absolute_distance:.1f} ranks ({c.older_median_relative_distance:.1%})")
                diff_pct = ((c.older_median_absolute_distance - c.recent_median_absolute_distance) / c.recent_median_absolute_distance) * 100.0 if c.recent_median_absolute_distance > 0 else 0.0
                print(f"Older Distance Excess:    +{diff_pct:.1f}% larger than recent year")
            print("=" * 110 + "\n")

        elif sub == "anomalies":
            anomalies = service.get_anomalies()
            summary = defaultdict(int)
            for a in anomalies:
                summary[a.anomaly_type.value] += 1
            print("\n" + "=" * 110)
            print("COMEDK COMPASS - FACTUAL DATA ANOMALIES REPORT")
            print("=" * 110)
            for atype, count in summary.items():
                print(f"  {atype:<32}: {count:>5} detected")

            backward = [a for a in anomalies if a.anomaly_type.value == "BACKWARD_ROUND_MOVEMENT"]
            print(f"\nBackward Numerical Round Movement Cases (Sample 10 of {len(backward)}):")
            print("  Direction:   EARLIER_NUMERICALLY")
            print("  Cause:       NOT_DETERMINABLE_FROM_AVAILABLE_DATA")
            print("  Description: Observed closing rank decreased numerically between rounds.")
            print("-" * 110)
            print(f"{'YEAR':<6} {'COLLEGE':<10} {'BRANCH':<10} {'ROUND':<16} {'FROM RANK':<12} {'TO RANK':<12} {'DELTA':<10} {'DIRECTION'}")
            print("-" * 110)
            for b in backward[:10]:
                rnd = f"{b.from_round}->{b.to_round}"
                print(f"{b.academic_year:<6} {b.college_code:<10} {b.branch_code:<10} {rnd:<16} {b.from_rank:<12} {b.to_rank:<12} {b.rank_delta:<+10} {b.direction.value}")
            print("=" * 110 + "\n")

        elif sub == "report":
            rep = service.generate_report()
            cov = rep.coverage
            print("\n" + "=" * 110)
            print("COMEDK COMPASS - COMPLETE HISTORICAL ANALYTICS VALIDATION REPORT (2023-2026)")
            print("=" * 110)
            print(f"Total Published Cutoffs: {cov.total_records:,} across {len(cov.years_available)} years ({cov.years_available})")
            print(f"Records by Year: {dict(cov.records_per_year)}")
            print(f"Observation Depth: {dict(cov.observation_depth_counts)}")

            print("\n--- VOLATILITY STRATIFIED BY OBSERVATION COUNT (TERMINAL SCOPE) ---")
            for n, v in rep.volatility_by_n.items():
                med_cv = f"{v.median_cv:.2%}" if v.median_cv is not None else "N/A"
                print(f"  n={n}: Combos={v.combination_count:<4} | Median CV={med_cv:<8} | Quality={v.volatility_data_quality.value}")

            print("\n--- WITHIN-YEAR ROUND PROGRESSION ---")
            for p in rep.round_progressions:
                print(f"  {p.academic_year} {p.from_round:<12} -> {p.to_round:<18}: Pairs={p.matched_pairs:<4} | Med Abs={p.median_absolute_movement:<+8.1f} | Med Rel={p.median_relative_movement:<+7.1%}")

            print("\n--- YEAR-OVER-YEAR R1 PROGRESSION ---")
            for y in rep.yoy_movements:
                print(f"  {y.transition}: Pairs={y.matched_pairs:<4} | Med Abs={y.median_absolute_movement:<+8.1f} | Med Rel={y.median_relative_movement:<+7.1%} | Earlier={y.earlier_numerically_count} | Later={y.later_numerically_count}")

            print("\n--- RECENCY DISTANCE EVIDENCE (ANCHOR 2026, R1) ---")
            for r in rep.recency_evidence:
                print(f"  Recent Closer: {r.recent_closer_count}/{r.evaluated_triples} ({r.recent_closer_percentage:.1f}%) | Recent Med Dist={r.recent_median_absolute_distance:.1f} | Older Med Dist={r.older_median_absolute_distance:.1f}")

            print(f"\n--- FACTUAL ANOMALIES ---")
            for k, cnt in rep.anomaly_summary.items():
                print(f"  {k}: {cnt}")
            print("=" * 110 + "\n")
        elif sub == "backtest":
            from backend.app.analytics.backtesting import BacktestResearchEngine
            engine = BacktestResearchEngine(db)

            print("\n" + "=" * 110)
            print("COMEDK COMPASS - CHRONOLOGICAL BACKTEST & PREDICTION RESEARCH REPORT")
            print("=" * 110)

            # 1. 2026 R1 Backtest
            res_r1 = engine.run_r1_backtest(target_year=2026, program_type=args.program, category=args.category)
            print(f"\n--- WINDOW 1: {res_r1.window_name} (Program: {res_r1.program_type}, Cat: {res_r1.category}) ---")
            print(f"Train Years: {res_r1.train_years} | Target Year: {res_r1.target_year} | Scope: {res_r1.round_scope}")
            print(f"Total Test Combos: {res_r1.total_test_combinations} | Evaluated (History >= 1): {res_r1.evaluated_combinations} | Cold Start: {res_r1.cold_start_combinations}")
            print(f"Leakage Audit: {'PASSED' if res_r1.leakage_check_passed else 'FAILED'} ({res_r1.leakage_details})")

            print("\nBaseline Point Forecast Accuracy:")
            print(f"  {'MODEL':<35} {'MAE':<12} {'MedAE':<12} {'RMSE':<12} {'MdAPE':<10}")
            print("  " + "-" * 75)
            for mname, m in res_r1.baseline_metrics.items():
                print(f"  {mname:<35} {m.mae:<12.1f} {m.med_ae:<12.1f} {m.rmse:<12.1f} {m.mdape:<10.2%}")

            print("\nPrediction Interval Calibration (Target: 2026 R1):")
            print(f"  {'INTERVAL METHOD':<35} {'COVERAGE':<12} {'MEDIAN WIDTH':<16} {'BELOW (SURPRISE)':<18} {'ABOVE'}")
            print("  " + "-" * 90)
            for iname, im in res_r1.interval_metrics.items():
                print(f"  {iname:<35} {im.coverage:<12.1%} {im.median_width:<16.1f} {im.below_lower_rate:<18.1%} {im.above_upper_rate:.1%}")

            print("\nError Stratification by Prior History Depth (Baseline A - Lag-1):")
            for depth, dm in sorted(res_r1.depth_breakdown.items()):
                print(f"  Depth n_prior={depth}: N={dm.sample_size:<4} | MAE={dm.mae:<8.1f} | MedAE={dm.med_ae:<8.1f} | MdAPE={dm.mdape:.2%}")

            # 2. 2026 Terminal Backtest
            res_term = engine.run_terminal_backtest(target_year=2026, program_type=args.program, category=args.category)
            print(f"\n--- WINDOW 2: {res_term.window_name} (Program: {res_term.program_type}, Cat: {res_term.category}) ---")
            print(f"Train Years: {res_term.train_years} | Target Year: {res_term.target_year} | Scope: {res_term.round_scope}")
            print(f"Total Test Combos: {res_term.total_test_combinations} | Evaluated (History >= 1): {res_term.evaluated_combinations} | Cold Start: {res_term.cold_start_combinations}")

            print("\nBaseline Point Forecast Accuracy:")
            print(f"  {'MODEL':<35} {'MAE':<12} {'MedAE':<12} {'RMSE':<12} {'MdAPE':<10}")
            print("  " + "-" * 75)
            for mname, m in res_term.baseline_metrics.items():
                print(f"  {mname:<35} {m.mae:<12.1f} {m.med_ae:<12.1f} {m.rmse:<12.1f} {m.mdape:<10.2%}")

            print("\nPrediction Interval Calibration (Target: 2026 Terminal):")
            print(f"  {'INTERVAL METHOD':<35} {'COVERAGE':<12} {'MEDIAN WIDTH':<16} {'BELOW (SURPRISE)':<18} {'ABOVE'}")
            print("  " + "-" * 90)
            for iname, im in res_term.interval_metrics.items():
                print(f"  {iname:<35} {im.coverage:<12.1%} {im.median_width:<16.1f} {im.below_lower_rate:<18.1%} {im.above_upper_rate:.1%}")

            # 3. Vacancy & Secondary Feature Utility
            vac = engine.evaluate_vacancy_feature_utility()
            print(f"\n--- SECONDARY FEATURE: SEAT INTAKE & VACANCY UTILITY ---")
            print(f"Sample Size Evaluated: {vac.get('sample_size')}")
            print(f"Correlation (Total Seats -> Prediction Error): r = {vac.get('correlation_seats_to_prediction_error')}")
            print(f"Correlation (Total Seats -> Closing Rank):       r = {vac.get('correlation_seats_to_closing_rank')}")
            print(f"Utility Finding: {vac.get('utility_assessment')}")
            print(f"Detail: {vac.get('explanation')}")
            print("=" * 110 + "\n")

    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(
        prog="comedk-cli",
        description="COMEDK Compass - Operational & Automated Data Acquisition CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sources
    p_sources = subparsers.add_parser("sources", help="List or sync registered sources")
    p_sources.add_argument("--sync", action="store_true", help="Sync official sources into DB")

    # discover
    p_discover = subparsers.add_parser("discover", help="Discover documents from official sources")
    p_discover.add_argument("--year", type=int, default=2026, help="Academic year (default: 2026)")

    # download
    p_download = subparsers.add_parser("download", help="Download and archive documents")
    p_download.add_argument("--url", type=str, help="Specific URL to download")
    p_download.add_argument("--year", type=int, default=2026, help="Academic year")
    p_download.add_argument("--type", type=str, default="CUTOFF_PDF", help="Document type")

    # health
    p_health = subparsers.add_parser("health", help="Check source freshness and health telemetry")

    # review
    p_review = subparsers.add_parser("review", help="Inspect and manage review queue items")
    p_review.add_argument("--limit", type=int, default=50, help="Max items to list")
    p_review.add_argument("--approve", type=str, help="UUID of item to approve")
    p_review.add_argument("--reject", type=str, help="UUID of item to reject")
    p_review.add_argument("--by", type=str, default="OPERATOR", help="Reviewer name")
    p_review.add_argument("--notes", type=str, help="Review notes")

    # run
    p_run = subparsers.add_parser("run", help="Run complete ingestion pipeline")
    p_run.add_argument("--year", type=int, default=2026, help="Academic year")
    p_run.add_argument("--max-docs", type=int, default=None, help="Max cutoff documents to process")
    p_run.add_argument("--source-version", type=str, default=None, help="UUID of specific SourceVersion to ingest")

    # historical-analysis
    p_analysis = subparsers.add_parser("historical-analysis", help="Historical cutoff analytics and empirical validation")
    p_analysis.add_argument(
        "subcommand",
        nargs="?",
        default="report",
        choices=["coverage", "movement", "volatility", "progression", "recency", "anomalies", "report", "backtest"],
        help="Analytics subcommand (default: report)"
    )
    p_analysis.add_argument("--scope", type=str, default="R1", help="Round scope (R1, TERMINAL, MOCK, etc.)")
    p_analysis.add_argument("--from-year", type=int, default=2024, help="From academic year for YoY movement")
    p_analysis.add_argument("--to-year", type=int, default=2026, help="To academic year for YoY movement")
    p_analysis.add_argument("--year", type=int, default=2026, help="Academic year for round progression")
    p_analysis.add_argument("--program", type=str, default="ENGINEERING", help="Program type (ENGINEERING, ARCHITECTURE)")
    p_analysis.add_argument("--category", type=str, default="GM", help="Category code (GM, KKR)")

    args = parser.parse_args()

    if args.command == "sources":
        cmd_sources(args)
    elif args.command == "discover":
        asyncio.run(cmd_discover(args))
    elif args.command == "download":
        asyncio.run(cmd_download(args))
    elif args.command == "health":
        cmd_health(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "run":
        asyncio.run(cmd_run(args))
    elif args.command == "historical-analysis":
        cmd_historical_analysis(args)

if __name__ == "__main__":
    main()
