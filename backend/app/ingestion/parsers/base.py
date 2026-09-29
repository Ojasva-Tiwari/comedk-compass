from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from backend.app.core.enums import RecordStatus

@dataclass
class ParseResult:
    records: List[Dict[str, Any]] = field(default_factory=list)
    discovered_branches: Dict[str, str] = field(default_factory=dict)
    discovered_colleges: List[Dict[str, Any]] = field(default_factory=list)
    status: RecordStatus = RecordStatus.PARSED
    errors: List[Dict[str, Any]] = field(default_factory=list)
    anomalies: List[Dict[str, Any]] = field(default_factory=list)
    page_count: int = 0
    row_count: int = 0
    is_usable_text: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

class OCRInterface(ABC):
    """
    Abstract interface for OCR fallback execution.
    By design, unparsed/scanned PDFs default to NEEDS_REVIEW
    rather than fabricating or guessing data.
    """
    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying OCR engine (e.g. Tesseract) is configured."""
        pass

    @abstractmethod
    def extract_text_from_scanned_page(self, page_image_bytes: bytes) -> str:
        """Extract text from an image byte stream."""
        pass

class BaseParser(ABC):
    """
    Abstract base class for all COMEDK source and document parsers.
    """
    def __init__(self, ocr_engine: Optional[OCRInterface] = None):
        self.ocr_engine = ocr_engine

    @property
    def parser_name(self) -> str:
        return self.__class__.__name__

    @property
    def parser_version(self) -> str:
        return "v1.0.0"

    @abstractmethod
    def parse(self, content: bytes, context: Optional[Dict[str, Any]] = None) -> ParseResult:
        """
        Parses raw content bytes (HTML or PDF) and returns a structured ParseResult.
        """
        pass
