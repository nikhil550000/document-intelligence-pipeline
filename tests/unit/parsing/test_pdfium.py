"""Tests for reading a PDF's text page by page with PDFium."""

from importlib.metadata import version

import pytest

from docintel.evaluation.contracts import PDF_FOLDER
from docintel.parsing.pdfium import parse_pdf


def test_each_page_gives_its_own_text_in_page_order(three_page_pdf: bytes) -> None:
    """A blank page gives an empty text, so no later page moves up a place."""
    parsed = parse_pdf(three_page_pdf)

    assert parsed.pages == ("First page", "", "Third page")


def test_the_text_names_what_read_it_and_the_time_it_took(
    three_page_pdf: bytes,
) -> None:
    """The parser's name and version say which code made the text."""
    parsed = parse_pdf(three_page_pdf)

    assert parsed.parser == "pdfium"
    assert f"pypdfium2 {version('pypdfium2')}," in parsed.parser_version
    assert parsed.seconds > 0


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not PDF_FOLDER.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_a_hyphen_that_pdfium_marks_comes_out_as_a_hyphen() -> None:
    """PDFium gives U+FFFE, which is not a character, where the page shows -."""
    path = (
        PDF_FOLDER
        / "Part_II"
        / "Distributor"
        / "NETGEAR,INC_04_21_2003-EX-10.16-DISTRIBUTOR AGREEMENT.pdf"
    )

    parsed = parse_pdf(path.read_bytes())

    assert "Commercial\xa0Computer\xa0Software-Restricted\xa0Rights" in parsed.pages[2]
    for page in parsed.pages:
        assert "￾" not in page
