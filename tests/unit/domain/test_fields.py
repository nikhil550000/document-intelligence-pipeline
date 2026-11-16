"""Tests for the field list."""

from docintel.domain.fields import ALL_FIELDS, CLAUSE_FIELDS, FieldType


def test_there_are_41_fields() -> None:
    """The list covers every field CUAD labels."""
    assert len(ALL_FIELDS) == 41


def test_33_fields_are_clause_fields() -> None:
    """Eight fields hold a value and the other 33 are yes-or-no clauses."""
    clause_fields = [field for field in ALL_FIELDS if field.type is FieldType.CLAUSE]
    assert len(clause_fields) == 33
    assert len(CLAUSE_FIELDS) == 33


def test_no_name_appears_twice() -> None:
    """A repeated name would make two fields share one answer."""
    names = [field.name for field in ALL_FIELDS]
    assert len(set(names)) == len(names)
