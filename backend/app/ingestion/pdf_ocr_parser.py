"""Scanned-PDF parsing: rasterize pages, OCR them, then reuse the text-line
statement parser. Requires the optional `ocr` extras (pdf2image + pytesseract)
and a system tesseract binary.
"""
from .types import ParsedStatement


class OCRUnavailableError(RuntimeError):
    pass


def parse_pdf_ocr(path: str) -> ParsedStatement:
    try:
        import pytesseract  # type: ignore
        from pdf2image import convert_from_path  # type: ignore
    except ImportError as e:
        raise OCRUnavailableError(
            "Scanned-PDF support needs the optional OCR dependencies: "
            "pip install 'finance-agent-backend[ocr]' and install tesseract "
            "(brew install tesseract poppler)."
        ) from e

    from .pdf_text_parser import parse_statement_text

    pages = convert_from_path(path, dpi=300)
    text = "\n".join(pytesseract.image_to_string(page) for page in pages)
    return parse_statement_text(text)
