"""Read the text layer of a PDF with PDFium. A page that is only a picture is empty."""

import time

import pypdfium2
from pypdfium2.version import PDFIUM_INFO, PYPDFIUM_INFO

from docintel.parsing.parsed_text import ParsedText

PARSER_NAME = "pdfium"
# pypdfium2 can be built on another PDFium, so the PDFium build is named too.
PARSER_VERSION = f"pypdfium2 {PYPDFIUM_INFO.version}, PDFium {PDFIUM_INFO.build}"


def parse_pdf(pdf: bytes) -> ParsedText:
    """Returns the text of each page of the PDF, in page order."""
    start = time.perf_counter()
    pages: list[str] = []
    with pypdfium2.PdfDocument(pdf) as document:
        for page in document:
            text = page.get_textpage().get_text_range()
            # PDFium marks some hyphens with U+FFFE, which is not a character.
            pages.append(text.replace("￾", "-"))
    return ParsedText(
        pages=tuple(pages),
        parser=PARSER_NAME,
        parser_version=PARSER_VERSION,
        seconds=time.perf_counter() - start,
    )
