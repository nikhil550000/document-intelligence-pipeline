"""Tests for the duration and perpetual values."""

from docintel.domain.values import Duration, DurationUnit


def test_a_duration_has_three_units() -> None:
    """A record can give a duration in days, months or years, and not in weeks."""
    unit_names = {unit.value for unit in DurationUnit}
    assert unit_names == {"days", "months", "years"}


def test_durations_with_the_same_amount_and_unit_are_equal() -> None:
    """Two durations built separately are the same value."""
    assert Duration(30, DurationUnit.DAYS) == Duration(30, DurationUnit.DAYS)


def test_durations_with_different_units_are_not_equal() -> None:
    """30 days and 30 months are different values."""
    assert Duration(30, DurationUnit.DAYS) != Duration(30, DurationUnit.MONTHS)
