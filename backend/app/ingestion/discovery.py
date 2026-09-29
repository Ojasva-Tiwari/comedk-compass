import re
from datetime import date
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, quote
import httpx
from bs4 import BeautifulSoup
from backend.app.config import settings
from backend.app.core.enums import DocumentType
from backend.app.ingestion.normalizer import Normalizer

@dataclass
class DiscoveredSource:
    url: str
    title: str
    document_type: str
    academic_year: int
    counselling_round: Optional[str] = None
    publication_date: Optional[date] = None
    publisher: str = "COMEDK"

class OfficialSourceDiscovery:
    OFFICIAL_MEMBER_INSTITUTIONS_URL = "https://www.comedk.org/member-institutions"
    OFFICIAL_BE_COLLEGES_URL = "https://www.comedk.org/be-colleges"
    OFFICIAL_COUNSELLING_DOCS_URL = "https://www.comedk.org/counselling-document-2026"

    def __init__(self, academic_year: int = 2026):
        self.academic_year = academic_year
        self.headers = {"User-Agent": settings.USER_AGENT}

    @staticmethod
    def extract_publication_date(text: str) -> Optional[date]:
        match = re.search(
            r'Notified[_\s]+(?:on[_\s]+)?(\d{1,2})[._\/-](\d{1,2})[._\/-](\d{2,4})',
            text,
            re.IGNORECASE
        )
        if match:
            try:
                d = int(match.group(1))
                m = int(match.group(2))
                y = int(match.group(3))
                if y < 100:
                    y += 2000
                return date(y, m, d)
            except Exception:
                pass
        return None

    @staticmethod
    def identify_document_type(title_or_url: str) -> str:
        s = title_or_url.lower()
        if "cut-off" in s or "cutoff" in s or "cut_off" in s or "cut off" in s:
            return DocumentType.CUTOFF_PDF.value
        elif "seat" in s or "vacant" in s:
            if "fee" in s:
                return DocumentType.SEAT_MATRIX_PDF.value # Often combined with fee
            return DocumentType.SEAT_MATRIX_PDF.value
        elif "fee" in s:
            return DocumentType.FEE_STRUCTURE_PDF.value
        elif "notification" in s or "guide" in s or "process" in s:
            return DocumentType.NOTIFICATION_PDF.value
        elif "branch" in s or "course" in s:
            return DocumentType.BRANCHES_OFFERED_PDF.value
        return DocumentType.OTHER.value

    @staticmethod
    def identify_round(title_or_url: str) -> Optional[str]:
        s = title_or_url.lower()
        if "mock" in s:
            return "MOCK"
        elif "round 1" in s or "round-1" in s or "round_1" in s:
            return "R1"
        elif "round 2" in s or "round-2" in s or "round_2" in s:
            return "R2"
        elif "round 3" in s or "round-3" in s or "round_3" in s:
            return "R3"
        elif "round 4" in s or "round-4" in s or "round_4" in s:
            return "R4"
        return None

    async def discover_all(self) -> List[DiscoveredSource]:
        discovered: List[DiscoveredSource] = []
        seen_urls = set()

        # 1. Base official HTML pages
        base_pages = [
            (self.OFFICIAL_MEMBER_INSTITUTIONS_URL, "COMEDK Member Institutions Registry", DocumentType.MEMBER_INSTITUTIONS_HTML.value),
            (self.OFFICIAL_BE_COLLEGES_URL, "COMEDK Engineering Colleges Directory", DocumentType.BE_COLLEGES_HTML.value),
            (self.OFFICIAL_COUNSELLING_DOCS_URL, f"COMEDK Counselling Documents Portal {self.academic_year}", DocumentType.COUNSELLING_PORTAL_HTML.value),
        ]

        for url, title, dtype in base_pages:
            if url not in seen_urls:
                discovered.append(DiscoveredSource(
                    url=url,
                    title=title,
                    document_type=dtype,
                    academic_year=self.academic_year,
                    counselling_round=None,
                    publication_date=None
                ))
                seen_urls.add(url)

        # 2. Dynamic discovery from the official counselling page
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, follow_redirects=True) as client:
            try:
                resp = await client.get(self.OFFICIAL_COUNSELLING_DOCS_URL, headers=self.headers)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if not href or href.startswith("#") or href.startswith("javascript:"):
                            continue

                        full_url = urljoin(self.OFFICIAL_COUNSELLING_DOCS_URL, href)
                        if full_url in seen_urls:
                            continue

                        # Extract context from link text and enclosing parent
                        link_text = Normalizer.clean_text(a.get_text())
                        parent = a.find_parent(["li", "tr", "div", "p"])
                        parent_text = Normalizer.clean_text(parent.get_text()) if parent else ""
                        
                        combined_text = f"{parent_text} {link_text}".strip()
                        if not combined_text:
                            combined_text = full_url

                        # Only include relevant official documents
                        if full_url.lower().endswith(".pdf") or any(kw in combined_text.lower() for kw in [
                            "cut-off", "cutoff", "cut_off", "cut off", "seat", "fee", "notification", "counselling"
                        ]):
                            doc_type = self.identify_document_type(combined_text)
                            c_round = self.identify_round(combined_text)
                            pub_date = self.extract_publication_date(combined_text) or self.extract_publication_date(full_url)

                            # Clean title
                            title = link_text if len(link_text) > 10 else parent_text
                            title = title or full_url.split("/")[-1]
                            title = title[:500]

                            discovered.append(DiscoveredSource(
                                url=full_url,
                                title=title,
                                document_type=doc_type,
                                academic_year=self.academic_year,
                                counselling_round=c_round,
                                publication_date=pub_date
                            ))
                            seen_urls.add(full_url)
            except Exception as e:
                # Log or handle network error safely
                pass

        return discovered
