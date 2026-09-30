from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.source import Source
from backend.app.core.enums import DocumentType, SourceAuthorityLevel

@dataclass
class RegisteredSourceConfig:
    source_code: str
    source_name: str
    url: str
    source_type: str
    authority_level: str = SourceAuthorityLevel.OFFICIAL_PRIMARY.value
    is_enabled: bool = True
    check_frequency_hours: int = 24
    expected_document_types: List[str] = field(default_factory=list)
    academic_year: int = 2026
    document_type: str = DocumentType.OTHER.value
    parser_type: Optional[str] = None
    parser_version: str = "v1.0.0"

# Canonical Official COMEDK Source Registry
OFFICIAL_COMEDK_SOURCES: List[RegisteredSourceConfig] = [
    RegisteredSourceConfig(
        source_code="COMEDK_MEMBER_INSTITUTIONS",
        source_name="COMEDK Member Institutions Registry",
        url="https://www.comedk.org/member-institutions",
        source_type="OFFICIAL_DIRECTORY",
        authority_level=SourceAuthorityLevel.OFFICIAL_PRIMARY.value,
        is_enabled=True,
        check_frequency_hours=24,
        expected_document_types=[DocumentType.MEMBER_INSTITUTIONS_HTML.value],
        academic_year=2026,
        document_type=DocumentType.MEMBER_INSTITUTIONS_HTML.value,
        parser_type="CollegeParser",
        parser_version="v1.0.0"
    ),
    RegisteredSourceConfig(
        source_code="COMEDK_BE_COLLEGES",
        source_name="COMEDK Engineering Colleges Directory",
        url="https://www.comedk.org/be-colleges",
        source_type="OFFICIAL_DIRECTORY",
        authority_level=SourceAuthorityLevel.OFFICIAL_PRIMARY.value,
        is_enabled=True,
        check_frequency_hours=24,
        expected_document_types=[DocumentType.BE_COLLEGES_HTML.value],
        academic_year=2026,
        document_type=DocumentType.BE_COLLEGES_HTML.value,
        parser_type="CollegeParser",
        parser_version="v1.0.0"
    ),
    RegisteredSourceConfig(
        source_code="COMEDK_COUNSELLING_PORTAL_2026",
        source_name="COMEDK Counselling Documents Portal 2026",
        url="https://www.comedk.org/counselling-document-2026",
        source_type="OFFICIAL_PORTAL",
        authority_level=SourceAuthorityLevel.OFFICIAL_PRIMARY.value,
        is_enabled=True,
        check_frequency_hours=12,
        expected_document_types=[
            DocumentType.COUNSELLING_PORTAL_HTML.value,
            DocumentType.CUTOFF_PDF.value,
            DocumentType.SEAT_MATRIX_PDF.value,
            DocumentType.VACANT_SEATS_PDF.value,
            DocumentType.FEE_STRUCTURE_PDF.value,
            DocumentType.BRANCHES_OFFERED_PDF.value,
            DocumentType.NOTIFICATION_PDF.value
        ],
        academic_year=2026,
        document_type=DocumentType.COUNSELLING_PORTAL_HTML.value,
        parser_type="CounsellingPortalParser",
        parser_version="v1.0.0"
    ),
    RegisteredSourceConfig(
        source_code="COMEDK_COUNSELLING_PORTAL_2024",
        source_name="COMEDK Counselling Documents Portal 2024",
        url="https://www.comedk.org/counselling-document-2024",
        source_type="OFFICIAL_PORTAL",
        authority_level=SourceAuthorityLevel.OFFICIAL_PRIMARY.value,
        is_enabled=True,
        check_frequency_hours=24,
        expected_document_types=[
            DocumentType.COUNSELLING_PORTAL_HTML.value,
            DocumentType.CUTOFF_PDF.value,
            DocumentType.SEAT_MATRIX_PDF.value,
            DocumentType.VACANT_SEATS_PDF.value,
            DocumentType.FEE_STRUCTURE_PDF.value,
            DocumentType.BRANCHES_OFFERED_PDF.value,
            DocumentType.NOTIFICATION_PDF.value
        ],
        academic_year=2024,
        document_type=DocumentType.COUNSELLING_PORTAL_HTML.value,
        parser_type="CounsellingPortalParser",
        parser_version="v1.0.0"
    ),
    RegisteredSourceConfig(
        source_code="COMEDK_COUNSELLING_PORTAL_2023",
        source_name="COMEDK Counselling Documents Portal 2023",
        url="https://www.comedk.org/counselling-document-2023",
        source_type="OFFICIAL_PORTAL",
        authority_level=SourceAuthorityLevel.OFFICIAL_PRIMARY.value,
        is_enabled=True,
        check_frequency_hours=24,
        expected_document_types=[
            DocumentType.COUNSELLING_PORTAL_HTML.value,
            DocumentType.CUTOFF_PDF.value,
            DocumentType.SEAT_MATRIX_PDF.value,
            DocumentType.VACANT_SEATS_PDF.value,
            DocumentType.FEE_STRUCTURE_PDF.value,
            DocumentType.BRANCHES_OFFERED_PDF.value,
            DocumentType.NOTIFICATION_PDF.value
        ],
        academic_year=2023,
        document_type=DocumentType.COUNSELLING_PORTAL_HTML.value,
        parser_type="CounsellingPortalParser",
        parser_version="v1.0.0"
    ),
]

