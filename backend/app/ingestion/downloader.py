import asyncio
import hashlib
import re
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, quote
import httpx
from backend.app.config import settings

class DownloaderError(Exception):
    """Raised when document downloading fails or response is invalid."""
    pass

class CorruptDocumentError(DownloaderError):
    """Raised when downloaded file content is corrupt or does not match expected format."""
    pass

class DocumentDownloader:
    MAX_SIZE_BYTES = 50 * 1024 * 1024 # 50 MB protection

    def __init__(self, raw_base_dir: Optional[Path] = None):
        self.raw_base_dir = raw_base_dir or (settings.RAW_DATA_DIR / "comedk")
        self.raw_base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def validate_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        # Prevent directory traversal and remove invalid characters
        clean = Path(filename).name
        clean = re.sub(r'[\\/*?:"<>| ]', '_', clean)
        clean = re.sub(r'_+', '_', clean)
        clean = clean.strip('_.')
        return clean or "document.bin"

    @classmethod
    def validate_content_integrity(cls, content: bytes, content_type: str, url: str) -> None:
        """
        Validates that content is not empty, does not exceed size limit,
        and is genuine (e.g., rejecting HTML error pages returned with a .pdf URL).
        """
        if not content or len(content) == 0:
            raise CorruptDocumentError(f"Downloaded content from {url} is empty (0 bytes)")

        if len(content) > cls.MAX_SIZE_BYTES:
            raise CorruptDocumentError(
                f"Document from {url} exceeds maximum size limit ({len(content)} > {cls.MAX_SIZE_BYTES} bytes)"
            )

        lower_url = url.lower()
        # If URL indicates a PDF or content-type is application/pdf, verify PDF magic header
        if lower_url.endswith(".pdf") or "application/pdf" in content_type.lower():
            if not content.startswith(b"%PDF-"):
                # Detect HTML error page saved as PDF
                sample = content[:200].decode("utf-8", errors="replace").lower()
                if "<html" in sample or "<!doctype" in sample or "error" in sample:
                    raise CorruptDocumentError(
                        f"URL {url} returned HTML content instead of a valid PDF (magic header missing, found HTML)"
                    )
                raise CorruptDocumentError(f"File at {url} does not have valid PDF magic bytes '%PDF-'")

    def get_destination_folder(self, academic_year: int, document_type: str) -> Path:
        sub = document_type.lower()
        if "cutoff" in sub:
            type_dir = "cutoff"
        elif "vacant" in sub:
            type_dir = "vacant_seats"
        elif "seat" in sub:
            type_dir = "seat_matrix"
        elif "fee" in sub:
            type_dir = "fees"
        elif "notification" in sub:
            type_dir = "notifications"
        elif "branch" in sub:
            type_dir = "branches"
        elif "member_institutions" in sub:
            type_dir = "registry"
        elif "be_colleges" in sub:
            type_dir = "colleges"
        elif "portal" in sub:
            type_dir = "portal"
        else:
            type_dir = "other"

        dest = self.raw_base_dir / str(academic_year) / type_dir
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    def archive_content(
        self,
        content: bytes,
        academic_year: int,
        document_type: str,
        filename: str
    ) -> Tuple[str, Path, int]:
        """
        Deterministic, immutable raw file archiving.
        If file exists and content differs, writes under hash prefix to preserve history.
        """
        content_hash = self.compute_sha256(content)
        folder = self.get_destination_folder(academic_year, document_type)
        safe_name = self.sanitize_filename(filename)

        target_path = folder / safe_name

        if target_path.exists():
            existing_hash = self.compute_sha256(target_path.read_bytes())
            if existing_hash == content_hash:
                return content_hash, target_path, len(content)
            else:
                # Content changed under same filename: preserve old, store new with hash prefix
                target_path = folder / f"{content_hash[:8]}_{safe_name}"

        target_path.write_bytes(content)
        return content_hash, target_path, len(content)

    async def download_and_archive(
        self,
        url: str,
        academic_year: int,
        document_type: str,
        fallback_filename: Optional[str] = None,
        max_retries: int = 3
    ) -> Tuple[bytes, str, Path, int, str]:
        """
        Downloads a document with retry handling, size protection, and magic byte validation.
        Returns: (content_bytes, sha256_hash, local_path, file_size_bytes, content_type)
        """
        if not self.validate_url(url):
            raise DownloaderError(f"Invalid remote URL: {url}")

        parsed = urlparse(url)
        safe_path = quote(parsed.path, safe="/:@&=+$,-_.!~*'()")
        safe_url = f"{parsed.scheme}://{parsed.netloc}{safe_path}"
        if parsed.query:
            safe_url += f"?{parsed.query}"

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "*/*"
        }

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, follow_redirects=True) as client:
                    resp = await client.get(safe_url, headers=headers)
                    if resp.status_code != 200:
                        raise DownloaderError(f"HTTP {resp.status_code} fetching {url}")

                    content = resp.content
                    content_type = resp.headers.get("content-type", "application/octet-stream")
                    break
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                else:
                    raise DownloaderError(f"Failed to download {url} after {max_retries} attempts: {last_error}")

        # Validate file integrity and size
        self.validate_content_integrity(content, content_type, url)

        # Derive filename
        url_name = Path(parsed.path).name
        filename = url_name or fallback_filename or f"doc_{self.compute_sha256(content)[:12]}"
        if "." not in filename and "pdf" in content_type.lower():
            filename += ".pdf"
        elif "." not in filename and "html" in content_type.lower():
            filename += ".html"

        content_hash, local_path, size = self.archive_content(
            content=content,
            academic_year=academic_year,
            document_type=document_type,
            filename=filename
        )

        return content, content_hash, local_path, size, content_type
