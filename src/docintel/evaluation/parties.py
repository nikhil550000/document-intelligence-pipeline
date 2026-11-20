"""Compare party names, and read CUAD's answer for the parties."""

import re

from docintel.evaluation.gold import PartyNames, Skipped, SkipRule
from docintel.evaluation.names import comparable_name
from docintel.evaluation.parties_by_hand import PARTIES_BY_HAND

CURLY_QUOTES = str.maketrans(
    {"\N{LEFT DOUBLE QUOTATION MARK}": '"', "\N{RIGHT DOUBLE QUOTATION MARK}": '"'}
)
# The alias starts at the first bracket that holds a quotation mark, or at the first
# quotation mark. A bracket with none, as in `TOM Online (BVI) limited`, is the name.
ALIAS_START = re.compile(r'\([^()]*"|"')
ALIAS = re.compile(r'"([^"]*)"')
# A trading name is another name for the same party, so it is no second party.
# Text copied from a PDF may break it over lines, so the cut runs past line breaks.
TRADING_NAME = re.compile(
    r"\b(?:d/b/a|dba|doing business as)\b.*", re.IGNORECASE | re.DOTALL
)
# Punctuation in front, as in a quoted `"The John Hopkins University"`, is no word.
THE_IN_FRONT = re.compile(r"^\W*the\s+", re.IGNORECASE)
# These words describe the parties together: `MS and MSCI individually as "Party"`.
GROUP_WORDS = re.compile(
    r"\b(?:individually|collectively|each|together|referred)\b", re.IGNORECASE
)
NAME_JOINERS = re.compile(r",|\band\b", re.IGNORECASE)
# A company may be called `X`, so a short run of x is a name, not a blackout.
REDACTED_BY_LETTERS = re.compile(r"x{3,}")


def comparable_party(name: str) -> str:
    """Gives the form in which two party names are compared.

    A trading name after "d/b/a" and a leading "The" are dropped, then only the
    letters and digits are kept. `Inc.` stays different from `Incorporated`.
    """
    # "The" goes first, so that `The DBA Group` keeps the name `DBA Group`.
    name = THE_IN_FRONT.sub("", name.strip())
    return comparable_name(without_trading_name(name))


def same_party(first: str, second: str) -> bool:
    """Tells whether two party names name the same party."""
    return comparable_party(first) == comparable_party(second)


def without_trading_name(name: str) -> str:
    """Cuts the text from "d/b/a" on, when a name stands in front of it."""
    trading_name = TRADING_NAME.search(name)
    if trading_name is None:
        return name
    # With nothing in front, `DBA Group` is a legal name, not a trading name.
    in_front = name[: trading_name.start()]
    if not comparable_name(in_front):
        return name
    return in_front


def read_parties_answer(answer: str) -> PartyNames | Skipped:
    """Reads CUAD's answer for the parties into the names it holds.

    Each piece between semicolons is first looked up in the pieces read by hand.
    Otherwise its name is the text in front of its alias, and a piece that names
    no party is dropped. When only blanks are left, the answer is skipped as
    redacted.

    Raises:
        ValueError: A piece is empty, or no piece names a party and none is a blank.
    """
    aliases = set()
    for alias in ALIAS.findall(answer.translate(CURLY_QUOTES)):
        aliases.add(comparable_name(alias))

    names: list[str] = []
    found_a_blank = False
    for piece in cut_parties_answer(answer):
        if piece in PARTIES_BY_HAND:
            names.extend(PARTIES_BY_HAND[piece])
            continue
        name = name_in_piece(piece)
        # Nothing in front of the alias: `(collectively "Parties")`.
        if not name:
            continue
        if is_blank(name):
            found_a_blank = True
        elif not names_no_party(name, aliases):
            names.append(name)

    if names:
        return PartyNames(tuple(names))
    if found_a_blank:
        return Skipped(SkipRule.REDACTED)
    raise ValueError(f"no party named in the answer: {answer!r}")


def cut_parties_answer(answer: str) -> list[str]:
    """Cuts an answer at each semicolon, never at a comma, which names contain.

    Raises:
        ValueError: A piece is empty.
    """
    # Five answers end with a semicolon, which leaves no piece behind it.
    pieces = [piece.strip() for piece in answer.strip().removesuffix(";").split(";")]
    if "" in pieces:
        raise ValueError(f"empty piece in the answer: {answer!r}")
    return pieces


def name_in_piece(piece: str) -> str:
    """Gives the text in front of the alias, without a trading name."""
    piece = piece.translate(CURLY_QUOTES)
    alias_start = ALIAS_START.search(piece)
    if alias_start is not None:
        piece = piece[: alias_start.start()]
    name = without_trading_name(piece).strip()
    # Seven pieces open with a bracket that is never closed: `(DGT Corp. ("DGT")`.
    if name.startswith("(") and ")" not in name:
        name = name[1:].strip()
    return name


def is_blank(name: str) -> bool:
    """Tells whether the name is left blank or blacked out, as in a form contract."""
    comparable = comparable_name(name)
    return not comparable or REDACTED_BY_LETTERS.fullmatch(comparable) is not None


def names_no_party(name: str, aliases: set[str]) -> bool:
    """Tells whether the name describes the parties together.

    Args:
        name: The text in front of the alias.
        aliases: Every alias of the answer, in comparable form.
    """
    if GROUP_WORDS.search(name):
        return True
    # `Stryker and Conformis` names two parties by the aliases given to them before.
    parts = []
    for part in NAME_JOINERS.split(name):
        if part.strip():
            parts.append(comparable_name(part))
    return len(parts) > 1 and all(part in aliases for part in parts)
