"""Cut one of CUAD's answers into the values written in it."""

import re

# A slash cuts only with a space on each side, so the slashes inside a date stay.
PIECE_SEPARATORS = re.compile(r";|,| / ")


def cut_into_pieces(answer: str) -> list[str]:
    """Cuts an answer at each separator into pieces in lower case.

    A piece left empty by a separator at the end, as in `6 months;`, is dropped.

    Raises:
        ValueError: The answer has no piece in it.
    """
    pieces = []
    for piece in PIECE_SEPARATORS.split(answer):
        text = piece.strip().lower()
        if text:
            pieces.append(text)

    if not pieces:
        raise ValueError(f"no value in the answer: {answer!r}")
    return pieces
