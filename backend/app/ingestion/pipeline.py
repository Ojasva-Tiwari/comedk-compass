import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from bs4 import BeautifulSoup
from backend.app.config import settings
from backend.app.core.enums import (
    RecordStatus,
    DocumentType,
    RunStatus,
    ValidationSeverity,
    InstitutionType,
    ProgramType,
    FailureReason,
    ReviewStatus,
)
from backend.app.models import (
    IngestionRun,
    Source,
    SourceVersion,
    College,
    CollegeAlias,
    Branch,
    CollegeBranch,
    Category,
    CounsellingRound,
    CutoffRecord,
    SeatRecord,
    FeeRecord,
    ValidationError,
    IngestionReviewItem,
)
from backend.app.ingestion.archiver import DocumentArchiver
from backend.app.ingestion.downloader import DocumentDownloader, DownloaderError, CorruptDocumentError
from backend.app.ingestion.discovery import OfficialSourceDiscovery, DiscoveredSource
from backend.app.ingestion.normalizer import Normalizer
from backend.app.ingestion.source_registry import SourceRegistryService
from backend.app.ingestion.parsers.registry import ParserRegistry, NoParserAvailableError
from backend.app.ingestion.review_queue import ReviewQueueService
from backend.app.ingestion.health import SourceHealthService
from backend.app.ingestion.classifier import DocumentClassifier
from backend.app.ingestion.validator import DataValidator, ValidationErrorItem

