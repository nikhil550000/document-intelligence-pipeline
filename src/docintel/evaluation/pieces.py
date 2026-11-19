"""Cut one of CUAD's answers into the values written in it."""

import re

# A slash cuts only with a space on each side, so the slashes inside a date stay.
PIECE_SEPARATORS = re.compile(r";|,| / ")


def cut_into_pieces(answer: str) -> list[str]:
    """Cuts an answer at each separator into pieces in lower case.

    Raises:
        ValueError: A piece is empty, as in an empty answer or `5 years;;2 years`.
    """
    pieces = []
    for piece in PIECE_SEPARATORS.split(answer):
        text = piece.strip().lower()
        if not text:
            raise ValueError(f"empty piece in the answer: {answer!r}")
        pieces.append(text)
    return pieces
