"""A small PDF made in code, for the tests that read or store one."""

import pytest


def make_pdf(page_texts: list[str]) -> bytes:
    """Writes a PDF with one page for each text, in Helvetica; "" is a blank page."""
    # Objects 1 to 3 are the catalog, the list of pages and the font. Each page
    # then adds two: its content, and the page that points to it.
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    page_references = []
    for text in page_texts:
        content = ""
        if text:
            content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
        content_number = len(objects)
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_number} 0 R >>"
        )
        page_references.append(f"{len(objects)} 0 R")
    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(page_references)}] "
        f"/Count {len(page_references)} >>"
    )

    # A reader finds each object through the table of byte offsets at the end.
    pdf = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n{body}\nendobj\n"
    table_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
    pdf += f"startxref\n{table_offset}\n%%EOF\n"
    return pdf.encode("ascii")


@pytest.fixture
def three_page_pdf() -> bytes:
    """A PDF of three pages whose middle page is blank."""
    return make_pdf(["First page", "", "Third page"])
