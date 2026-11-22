"""Tests for finding the PDF of each CUAD answer row."""

from pathlib import Path

import pytest

from docintel.evaluation.contracts import (
    PDF_FOLDER,
    PDF_NAMES_THAT_DIFFER,
    find_contract_pdfs,
)
from docintel.evaluation.cuad import MASTER_CLAUSES_PATH, load_cuad_answers


def write_files(folder: Path, relative_paths: list[str]) -> None:
    """Writes an empty file at each path, making its folders first."""
    for relative_path in relative_paths:
        path = folder / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")


def test_a_row_finds_the_pdf_of_the_same_name_in_any_folder(tmp_path: Path) -> None:
    """CUAD keeps its PDFs in a folder for each part and kind of agreement."""
    write_files(tmp_path, ["Part_I/License/a.pdf", "Part_II/Service/b.PDF"])

    pdfs = find_contract_pdfs(tmp_path, ["a.pdf", "b.PDF"])

    assert pdfs == {
        "a.pdf": tmp_path / "Part_I" / "License" / "a.pdf",
        "b.PDF": tmp_path / "Part_II" / "Service" / "b.PDF",
    }


def test_a_row_named_differently_finds_the_file_the_table_gives(
    tmp_path: Path,
) -> None:
    """The answer file writes & where the PDF's name has _."""
    row_name = "MOELIS&CO_03_24_2014-EX-10.19-STRATEGIC ALLIANCE AGREEMENT.PDF"
    file_name = "MOELIS_CO_03_24_2014-EX-10.19-STRATEGIC ALLIANCE AGREEMENT.PDF"
    write_files(tmp_path, [f"Part_I/Strategic Alliance/{file_name}"])

    pdfs = find_contract_pdfs(tmp_path, [row_name])

    assert pdfs[row_name].name == file_name


def test_a_row_without_a_pdf_stops(tmp_path: Path) -> None:
    """Nothing guesses at a name the table does not hold, not even another case."""
    write_files(tmp_path, ["Part_I/License/a.pdf"])

    with pytest.raises(FileNotFoundError, match="A.PDF"):
        find_contract_pdfs(tmp_path, ["A.PDF"])


# Skipped without the dataset; one CI job downloads it and fails on any skip.
@pytest.mark.skipif(
    not PDF_FOLDER.exists(),
    reason="CUAD is not downloaded; run `docintel data download`",
)
def test_every_answer_row_finds_a_pdf_of_its_own() -> None:
    """All 510 rows find a PDF, no two rows the same one, and no PDF is left over."""
    row_names = list(load_cuad_answers(MASTER_CLAUSES_PATH))

    pdfs = find_contract_pdfs(PDF_FOLDER, row_names)

    all_pdfs = set()
    for path in PDF_FOLDER.rglob("*"):
        if path.is_file():
            all_pdfs.add(path)
    assert len(row_names) == 510
    assert len(set(pdfs.values())) == 510
    assert set(pdfs.values()) == all_pdfs
    # Every line of the table is a row of the answer file, so none is stale.
    assert set(PDF_NAMES_THAT_DIFFER) <= set(row_names)
