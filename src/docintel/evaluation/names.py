"""Compare names, and read CUAD's answer for the document name."""

import unicodedata

from docintel.evaluation.gold import AcceptedValues

# Every answer written in parts puts a blank line between them.
PART_BREAK = "\n\n"

# Two answers are one title broken over lines, so a part alone, such as `OF`, is
# no title. No rule tells them from two titles, so they are listed, in comparable form.
TITLES_BROKEN_OVER_LINES = (
    "addendumtozebrapartnerconnectdistributoragreement",
    "amendmentandterminationofjointventureagreement",
)


def comparable_name(text: str) -> str:
    """Keeps only the letters and digits, in lower case.

    Spacing in CUAD's text is sometimes broken (`SOFT WARE`), so spaces are
    ignored completely. Accents stay: `Spôk` is not `Spok`.
    """
    # Accents are split from their letters before the case is folded, as Unicode's
    # caseless match does, so `ΐ` matches its capital, `Ι` and two marks. Folding
    # makes `ß` match `SS`.
    text = unicodedata.normalize("NFD", text).casefold()
    # A mark belongs to the character before it. It stays with a letter: dropped,
    # `कुमार` would equal `कमर`. It goes with a symbol, as the invisible mark that
    # asks for `®` in emoji style does.
    kept = []
    keep_marks = False
    for character in text:
        if unicodedata.category(character).startswith("M"):
            if keep_marks:
                kept.append(character)
        else:
            keep_marks = character.isalnum()
            if keep_marks:
                kept.append(character)
    return "".join(kept)


def same_name(first: str, second: str) -> bool:
    """Tells whether two names are equal once capitals, spacing and punctuation go."""
    return comparable_name(first) == comparable_name(second)


def read_document_name_answer(answer: str) -> AcceptedValues:
    """Reads CUAD's answer for the document name into the titles that count as right.

    A title in parts is right on any one part, or on all parts joined in order.
    A title broken over lines is right only on all parts joined.
    The document name is never skipped, so an answer with no name in it is a bug.

    Raises:
        ValueError: A part has no letter or digit in it.
    """
    parts = [part.strip() for part in answer.split(PART_BREAK)]
    for part in parts:
        if not any(character.isalnum() for character in part):
            raise ValueError(f"no name in the answer: {answer!r}")

    if len(parts) == 1:
        return AcceptedValues((parts[0],))
    joined = " ".join(parts)
    if comparable_name(joined) in TITLES_BROKEN_OVER_LINES:
        return AcceptedValues((joined,))
    return AcceptedValues((*parts, joined))
