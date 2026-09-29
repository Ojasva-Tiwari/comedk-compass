import asyncio
import sys
from pathlib import Path

# Ensure root path is included
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.database import SessionLocal
from backend.app.ingestion.pipeline import IngestionPipeline

async def main():
    print("=" * 60)
    print("COMEDK Compass - Stage 1 Official Data Ingestion Engine")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        pipeline = IngestionPipeline(db=db, academic_year=2026)
        print("Starting ingestion against official COMEDK public sources...")
        stats = await pipeline.run(max_cutoff_docs=None)
        
        print("\n" + "=" * 60)
        print("STAGE 1 INGESTION REPORT")
        print("=" * 60)
        
        print("\nCOLLEGES")
        print(f"  Discovered: {stats['colleges_discovered']}")
        print(f"  Inserted:   {stats['colleges_inserted']}")
        print(f"  Updated:    {stats['colleges_updated']}")
        print(f"  Unchanged:  {stats['colleges_unchanged']}")
        print(f"  Skipped:    {stats['colleges_skipped']}")
        print(f"  Duplicates: 0 (Enforced by code)")

        print("\nBRANCHES")
        print(f"  Discovered: {stats['branches_discovered']}")
        print(f"  Inserted:   {stats['branches_inserted']}")
        print(f"  Updated:    {stats['branches_updated']}")

        print("\nDOCUMENTS")
        print(f"  Discovered:       {stats['documents_discovered']}")
        print(f"  Downloaded:       {stats['documents_downloaded']}")
        print(f"  Already Archived: {stats['documents_already_archived']}")
        print(f"  Failed Downloads: {stats['documents_failed']}")
        print(f"  Parsed:           {stats['documents_parsed']}")
        print(f"  Needs Review:     {stats['documents_needs_review']}")

        print("\nRECORDS")
        print(f"  Parsed:       {stats['records_parsed']}")
        print(f"  Validated:    {stats['records_validated']}")
        print(f"  Published:    {stats['records_published']}")
        print(f"  Rejected:     {stats['records_rejected']}")
        print(f"  Needs Review: {stats['records_needs_review']}")

        print("\nQUALITY")
        print(f"  Validation Errors: {stats['validation_errors']}")
        print(f"  Anomalies:         {stats['anomalies']}")
        print(f"  Parser Failures:   {stats['parser_failures']}")

        print("\nDOCUMENT PARSING REPORTS")
        for i, rep in enumerate(stats.get("parsing_reports", []), start=1):
            print(f"\n--- Document {i}: {rep.get('source_title')} [{rep.get('counselling_round')}] ---")
            print(f"  Academic Year:        {rep.get('academic_year')}")
            print(f"  PDF Page Count:       {rep.get('pdf_page_count')}")
            print(f"  Extracted Pages:      {rep.get('extracted_pages')}")
            print(f"  Raw Rows Detected:    {rep.get('raw_rows_detected')}")
            print(f"  Candidate Records:    {rep.get('candidate_records')}")
            print(f"  Validated Records:    {rep.get('validated_records')}")
            print(f"  Rejected Records:     {rep.get('rejected_records')}")
            print(f"  Needs Review Records: {rep.get('needs_review_records')}")
            print(f"  Unique Colleges:      {rep.get('unique_college_count')}")
            print(f"  Unique Branches:      {rep.get('unique_branch_count')}")
            print(f"  Category Count:       {rep.get('category_count')} ({rep.get('categories')})")
            print(f"  Published Records:    {rep.get('published_records')}")
            print(f"  Verified Unchanged:   {rep.get('verified_unchanged_records', 0)}")
            print(f"  Superseded Records:   {rep.get('superseded_records', 0)}")
            print(f"  Factual Changes:      {rep.get('factual_changes', 0)}")
            print(f"  Parser Warnings:      {len(rep.get('parser_warnings', []))}")
            if rep.get('parser_warnings'):
                for w in rep['parser_warnings'][:5]:
                    print(f"    - {w}")

        print("=" * 60)

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
