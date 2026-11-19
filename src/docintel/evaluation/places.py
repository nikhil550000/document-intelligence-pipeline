"""Compare place names, and read CUAD's answer for the governing law."""

import re

from docintel.evaluation.gold import AcceptedValues, Skipped, SkipRule
from docintel.evaluation.names import comparable_name

# Other spellings of one place, each seen in CUAD's answers or in the passages
# behind them, and the name they are compared as.
SAME_PLACE = {
    # England and Wales are one legal system. CUAD wrote `England` for "the laws of
    # England and Wales" in one contract and `England; Wales` in another.
    "England": "England and Wales",
    "Wales": "England and Wales",
    "England; Wales": "England and Wales",
    "England, United Kingdom; Wales, United Kingdom": "England and Wales",
    "England and Wales, UK": "England and Wales",
    # Passages say "PRC Laws" and "the laws of the PRC".
    "China": "People's Republic of China",
    "PRC": "People's Republic of China",
    "Federal Republic of Germany": "Germany",
    # Looked up before "Republic of" is dropped, which would turn this into China.
    "Republic of China": "Taiwan",
    "R.O.C.": "Taiwan",
    "United States of America": "United States",
    # CUAD's own spelling slip.
    "Massachussets": "Massachusetts",
}
SAME_PLACE_BY_COMPARABLE = {
    comparable_name(spelling): comparable_name(place)
    for spelling, place in SAME_PLACE.items()
}

# Contracts write "the State of New York" where CUAD wrote `New York`.
THE_IN_FRONT = re.compile(r"^the\s+", re.IGNORECASE)
WORDS_IN_FRONT = re.compile(
    r"^(?:state|commonwealth|province|republic)\s+of\s+", re.IGNORECASE
)
# Only these countries go after a comma, so `Delaware, Illinois` stays two places.
COUNTRIES = r"(?:canada|australia|united kingdom|uk|united states|usa)"
COUNTRY_BEHIND = re.compile(rf",\s*{COUNTRIES}\s*$", re.IGNORECASE)
# A comma may follow the country: `Ontario, Canada, New York` is two places.
PLACE_SEPARATORS = re.compile(rf";|,(?!\s*{COUNTRIES}\s*(?:;|,|$))", re.IGNORECASE)

# The only pieces of CUAD's answers that are not a place.
NOT_A_PLACE = frozenset(
    comparable_name(piece)
    for piece in (
        "the state in which the breach occurs",
        "United Nations Convention on Contract for the International Sale of Goods",
        "THE STATE IN WHICH THE FRANCHISED RESTAURANT IS LOCATED",
        "THE UNITED STATES TRADEMARK ACT OF 1946",
    )
)


def comparable_place(text: str) -> str:
    """Gives the form in which two place names are compared.

    "The" and "State of" and similar words in front, and a country after a comma,
    are dropped. Another spelling of the same place is replaced by that place.
    """
    as_written = text.strip()
    without_the_or_country = COUNTRY_BEHIND.sub("", THE_IN_FRONT.sub("", as_written))
    bare_name = WORDS_IN_FRONT.sub("", without_the_or_country)
    # Looked up at each step: `Republic of China` matches before "Republic of" goes,
    # and `England, United Kingdom` only once the country has gone.
    for name in (as_written, without_the_or_country, bare_name):
        same_place = SAME_PLACE_BY_COMPARABLE.get(comparable_name(name))
        if same_place is not None:
            return same_place
    return comparable_name(bare_name)


def same_place(first: str, second: str) -> bool:
    """Tells whether two place names name the same place."""
    return comparable_place(first) == comparable_place(second)


def read_governing_law_answer(answer: str) -> AcceptedValues | Skipped:
    """Reads CUAD's answer for the governing law into the places that count as right.

    A piece that is redacted or is not a place is dropped. When every piece is
    dropped, the answer is skipped under the rule of the first one.

    Raises:
        ValueError: A piece is empty.
    """
    places = [piece.strip() for piece in PLACE_SEPARATORS.split(answer)]
    if "" in places:
        raise ValueError(f"empty piece in the answer: {answer!r}")
    # `England; Wales` is one place, so a spelling in the table is not cut.
    if comparable_name(answer) in SAME_PLACE_BY_COMPARABLE:
        return AcceptedValues((answer.strip(),))

    values = []
    dropped_for = []
    for place in places:
        rule = rule_that_drops(place)
        if rule is None:
            values.append(place)
        else:
            dropped_for.append(rule)

    if values:
        return AcceptedValues(tuple(values))
    return Skipped(dropped_for[0])


def rule_that_drops(piece: str) -> SkipRule | None:
    """Gives the rule that drops a piece, or None when the piece is a place."""
    comparable = comparable_name(piece)
    # A bracket alone is no redaction; a piece with no letter or digit, `[* * *]`, is.
    if not comparable:
        return SkipRule.REDACTED
    if comparable in NOT_A_PLACE:
        return SkipRule.NO_NAMED_PLACE
    return None
