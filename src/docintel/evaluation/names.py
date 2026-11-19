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
    # An accent written as a separate mark would be dropped as punctuation, and the
    # same name would then score differently depending on how it was encoded.
    text = unicodedata.normalize("NFC", text).lower()
    return "".join(character for character in text if character.isalnum())


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
        if not comparable_name(part):
            raise ValueError(f"no name in the answer: {answer!r}")

    if len(parts) == 1:
        return AcceptedValues((parts[0],))
    joined = " ".join(parts)
    if comparable_name(joined) in TITLES_BROKEN_OVER_LINES:
        return AcceptedValues((joined,))
    return AcceptedValues((*parts, joined))
