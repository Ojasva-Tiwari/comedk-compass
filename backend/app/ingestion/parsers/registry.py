from typing import Dict, Any, List, Optional
from backend.app.core.enums import DocumentType
from backend.app.ingestion.parsers.base import BaseParser, ParseResult
from backend.app.ingestion.parsers.college_parser import CollegeParser
from backend.app.ingestion.parsers.cutoff_pdf_parser import CutoffPDFParser
CutoffPdfParser = CutoffPDFParser
from backend.app.ingestion.parsers.seat_and_fee_parser import SeatAndFeeParser

class NoParserAvailableError(Exception):
    """Raised when no parser is registered for a specific document type."""
    pass

class ParserRegistry:
    """
    Registry mapping COMEDK document types to dedicated parser implementations.
    Enforces parser versioning, supported type checks, and routes unknown documents safely.
    """

    def __init__(self):
        self._parsers: Dict[str, BaseParser] = {}
        self._register_default_parsers()

    def _register_default_parsers(self) -> None:
        college_parser = CollegeParser()
        cutoff_parser = CutoffPdfParser()
        seat_fee_parser = SeatAndFeeParser()

        # Register CollegeParser for HTML member and college directories
        self.register_parser(DocumentType.MEMBER_INSTITUTIONS_HTML.value, college_parser)
        self.register_parser(DocumentType.BE_COLLEGES_HTML.value, college_parser)

        # Register CutoffPdfParser for cutoffs
        self.register_parser(DocumentType.CUTOFF_PDF.value, cutoff_parser)

        # Register SeatAndFeeParser for seat matrices, fee structures, and vacant seat matrices
        self.register_parser(DocumentType.SEAT_MATRIX_PDF.value, seat_fee_parser)
        self.register_parser(DocumentType.FEE_STRUCTURE_PDF.value, seat_fee_parser)
        self.register_parser(DocumentType.VACANT_SEATS_PDF.value, seat_fee_parser)

    def register_parser(self, document_type: str, parser: BaseParser) -> None:
        self._parsers[document_type] = parser

    def get_parser(self, document_type: str) -> BaseParser:
        if document_type not in self._parsers:
            raise NoParserAvailableError(
                f"No registered parser available for document type '{document_type}'"
            )
        return self._parsers[document_type]

    def has_parser(self, document_type: str) -> bool:
        return document_type in self._parsers

    def get_parser_info(self, document_type: str) -> Dict[str, Any]:
        parser = self.get_parser(document_type)
        return {
            "document_type": document_type,
            "parser_name": parser.parser_name,
            "parser_version": parser.parser_version,
            "supported_types": getattr(parser, "supported_types", [document_type]),
        }

    def list_supported_types(self) -> List[str]:
        return sorted(list(self._parsers.keys()))
