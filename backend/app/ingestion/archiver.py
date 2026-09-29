import hashlib
import re
from pathlib import Path
from typing import Tuple, Optional
from urllib.parse import urlparse, quote
import httpx
from backend.app.config import settings

class ArchiverError(Exception):
    pass

class DocumentArchiver:
    def __init__(self, base_raw_dir: Optional[Path] = None):
        self.base_raw_dir = base_raw_dir or settings.RAW_DATA_DIR
        self.base_raw_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def get_destination_folder(self, academic_year: int, doc_type: str) -> Path:
        dt = doc_type.upper()
        if "CUTOFF" in dt:
            sub = "cutoff"
        elif "SEAT" in dt:
            sub = "seat_matrix"
        elif "FEE" in dt:
            sub = "fees"
        elif "NOTIFICATION" in dt:
            sub = "notifications"
        else:
            sub = "other"

        dest = self.base_raw_dir / str(academic_year) / sub
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    def sanitize_filename(self, filename: str) -> str:
        # Keep letters, numbers, hyphens, underscores, dots
        clean = re.sub(r'[\\/*?:"<>| ]', '_', filename)
        clean = re.sub(r'_+', '_', clean)
        return clean.strip('_.')

    def archive_content(
        self,
        content: bytes,
        academic_year: int,
        doc_type: str,
        filename: str
    ) -> Tuple[str, Path, int]:
        """
        Stores content and returns (sha256_hash, local_path, file_size_bytes).
        If file exists and content differs, appends hash prefix to avoid collision.
        Never modifies existing files.
        """
        content_hash = self.compute_sha256(content)
        folder = self.get_destination_folder(academic_year, doc_type)
        safe_name = self.sanitize_filename(filename)
        
        target_path = folder / safe_name
        
        if target_path.exists():
            existing_hash = self.compute_sha256(target_path.read_bytes())
            if existing_hash == content_hash:
                return content_hash, target_path, len(content)
            else:
                # Content updated / changed under same name: archive with hash prefix
                target_path = folder / f"{content_hash[:8]}_{safe_name}"

        target_path.write_bytes(content)
        return content_hash, target_path, len(content)

    async def download_and_archive(
        self,
        url: str,
        academic_year: int,
        doc_type: str,
        fallback_filename: Optional[str] = None
    ) -> Tuple[bytes, str, Path, int, str]:
        """
        Downloads a document from an external URL and archives it locally.
        Returns: (content_bytes, sha256_hash, local_path, file_size, content_type)
        """
        if not self.validate_url(url):
            raise ArchiverError(f"Invalid external URL: {url}")

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "*/*"
        }

        # Handle spaces in URL path if not percent-encoded
        parsed = urlparse(url)
        safe_path = quote(parsed.path, safe="/:@&=+$,-_.!~*'()")
        safe_url = f"{parsed.scheme}://{parsed.netloc}{safe_path}"
        if parsed.query:
            safe_url += f"?{parsed.query}"

        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(safe_url, headers=headers)
            if resp.status_code != 200:
                raise ArchiverError(f"HTTP {resp.status_code} fetching {url}")
            
            content = resp.content
            content_type = resp.headers.get("content-type", "application/octet-stream")

        url_filename = Path(parsed.path).name
        filename = url_filename or fallback_filename or f"doc_{content_hash[:12]}"
        
        content_hash, local_path, size = self.archive_content(
            content=content,
            academic_year=academic_year,
            doc_type=doc_type,
            filename=filename
        )

        return content, content_hash, local_path, size, content_type
