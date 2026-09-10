import pytest
from pydantic import ValidationError

from lumon.solve import OptimalityGuarantee, Solution


def _solution_data() -> dict[str, object]:
    return {
        "selected_intervention_ids": [],
        "total_cost": 0.0,
        "covered_path_ids": [],
        "covered_weight": 0.0,
        "uncovered_path_ids": [],
        "is_full_cover": True,
        "solver_name": "test",
        "guarantee": OptimalityGuarantee.EXACT,
        "wall_time_seconds": 0.0,
        "notes": None,
    }


@pytest.mark.parametrize("guarantee", list(OptimalityGuarantee))
def test_solution_guarantee_survives_json_round_trip(guarantee: OptimalityGuarantee) -> None:
    fields = _solution_data()
    fields["guarantee"] = guarantee

    solution = Solution.model_validate(fields)
    restored = Solution.model_validate_json(solution.model_dump_json())

    assert restored == solution
    assert restored.guarantee is guarantee
    assert solution.model_dump(mode="json")["guarantee"] == guarantee.value


def test_solution_rejects_unsupported_guarantees() -> None:
    fields = _solution_data()
    fields["guarantee"] = "approximate"

    with pytest.raises(ValidationError, match="Input should be"):
        Solution.model_validate(fields)


@pytest.mark.parametrize(
    "field",
    ["selected_intervention_ids", "covered_path_ids", "uncovered_path_ids"],
)
@pytest.mark.parametrize("ids", [["z", "a"], ["a", "a"]], ids=["unsorted", "duplicate"])
def test_solution_id_lists_must_be_sorted_and_unique(field: str, ids: list[str]) -> None:
    fields = _solution_data()
    fields[field] = ids

    with pytest.raises(ValidationError, match="sorted and contain no duplicates"):
        Solution.model_validate(fields)


def test_solution_is_frozen() -> None:
    solution = Solution.model_validate(_solution_data())

    with pytest.raises(ValidationError, match="frozen"):
        solution.total_cost = 1.0


@pytest.mark.parametrize("field", ["approximation_ratio", "unexpected"])
def test_solution_rejects_extra_fields(field: str) -> None:
    fields = _solution_data()
    fields[field] = 2.0

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Solution.model_validate(fields)
