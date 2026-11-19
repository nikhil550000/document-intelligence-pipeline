"""Compare names, and read CUAD's answer for the document name."""

from docintel.evaluation.gold import AcceptedValues

# Every answer written in parts puts a blank line between them.
PART_BREAK = "\n\n"


def comparable_name(text: str) -> str:
    """Keeps only the letters and digits, in lower case.

    Spacing in CUAD's text is sometimes broken (`SOFT WARE`), so spaces are
    ignored completely. Accents stay: `Spôk` is not `Spok`.
    """
    return "".join(character for character in text.lower() if character.isalnum())


def same_name(first: str, second: str) -> bool:
    """Tells whether two names are equal once capitals, spacing and punctuation go."""
    return comparable_name(first) == comparable_name(second)


def read_document_name_answer(answer: str) -> AcceptedValues:
    """Reads CUAD's answer for the document name into the titles that count as right.

    A title in parts is right on any one part, or on all parts joined in order.
    The document name is never skipped, so an answer with no name in it is a bug.

    Raises:
        ValueError: A part has no letter or digit in it.
    """
    parts = [part.strip() for part in answer.split(PART_BREAK)]
    for part in parts:
        if not comparable_name(part):
            raise ValueError(f"no name in the answer: {answer!r}")

    if len(parts) == 1:
        return AcceptedValues((parts[0],))
    return AcceptedValues((*parts, " ".join(parts)))
