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


def test_a_separator_at_the_end_leaves_no_empty_piece() -> None:
    """CUAD has the answer `successive 12 months; successive 6 months;`."""
    assert cut_into_pieces("successive 12 months; successive 6 months;") == [
        "successive 12 months",
        "successive 6 months",
    ]


@pytest.mark.parametrize("answer", ["", " ", ";"])
def test_an_answer_with_no_value_raises(answer: str) -> None:
    """Nothing may be dropped without a rule, so an empty answer is a mistake."""
    with pytest.raises(ValueError):
        cut_into_pieces(answer)