class IngestionPipeline:
    def __init__(self, db: Session, academic_year: int = 2026):
        self.db = db
        self.academic_year = academic_year
        self.archiver = DocumentArchiver()
        self.downloader = DocumentDownloader()
        self.source_registry = SourceRegistryService(db)
        self.discovery = OfficialSourceDiscovery(academic_year=academic_year)
        self.parser_registry = ParserRegistry()
        self.college_parser = self.parser_registry.get_parser(DocumentType.MEMBER_INSTITUTIONS_HTML.value)
        self.cutoff_parser = self.parser_registry.get_parser(DocumentType.CUTOFF_PDF.value)
        self.seat_fee_parser = self.parser_registry.get_parser(DocumentType.SEAT_MATRIX_PDF.value)
        self.review_queue = ReviewQueueService(db)
        self.health = SourceHealthService(db)

    def _seed_base_reference_data(self) -> Tuple[Dict[str, Category], Dict[str, CounsellingRound]]:
        # Seed standard categories
        standard_categories = [
            ("GM", "General Merit", "Unreserved Karnataka and non-Karnataka open quota"),
            ("KKR", "Kalyana Karnataka Region", "Hyderabad-Karnataka quota under Article 371J"),
            ("HKR", "Hyderabad Karnataka Region", "Legacy Hyderabad-Karnataka reservation quota"),
        ]
        cat_map: Dict[str, Category] = {}
        for code, name, desc in standard_categories:
            cat = self.db.execute(select(Category).where(Category.code == code)).scalar_one_or_none()
            if not cat:
                cat = Category(code=code, name=name, description=desc)
                self.db.add(cat)
                self.db.flush()
            cat_map[code] = cat

        # Seed counselling rounds
        standard_rounds = [
            ("MOCK", "Mock Round", 0),
            ("R1", "Round 1", 1),
            ("R2", "Round 2", 2),
            ("R3", "Round 3", 3),
            ("R4", "Round 4", 4),
        ]
        round_map: Dict[str, CounsellingRound] = {}
        for yr in (self.academic_year, 2025):
            for code, name, num in standard_rounds:
                rnd = self.db.execute(
                    select(CounsellingRound).where(
                        CounsellingRound.academic_year == yr,
                        CounsellingRound.code == code
                    )
                ).scalar_one_or_none()
                if not rnd:
                    rnd = CounsellingRound(
                        code=code,
                        name=name,
                        academic_year=yr,
                        round_number=num
                    )
                    self.db.add(rnd)
                    self.db.flush()
                if yr == self.academic_year:
                    round_map[code] = rnd

        self.db.commit()
        return cat_map, round_map

    async def run(self, max_cutoff_docs: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes complete ingestion pipeline.
        If max_cutoff_docs is None, processes all discovered official cutoff documents.
        """
        started_at = datetime.now(timezone.utc)
        run_record = IngestionRun(
            started_at=started_at,
            status=RunStatus.RUNNING.value,
            parser_version=settings.PARSER_VERSION
        )
        self.db.add(run_record)
        self.db.commit()
        self.db.refresh(run_record)

        stats = {
            "colleges_discovered": 0,
            "colleges_inserted": 0,
            "colleges_updated": 0,
            "colleges_unchanged": 0,
            "colleges_skipped": 0,
            "branches_discovered": 0,
            "branches_inserted": 0,
            "branches_updated": 0,
            "documents_discovered": 0,
            "documents_downloaded": 0,
            "documents_already_archived": 0,
            "documents_failed": 0,
            "documents_parsed": 0,
            "documents_needs_review": 0,
            "records_parsed": 0,
            "records_validated": 0,
            "records_published": 0,
            "records_rejected": 0,
            "records_needs_review": 0,
            "validation_errors": 0,
            "anomalies": 0,
            "parser_failures": 0,
            "parsing_reports": [],
        }

        try:
            cat_map, round_map = self._seed_base_reference_data()

            # 0. Sync registered official sources
            self.source_registry.sync_registered_sources()

            # 1. Official Source Discovery
            discovered_sources: List[DiscoveredSource] = await self.discovery.discover_all()
            stats["documents_discovered"] = len(discovered_sources)

            # Prioritize HTML college sources first
            html_sources = [s for s in discovered_sources if "HTML" in s.document_type]
            cutoff_sources = [s for s in discovered_sources if s.document_type == DocumentType.CUTOFF_PDF.value]
            seat_fee_sources = [s for s in discovered_sources if s.document_type in (DocumentType.SEAT_MATRIX_PDF.value, DocumentType.FEE_STRUCTURE_PDF.value)]

            # Order cutoffs: 2026 Engineering cutoffs sorted by round: MOCK -> R1 -> R2 -> R3 -> R4, then Architecture
            round_order = {"MOCK": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}
            eng_cutoffs = [
                s for s in cutoff_sources
                if "architecture" not in s.title.lower() and "architecture" not in s.url.lower() and s.academic_year == self.academic_year
            ]
            eng_cutoffs.sort(key=lambda s: round_order.get(s.counselling_round or "", 99))

            other_cutoffs = [s for s in cutoff_sources if s not in eng_cutoffs]

            all_cutoffs = eng_cutoffs + other_cutoffs
            if max_cutoff_docs is not None and max_cutoff_docs > 0:
                ordered_cutoff_sources = all_cutoffs[:max_cutoff_docs]
            else:
                ordered_cutoff_sources = all_cutoffs

            ordered_sources = html_sources + seat_fee_sources + ordered_cutoff_sources
            stats["documents_discovered"] = len(ordered_sources)

            for disc in ordered_sources:
                try:
                    # Upsert / sync Source registry record
                    source_db = self.db.execute(select(Source).where(Source.url == disc.url)).scalar_one_or_none()
                    if not source_db:
                        source_db = Source(
                            source_code=f"DISC_{disc.academic_year}_{disc.document_type}_{uuid.uuid4().hex[:6]}",
                            source_type="OFFICIAL_DISCOVERED",
                            url=disc.url,
                            title=disc.title,
                            publisher=disc.publisher,
                            document_type=disc.document_type,
                            academic_year=disc.academic_year,
                            is_enabled=True,
                            parser_version=settings.PARSER_VERSION
                        )
                        self.db.add(source_db)
                        self.db.flush()

                    # Record source check
                    self.source_registry.record_check(source_db.id)

                    # Download and archive with safe DocumentDownloader
                    try:
                        content, content_hash, local_path, file_size, content_type = await self.downloader.download_and_archive(
                            url=disc.url,
                            academic_year=disc.academic_year,
                            document_type=disc.document_type
                        )
                        stats["documents_downloaded"] += 1
                        self.source_registry.record_success(source_db.id, content_hash=content_hash)
                    except CorruptDocumentError as cde:
                        stats["documents_failed"] += 1
                        stats["parser_failures"] += 1
                        self._record_error(
                            run_id=run_record.id,
                            source_version_id=None,
                            entity_type="SOURCE",
                            entity_id=disc.url,
                            code="CORRUPT_DOCUMENT",
                            msg=str(cde),
                            severity=ValidationSeverity.CRITICAL.value
                        )
                        self.review_queue.add_review_item(
                            source_id=source_db.id,
                            document_type=disc.document_type,
                            document_url=disc.url,
                            failure_reason=FailureReason.CORRUPT_DOCUMENT.value,
                            ingestion_run_id=run_record.id,
                            parser_version=settings.PARSER_VERSION,
                            review_notes=str(cde)
                        )
                        continue
                    except DownloaderError as de:
                        stats["documents_failed"] += 1
                        stats["parser_failures"] += 1
                        self._record_error(
                            run_id=run_record.id,
                            source_version_id=None,
                            entity_type="SOURCE",
                            entity_id=disc.url,
                            code="DOWNLOAD_FAILED",
                            msg=str(de),
                            severity=ValidationSeverity.ERROR.value
                        )
                        self.review_queue.add_review_item(
                            source_id=source_db.id,
                            document_type=disc.document_type,
                            document_url=disc.url,
                            failure_reason=FailureReason.DOWNLOAD_FAILED.value,
                            ingestion_run_id=run_record.id,
                            parser_version=settings.PARSER_VERSION,
                            review_notes=str(de)
                        )
                        continue
                    except Exception as e:
                        stats["documents_failed"] += 1
                        stats["parser_failures"] += 1
                        self._record_error(
                            run_id=run_record.id,
                            source_version_id=None,
                            entity_type="SOURCE",
                            entity_id=disc.url,
                            code="DOWNLOAD_UNEXPECTED_ERROR",
                            msg=f"Failed to download {disc.url}: {e}",
                            severity=ValidationSeverity.ERROR.value
                        )
                        self.review_queue.add_review_item(
                            source_id=source_db.id,
                            document_type=disc.document_type,
                            document_url=disc.url,
                            failure_reason=FailureReason.DOWNLOAD_FAILED.value,
                            ingestion_run_id=run_record.id,
                            parser_version=settings.PARSER_VERSION,
                            review_notes=f"Unexpected download failure: {e}"
                        )
                        continue

                    # Document type detection / normalization
                    detected_type = disc.document_type
                    if detected_type in (DocumentType.OTHER.value, DocumentType.UNKNOWN.value):
                        classified_type, classified_round = DocumentClassifier.classify_with_round(f"{disc.title} {disc.url}")
                        detected_type = classified_type
                        if classified_round and not disc.counselling_round:
                            disc.counselling_round = classified_round

                    # Upsert SourceVersion record
                    sv = self.db.execute(
                        select(SourceVersion).where(
                            SourceVersion.source_id == source_db.id,
                            SourceVersion.content_hash == content_hash
                        )
                    ).scalar_one_or_none()

                    if not sv:
                        sv = SourceVersion(
                            source_id=source_db.id,
                            ingestion_run_id=run_record.id,
                            source_url=disc.url,
                            source_title=disc.title,
                            publisher=disc.publisher,
                            academic_year=disc.academic_year,
                            document_type=detected_type,
                            counselling_round=disc.counselling_round,
                            publication_date=disc.publication_date,
                            content_hash=content_hash,
                            local_path=str(local_path),
                            file_size_bytes=file_size,
                            content_type=content_type,
                            parser_version=settings.PARSER_VERSION,
                            processing_status=RecordStatus.DOWNLOADED.value
                        )
                        self.db.add(sv)
                        self.db.flush()
                    else:
                        stats["documents_already_archived"] += 1

                    # Check parser availability from ParserRegistry
                    if not self.parser_registry.has_parser(detected_type) and detected_type != DocumentType.COUNSELLING_PORTAL_HTML.value:
                        stats["documents_needs_review"] += 1
                        sv.processing_status = RecordStatus.NEEDS_REVIEW.value
                        self.review_queue.add_review_item(
                            source_id=source_db.id,
                            source_version_id=sv.id,
                            document_type=detected_type,
                            document_url=disc.url,
                            failure_reason=FailureReason.UNSUPPORTED_DOCUMENT_TYPE.value,
                            ingestion_run_id=run_record.id,
                            parser_version=settings.PARSER_VERSION,
                            review_notes=f"No parser available for detected document type '{detected_type}'"
                        )
                        self.db.commit()
                        continue

                    # 2. Parse depending on document type
                    if detected_type in (DocumentType.MEMBER_INSTITUTIONS_HTML.value, DocumentType.BE_COLLEGES_HTML.value):
                        parser = self.parser_registry.get_parser(detected_type)
                        parse_res = parser.parse(content)
                        stats["documents_parsed"] += 1
                        self._ingest_colleges(parse_res.discovered_colleges, sv.id, stats)

                    elif detected_type == DocumentType.COUNSELLING_PORTAL_HTML.value:
                        official_branches = self._extract_branches_from_counselling_portal(content)
                        stats["documents_parsed"] += 1
                        if official_branches:
                            self._ingest_branches(official_branches, stats)

                    elif detected_type in (DocumentType.SEAT_MATRIX_PDF.value, DocumentType.FEE_STRUCTURE_PDF.value, DocumentType.VACANT_SEATS_PDF.value):
                        parser = self.parser_registry.get_parser(detected_type)
                        parse_res = parser.parse(content, {"academic_year": disc.academic_year})
                        stats["documents_parsed"] += 1
                        if parse_res.discovered_branches:
                            self._ingest_branches(parse_res.discovered_branches, stats)
                        if parse_res.discovered_colleges:
                            self._ingest_colleges(parse_res.discovered_colleges, sv.id, stats)
                        self._ingest_seat_and_fee_records(parse_res, sv.id, stats)

                    elif detected_type == DocumentType.CUTOFF_PDF.value:
                        parser = self.parser_registry.get_parser(detected_type)
                        parse_res = parser.parse(content, {
                            "academic_year": disc.academic_year,
                            "counselling_round": disc.counselling_round or "R1"
                        })
                        stats["documents_parsed"] += 1

                        if not parse_res.is_usable_text:
                            stats["documents_needs_review"] += 1
                            sv.processing_status = RecordStatus.NEEDS_REVIEW.value
                            self.review_queue.add_review_item(
                                source_id=source_db.id,
                                source_version_id=sv.id,
                                document_type=detected_type,
                                document_url=disc.url,
                                failure_reason=FailureReason.SCANNED_PDF.value,
                                ingestion_run_id=run_record.id,
                                parser_version=settings.PARSER_VERSION,
                                review_notes="PDF has non-extractable text (scanned or image-based); manual review or OCR required."
                            )
                            self.db.commit()
                            continue

                        # Register any newly discovered branches & colleges from the cutoff PDF
                        if parse_res.discovered_branches:
                            self._ingest_branches(parse_res.discovered_branches, stats)
                        if parse_res.discovered_colleges:
                            self._ingest_colleges(parse_res.discovered_colleges, sv.id, stats)

                        # Validate and persist cutoffs
                        doc_report = self._ingest_cutoff_records(
                            parse_res=parse_res,
                            sv=sv,
                            cat_map=cat_map,
                            round_map=round_map,
                            run_id=run_record.id,
                            stats=stats
                        )
                        stats["parsing_reports"].append(doc_report)

                    if sv.processing_status != RecordStatus.NEEDS_REVIEW.value:
                        sv.processing_status = RecordStatus.PUBLISHED.value
                    self.db.commit()

                except Exception as e:
                    stats["parser_failures"] += 1
                    self.db.rollback()
                    self._record_error(
                        run_id=run_record.id,
                        source_version_id=None,
                        entity_type="PIPELINE",
                        entity_id=disc.url,
                        code="UNHANDLED_SOURCE_ERROR",
                        msg=f"Error processing source {disc.url}: {e}",
                        severity=ValidationSeverity.ERROR.value
                    )

            # Finalize Run Record
            finished_at = datetime.now(timezone.utc)
            run_record.finished_at = finished_at
            run_record.status = RunStatus.SUCCESS.value if stats["parser_failures"] == 0 else RunStatus.PARTIAL_SUCCESS.value
            run_record.source_count = stats["documents_discovered"]
            run_record.downloaded_count = stats["documents_downloaded"]
            run_record.parsed_count = stats["documents_parsed"]
            run_record.published_count = stats["records_published"]
            run_record.rejected_count = stats["records_rejected"]
            run_record.needs_review_count = stats["records_needs_review"]
            run_record.validation_error_count = stats["validation_errors"]
            run_record.anomaly_count = stats["anomalies"]
            run_record.summary = stats

            self.db.commit()
            return stats

        except Exception as e:
            self.db.rollback()
            run_record.finished_at = datetime.now(timezone.utc)
            run_record.status = RunStatus.FAILED.value
            run_record.summary = {"fatal_error": str(e), **stats}
            self.db.commit()
            raise

    def _extract_branches_from_counselling_portal(self, content: bytes) -> Dict[str, str]:
        branches = {}
        try:
            html = content.decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "html.parser")
            for h2 in soup.find_all("h2"):
                if "Branches offered for B.E." in h2.get_text():
                    container = h2.find_parent("div", class_="txt-content")
                    if container:
                        for tr in container.find_all("tr"):
                            tds = tr.find_all("td")
                            if len(tds) >= 3:
                                bname = tds[1].get_text(strip=True)
                                bcode = tds[2].get_text(strip=True)
                                if bcode and bcode.upper() != "BRANCH CODE":
                                    norm_code = Normalizer.normalize_branch_code(bcode)
                                    norm_name, _ = Normalizer.normalize_branch_name(bname)
                                    if norm_code and norm_name:
                                        branches[norm_code] = norm_name
        except Exception:
            pass
        return branches

    def _ingest_colleges(self, colleges: List[Dict[str, Any]], source_version_id: uuid.UUID, stats: Dict[str, int]):
        for c in colleges:
            code = c["code"]
            stats["colleges_discovered"] += 1
            inst_type = c.get("institution_type", InstitutionType.ENGINEERING.value)
            existing = self.db.execute(select(College).where(College.code == code)).scalar_one_or_none()
            if not existing:
                college = College(
                    code=code,
                    name=c["name"],
                    original_name=c["original_name"],
                    location=c.get("location"),
                    institution_type=inst_type
                )
                self.db.add(college)
                self.db.flush()
                stats["colleges_inserted"] += 1
                
                # Add default alias
                alias = CollegeAlias(college_id=college.id, alias=c["name"], source="COMEDK")
                self.db.add(alias)
            else:
                updated = False
                if c.get("location") and not existing.location:
                    existing.location = c["location"]
                    updated = True
                # Only update institution_type if c explicitly came with an authoritative institution_type
                if "institution_type" in c and c["institution_type"]:
                    if existing.institution_type != c["institution_type"]:
                        existing.institution_type = c["institution_type"]
                        updated = True
                if updated:
                    stats["colleges_updated"] += 1
                else:
                    stats["colleges_unchanged"] += 1

    def _ingest_branches(self, branches: Dict[str, str], stats: Dict[str, int]):
        alias_map = {
            "BDC": "DC",
            "BIN": "BI",
            "BPL": "BP",
            "ECV": "ED",
            "ECS": "EC",
        }
        for b_code, b_name in branches.items():
            stats["branches_discovered"] += 1
            existing = self.db.execute(select(Branch).where(Branch.code == b_code)).scalar_one_or_none()
            norm_name, orig_name = Normalizer.normalize_branch_name(b_name)

            if b_code == "AT" or "ARCHITECTURE" in norm_name.upper():
                ptype = ProgramType.ARCHITECTURE.value
            elif b_code in ("BD", "BDC", "BI", "BIN", "DC", "DF", "DI", "DL") or "BACHELOR OF DESIGN" in norm_name.upper() or "B. DESIGN" in norm_name.upper():
                ptype = ProgramType.DESIGN.value
            elif b_code in ("BP", "BPL", "IMP") or "PLANNING" in norm_name.upper():
                ptype = ProgramType.OTHER.value
            else:
                ptype = ProgramType.ENGINEERING.value

            is_canon = (b_code not in alias_map and b_code != "CM")

            if not existing:
                branch = Branch(
                    code=b_code,
                    name=norm_name,
                    original_name=orig_name,
                    program_type=ptype,
                    is_canonical=is_canon
                )
                self.db.add(branch)
                self.db.flush()
                stats["branches_inserted"] += 1
            else:
                if existing.program_type != ptype or existing.is_canonical != is_canon:
                    existing.program_type = ptype
                    existing.is_canonical = is_canon
                    stats["branches_updated"] += 1

        for alias_code, canon_code in alias_map.items():
            alias_b = self.db.execute(select(Branch).where(Branch.code == alias_code)).scalar_one_or_none()
            canon_b = self.db.execute(select(Branch).where(Branch.code == canon_code)).scalar_one_or_none()
            if alias_b and canon_b and alias_b.canonical_branch_id != canon_b.id:
                alias_b.canonical_branch_id = canon_b.id
        self.db.flush()

    def _ingest_seat_and_fee_records(self, parse_res, source_version_id: uuid.UUID, stats: Dict[str, int]):
        seat_recs = parse_res.metadata.get("seat_records", [])
        fee_recs = parse_res.metadata.get("fee_records", [])

        # Fetch college & branch maps
        colleges = {c.code: c.id for c in self.db.execute(select(College)).scalars().all()}
        branches = {b.code: b.id for b in self.db.execute(select(Branch)).scalars().all()}

        for s in seat_recs:
            c_id = colleges.get(s["college_code"])
            b_id = branches.get(s["branch_code"])
            if c_id and b_id:
                existing_seat = self.db.execute(
                    select(SeatRecord).where(
                        SeatRecord.source_version_id == source_version_id,
                        SeatRecord.college_id == c_id,
                        SeatRecord.branch_id == b_id,
                        SeatRecord.academic_year == s["academic_year"]
                    )
                ).scalars().first()
                if not existing_seat:
                    sr = SeatRecord(
                        source_version_id=source_version_id,
                        college_id=c_id,
                        branch_id=b_id,
                        academic_year=s["academic_year"],
                        total_seats=s.get("total_seats"),
                        vacant_seats=s.get("vacant_seats"),
                        status=RecordStatus.PUBLISHED.value
                    )
                    self.db.add(sr)
                    stats["records_published"] += 1

        for f in fee_recs:
            c_id = colleges.get(f["college_code"])
            b_id = branches.get(f["branch_code"])
            if c_id and f.get("total_fee") is not None:
                existing_fee = self.db.execute(
                    select(FeeRecord).where(
                        FeeRecord.source_version_id == source_version_id,
                        FeeRecord.college_id == c_id,
                        FeeRecord.branch_id == b_id,
                        FeeRecord.academic_year == f["academic_year"]
                    )
                ).scalars().first()
                if not existing_fee:
                    fr = FeeRecord(
                        source_version_id=source_version_id,
                        college_id=c_id,
                        branch_id=b_id,
                        academic_year=f["academic_year"],
                        total_fee=f["total_fee"],
                        tuition_fee=f.get("tuition_fee"),
                        other_fee=f.get("other_fee"),
                        status=RecordStatus.PUBLISHED.value
                    )
                    self.db.add(fr)
                    stats["records_published"] += 1

    def _ingest_cutoff_records(
        self,
        parse_res,
        sv: SourceVersion,
        cat_map: Dict[str, Category],
        round_map: Dict[str, CounsellingRound],
        run_id: uuid.UUID,
        stats: Dict[str, int]
    ):
        if stats is None:
            stats = {}
        raw_records = parse_res.records
        stats["records_parsed"] = stats.get("records_parsed", 0) + len(raw_records)

        college_map = {c.code: c.id for c in self.db.execute(select(College)).scalars().all()}
        branch_map = {b.code: b.id for b in self.db.execute(select(Branch)).scalars().all()}
        category_map = {c.code: c.id for c in self.db.execute(select(Category)).scalars().all()}
        round_map_db = {r.code: r.id for r in self.db.execute(select(CounsellingRound).where(CounsellingRound.academic_year == sv.academic_year)).scalars().all()}

        validator = DataValidator(
            known_college_codes=set(college_map.keys()),
            known_branch_codes=set(branch_map.keys()),
            known_categories=set(category_map.keys()),
        )

        valid_records, validation_errors, anomalies = validator.validate_cutoff_records(
            records=raw_records,
            academic_year=sv.academic_year
        )

        stats["records_validated"] = stats.get("records_validated", 0) + len(valid_records)
        stats["records_rejected"] = stats.get("records_rejected", 0) + len(validation_errors)
        stats["validation_errors"] = stats.get("validation_errors", 0) + len(validation_errors)
        stats["anomalies"] = stats.get("anomalies", 0) + len(anomalies)

        # Log validation errors to database
        for err in validation_errors:
            self._record_error(
                run_id=run_id,
                source_version_id=sv.id,
                entity_type=err.entity_type,
                entity_id=err.entity_identifier,
                code=err.error_code,
                msg=err.message,
                severity=err.severity,
                ctx=err.context_data
            )

        # Log anomalies to database
        for anom in anomalies:
            self._record_error(
                run_id=run_id,
                source_version_id=sv.id,
                entity_type=anom.entity_type,
                entity_id=anom.entity_identifier,
                code=anom.error_code,
                msg=anom.message,
                severity=anom.severity,
                ctx=anom.context_data
            )

        # Batch Completeness Check (Fail Closed for full cutoff documents)
        is_corrigendum = "corrigendum" in (sv.source_title or "").lower() or "corrigendum" in (sv.source_url or "").lower()
        completeness_errors = []
        if not is_corrigendum:
            # Determine document program type (Engineering vs Architecture)
            doc_program_type = DocumentClassifier.extract_program_type(f"{sv.source_title} {sv.source_url}")
            if valid_records and all(r.get("branch_code") in ("AT", "AR") for r in valid_records):
                doc_program_type = ProgramType.ARCHITECTURE.value

            rnd_code = sv.counselling_round or "R1"
            rnd_id_val = round_map_db.get(rnd_code)
            existing_baseline = 0
            if rnd_id_val:
                existing_baseline = self.db.execute(
                    select(func.count(CutoffRecord.id))
                    .join(Branch, CutoffRecord.branch_id == Branch.id)
                    .where(
                        CutoffRecord.academic_year == sv.academic_year,
                        CutoffRecord.round_id == rnd_id_val,
                        CutoffRecord.status == RecordStatus.PUBLISHED.value,
                        Branch.program_type == doc_program_type
                    )
                ).scalar_one()

            completeness_errors = validator.validate_batch_completeness(
                doc_type="CUTOFF_PDF",
                extracted_count=len(valid_records),
                historical_baseline_count=existing_baseline if existing_baseline > 0 else None,
                program_type=doc_program_type
            )

        if completeness_errors:
            stats["records_needs_review"] = stats.get("records_needs_review", 0) + len(valid_records)
            stats["documents_needs_review"] = stats.get("documents_needs_review", 0) + 1
            sv.processing_status = RecordStatus.NEEDS_REVIEW.value
            for err in completeness_errors:
                self._record_error(
                    run_id=run_id,
                    source_version_id=sv.id,
                    entity_type=err.entity_type,
                    entity_id=err.entity_identifier,
                    code=err.error_code,
                    msg=err.message,
                    severity=err.severity,
                    ctx=err.context_data
                )
            self.review_queue.add_review_item(
                source_id=sv.source_id,
                source_version_id=sv.id,
                ingestion_run_id=run_id,
                document_type=sv.document_type,
                document_url=sv.source_url,
                failure_reason=FailureReason.SUSPICIOUS_LOW_COUNT.value,
                validation_errors=[{"code": e.error_code, "message": e.message, "context": e.context_data} for e in completeness_errors],
                parser_version=sv.parser_version,
                review_notes=f"Completeness validation failed: {completeness_errors[0].message}"
            )
            self.db.commit()
            return {
                "source_title": sv.source_title,
                "academic_year": sv.academic_year,
                "counselling_round": sv.counselling_round,
                "status": "NEEDS_REVIEW",
                "failure_reason": FailureReason.SUSPICIOUS_LOW_COUNT.value,
                "candidate_records": len(raw_records),
                "validated_records": len(valid_records),
                "published_records": 0,
                "verified_unchanged_records": 0,
                "superseded_records": 0,
                "factual_changes": 0
            }

        val_colleges = {r["college_code"] for r in valid_records}
        val_branches = {r["branch_code"] for r in valid_records}
        val_categories = {r["category_code"] for r in valid_records}

        published_count = 0
        verified_unchanged_count = 0
        superseded_count = 0

        # Persist valid records with duplicate protection and strict source immutability
        for rec in valid_records:
            col_id = college_map[rec["college_code"]]
            br_id = branch_map[rec["branch_code"]]
            cat_id = category_map[rec["category_code"]]
            rnd_id = round_map_db.get(rec["round_code"])

            if not rnd_id:
                # Fallback to R1 if round code was missing
                rnd_id = round_map_db.get("R1")

            # Check if record already exists for THIS specific immutable source version
            existing_for_version = self.db.execute(
                select(CutoffRecord).where(
                    CutoffRecord.college_id == col_id,
                    CutoffRecord.branch_id == br_id,
                    CutoffRecord.category_id == cat_id,
                    CutoffRecord.round_id == rnd_id,
                    CutoffRecord.academic_year == rec["academic_year"],
                    CutoffRecord.source_version_id == sv.id
                )
            ).scalar_one_or_none()

            if existing_for_version:
                # Strictly enforce factual immutability
                if existing_for_version.closing_rank != rec["closing_rank"]:
                    self._record_error(
                        run_id=run_id,
                        source_version_id=sv.id,
                        entity_type="CUTOFF",
                        entity_id=rec.get("row_identifier"),
                        code="FACTUAL_MUTATION_REJECTED",
                        msg=f"Attempted to mutate closing rank from {existing_for_version.closing_rank} to {rec['closing_rank']} for immutable source version {sv.id}",
                        severity=ValidationSeverity.ERROR.value
                    )
                    continue
                # Record is verified identical in DB - 0 factual changes
                verified_unchanged_count += 1
                continue

            # Check if an earlier published source version exists for this logical key
            existing_earlier = self.db.execute(
                select(CutoffRecord).where(
                    CutoffRecord.college_id == col_id,
                    CutoffRecord.branch_id == br_id,
                    CutoffRecord.category_id == cat_id,
                    CutoffRecord.round_id == rnd_id,
                    CutoffRecord.academic_year == rec["academic_year"],
                    CutoffRecord.status == RecordStatus.PUBLISHED.value
                )
            ).scalars().all()

            for old_rec in existing_earlier:
                # Mark previous source version's record as SUPERSEDED without altering factual values
                old_rec.status = RecordStatus.SUPERSEDED.value
                superseded_count += 1

            cutoff = CutoffRecord(
                source_version_id=sv.id,
                college_id=col_id,
                branch_id=br_id,
                category_id=cat_id,
                round_id=rnd_id,
                academic_year=rec["academic_year"],
                opening_rank=rec.get("opening_rank"),
                closing_rank=rec["closing_rank"],
                page_number=rec.get("page_number"),
                row_identifier=rec.get("row_identifier"),
                status=RecordStatus.PUBLISHED.value
            )
            self.db.add(cutoff)
            stats["records_published"] = stats.get("records_published", 0) + 1
            published_count += 1

        self.db.flush()
        if sv.processing_status != RecordStatus.NEEDS_REVIEW.value:
            sv.processing_status = RecordStatus.PUBLISHED.value

        doc_report = {
            "source_title": sv.source_title,
            "academic_year": sv.academic_year,
            "counselling_round": sv.counselling_round,
            "pdf_page_count": parse_res.metadata.get("pdf_page_count", 0),
            "extracted_pages": parse_res.metadata.get("extracted_pages_count", 0),
            "raw_rows_detected": parse_res.metadata.get("raw_rows_detected", 0),
            "candidate_records": len(raw_records),
            "validated_records": len(valid_records),
            "rejected_records": len(validation_errors),
            "needs_review_records": len(anomalies),
            "unique_college_count": len(val_colleges),
            "unique_branch_count": len(val_branches),
            "category_count": len(val_categories),
            "categories": sorted(list(val_categories)),
            "parser_warnings": parse_res.metadata.get("parser_warnings", []),
            "published_records": published_count,
            "verified_unchanged_records": verified_unchanged_count,
            "superseded_records": superseded_count,
            "factual_changes": 0,
            "status": "PUBLISHED"
        }

        print(
            f"[PARSING REPORT] {sv.source_title} ({sv.counselling_round}): "
            f"Pages={doc_report['pdf_page_count']}, ExtractedPages={doc_report['extracted_pages']}, "
            f"RawRows={doc_report['raw_rows_detected']}, Candidates={doc_report['candidate_records']}, "
            f"Validated={doc_report['validated_records']}, Rejected={doc_report['rejected_records']}, "
            f"NeedsReview={doc_report['needs_review_records']}, Colleges={doc_report['unique_college_count']}, "
            f"Branches={doc_report['unique_branch_count']}, Categories={doc_report['category_count']} ({doc_report['categories']}), "
            f"Published={published_count}, VerifiedUnchanged={verified_unchanged_count}, FactualChanges=0"
        )

        return doc_report

    def _record_error(
        self,
        run_id: Optional[uuid.UUID],
        source_version_id: Optional[uuid.UUID],
        entity_type: str,
        entity_id: Optional[str],
        code: str,
        msg: str,
        severity: str = ValidationSeverity.ERROR.value,
        ctx: Optional[Dict[str, Any]] = None
    ):
        from backend.app.models.ingestion import IngestionRun
        valid_run_id = None
        if run_id and self.db.get(IngestionRun, run_id):
            valid_run_id = run_id
        else:
            latest = self.db.execute(select(IngestionRun).order_by(IngestionRun.started_at.desc())).scalars().first()
            if latest:
                valid_run_id = latest.id
            else:
                new_run = IngestionRun(started_at=datetime.now(timezone.utc), status=RunStatus.RUNNING.value)
                self.db.add(new_run)
                self.db.flush()
                valid_run_id = new_run.id

        err = ValidationError(
            ingestion_run_id=valid_run_id,
            source_version_id=source_version_id,
            entity_type=entity_type,
            entity_identifier=entity_id,
            error_code=code,
            message=msg,
            severity=severity,
            context_data=ctx
        )
        self.db.add(err)
