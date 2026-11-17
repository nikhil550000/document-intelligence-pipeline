"""Tests for the scoring form of a CUAD answer."""

from datetime import date

from docintel.domain.values import Perpetual
from docintel.evaluation.gold import AcceptedValues, NoAnswer, Skipped, SkipRule


def test_there_are_five_skip_rules_with_these_names() -> None:
    """Reports count skipped cases under these names, so they must not drift."""
    rule_names = {rule.value for rule in SkipRule}
    assert rule_names == {
        "redacted",
        "passage only",
        "perpetual renewal",
        "date in a duration field",
        "no named place",
    }


def test_accepted_values_with_the_same_values_are_equal() -> None:
    """Two answers built separately from the same values are the same answer."""
    first = AcceptedValues((date(2019, 9, 5), Perpetual.PERPETUAL))
    second = AcceptedValues((date(2019, 9, 5), Perpetual.PERPETUAL))
    assert first == second


def test_skips_are_equal_only_under_the_same_rule() -> None:
    """A skip is told apart from another skip by its rule."""
    assert Skipped(SkipRule.REDACTED) == Skipped(SkipRule.REDACTED)
    assert Skipped(SkipRule.REDACTED) != Skipped(SkipRule.PASSAGE_ONLY)


def test_no_answer_equals_no_answer() -> None:
    """It carries nothing, so any two are the same."""
    assert NoAnswer() == NoAnswer()
