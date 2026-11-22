"""Tests for the structure check."""

import json
from typing import Any

from docintel.domain.problems import Problem
from docintel.domain.record import ContractRecord
from docintel.validation.structure import check_structure


def test_output_that_loads_becomes_a_record(empty_record: dict[str, Any]) -> None:
    """A complete, well-typed output gives the record."""
    result = check_structure(json.dumps(empty_record), cut_off=False)

    assert isinstance(result, ContractRecord)


def test_output_that_is_not_json_gives_one_problem_for_the_whole_output() -> None:
    """Text that does not parse has no field to blame."""
    result = check_structure("The contract is about software.", cut_off=False)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].layer == "structure"
    assert result[0].rule == "json_invalid"
    assert result[0].field is None


def test_output_cut_off_at_the_length_limit_says_so_first(
    empty_record: dict[str, Any],
) -> None:
    """The reviewer sees why the JSON is broken, not only that it is."""
    whole = json.dumps(empty_record)

    result = check_structure(whole[: len(whole) // 2], cut_off=True)

    assert isinstance(result, list)
    assert result[0] == Problem(
        "structure",
        "cut_off",
        None,
        "The output stopped at the length limit before it was complete.",
    )
    assert result[1].rule == "json_invalid"


def test_output_cut_off_but_complete_is_still_a_record(
    empty_record: dict[str, Any],
) -> None:
    """A model may pad a finished answer with spaces until the limit."""
    result = check_structure(json.dumps(empty_record) + "   ", cut_off=True)

    assert isinstance(result, ContractRecord)


def test_each_wrong_field_gives_a_problem_named_by_its_field(
    empty_record: dict[str, Any],
) -> None:
    """Problems carry the field and the path inside it, for the reviewer."""
    record = empty_record
    record["agreement_date"]["value"] = "2014-02-30"
    del record["insurance"]

    result = check_structure(json.dumps(record), cut_off=False)

    assert isinstance(result, list)
    by_field = {problem.field: problem for problem in result}
    assert sorted(by_field) == ["agreement_date", "insurance"]
    assert by_field["agreement_date"].rule == "date_parsing"
    assert by_field["agreement_date"].message.startswith("agreement_date.value:")
    assert by_field["insurance"].rule == "missing"
