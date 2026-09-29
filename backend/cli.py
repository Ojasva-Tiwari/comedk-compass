import argparse
import asyncio
import sys
import uuid
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

if __name__ == "__main__":
    main()
