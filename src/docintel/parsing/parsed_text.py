"""What every parser gives back, so that one parser can stand in for another."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedText:
    """The text of a PDF, one string for each page, and what read it.

    A page that gives no text is an empty string, so page numbers never shift.
    """

    pages: tuple[str, ...]
    parser: str
    parser_version: str
    seconds: float