class SourceRegistryService:
    def __init__(self, db: Session):
        self.db = db

    def sync_registered_sources(self) -> List[Source]:
        """
        Idempotently synchronizes configured official sources into the PostgreSQL sources table.
        Preserves existing runtime fields like last_checked_at and last_seen_hash.
        """
        synced: List[Source] = []
        for cfg in OFFICIAL_COMEDK_SOURCES:
            existing = self.db.execute(
                select(Source).where(
                    (Source.source_code == cfg.source_code) | (Source.url == cfg.url)
                )
            ).scalars().first()

            if existing:
                existing.source_code = cfg.source_code
                existing.source_type = cfg.source_type
                existing.title = cfg.source_name
                existing.authority_level = cfg.authority_level
                existing.is_enabled = cfg.is_enabled
                existing.check_frequency_hours = cfg.check_frequency_hours
                existing.expected_document_types = cfg.expected_document_types
                existing.document_type = cfg.document_type
                existing.parser_type = cfg.parser_type
                existing.parser_version = cfg.parser_version
                synced.append(existing)
            else:
                new_source = Source(
                    source_code=cfg.source_code,
                    source_type=cfg.source_type,
                    title=cfg.source_name,
                    url=cfg.url,
                    publisher="COMEDK",
                    authority_level=cfg.authority_level,
                    document_type=cfg.document_type,
                    academic_year=cfg.academic_year,
                    is_enabled=cfg.is_enabled,
                    check_frequency_hours=cfg.check_frequency_hours,
                    expected_document_types=cfg.expected_document_types,
                    parser_type=cfg.parser_type,
                    parser_version=cfg.parser_version
                )
                self.db.add(new_source)
                synced.append(new_source)

        self.db.commit()
        return synced

    def get_active_sources(self) -> List[Source]:
        return self.db.execute(
            select(Source).where(Source.is_enabled == True)
        ).scalars().all()

    def record_check(self, source_id: UUID) -> None:
        src = self.db.get(Source, source_id)
        if src:
            src.last_checked_at = datetime.now(timezone.utc)
            self.db.commit()

    def record_success(self, source_id: UUID, content_hash: Optional[str] = None) -> None:
        src = self.db.get(Source, source_id)
        if src:
            now = datetime.now(timezone.utc)
            src.last_checked_at = now
            src.last_success_at = now
            if content_hash:
                src.last_seen_hash = content_hash
            self.db.commit()
