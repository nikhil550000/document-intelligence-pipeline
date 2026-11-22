"""The first check: the model's output must load into the record type."""

from pydantic import ValidationError

from docintel.domain.problems import Problem
from docintel.domain.record import ContractRecord

LAYER = "structure"


def check_structure(output: str, cut_off: bool) -> ContractRecord | list[Problem]:
    """Turns the model's output into a record, or into the problems that stop it.

    Args:
        output: The text the model returned.
        cut_off: The model stopped at the length limit, so the output may end
            in the middle.
    """
    try:
        return ContractRecord.model_validate_json(output)
    except ValidationError as error:
        problems = []
        if cut_off:
            # Said first, because it explains the errors that follow from it.
            problems.append(
                Problem(
                    LAYER,
                    "cut_off",
                    None,
                    "The output stopped at the length limit before it was complete.",
                )
            )
        for detail in error.errors():
            problems.append(
                problem_from_error(detail["type"], detail["loc"], detail["msg"])
            )
        return problems


def problem_from_error(
    error_type: str, location: tuple[int | str, ...], message: str
) -> Problem:
    """Turns one of Pydantic's errors into a problem, with the field it is in."""
    field = None
    if location:
        field = str(location[0])
    path = []
    for part in location:
        path.append(str(part))
    if path:
        message = f"{'.'.join(path)}: {message}"
    return Problem(LAYER, error_type, field, message)
