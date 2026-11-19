"""Tests for cutting CUAD's answers into pieces."""

import pytest

from docintel.evaluation.pieces import cut_into_pieces


@pytest.mark.parametrize(
    ("answer", "pieces"),
    [
        ("5 years; 2 years", ["5 years", "2 years"]),
        ("4 years, 6 months", ["4 years", "6 months"]),
        ("180 days / 6 months", ["180 days", "6 months"]),
    ],
)
def test_an_answer_is_cut_at_each_separator(answer: str, pieces: list[str]) -> None:
    """A semicolon, a comma and a slash with a space on each side all cut."""
    assert cut_into_pieces(answer) == pieces


def test_the_slashes_inside_a_date_do_not_cut() -> None:
    """Only a slash with a space on each side is a separator."""
    assert cut_into_pieces("09/01/2006") == ["09/01/2006"]


def test_pieces_are_in_lower_case_without_the_spaces_around_them() -> None:
    """Capitals and the space after a separator do not matter."""
    assert cut_into_pieces("Perpetual;  12 Months") == ["perpetual", "12 months"]


@pytest.mark.parametrize("answer", ["", " ", ";", "5 years;;2 years", "6 months;"])
def test_an_empty_piece_raises(answer: str) -> None:
    """Nothing may be dropped without a rule, so an empty piece is a mistake."""
    with pytest.raises(ValueError):
        cut_into_pieces(answer)
