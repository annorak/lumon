"""Tests for the `Path` and `PathSet` models.

These check the model in isolation. Extraction is tested separately, in
`test_path_extraction.py`, against graphs whose answers are known.
"""

import pytest
from pydantic import ValidationError

from lumon.model import Path, PathSet


def build_path(path_id: str = "p0000", objective: str = "n_obj", weight: float = 10.0) -> Path:
    return Path(
        id=path_id,
        edge_ids=["e_one", "e_two"],
        node_ids=["n_entry", "n_middle", objective],
        entry_id="n_entry",
        objective_id=objective,
        weight=weight,
    )


def test_a_well_formed_path_is_accepted() -> None:
    path = build_path()

    assert path.edge_ids == ["e_one", "e_two"]
    assert path.node_ids == ["n_entry", "n_middle", "n_obj"]


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        pytest.param({"edge_ids": []}, "at least 1 item", id="no edges"),
        pytest.param({"node_ids": ["n_entry", "n_obj"]}, "needs 3 nodes", id="too few nodes"),
        pytest.param(
            {"node_ids": ["n_other", "n_middle", "n_obj"]},
            "not at its entry",
            id="does not start at the entry",
        ),
        pytest.param(
            {"node_ids": ["n_entry", "n_middle", "n_other"]},
            "not at its objective",
            id="does not end at the objective",
        ),
        pytest.param({"weight": 0.0}, "greater than 0", id="weightless"),
        pytest.param({"weight": -1.0}, "greater than 0", id="negative weight"),
        pytest.param({"id": "p 0000"}, "no whitespace", id="whitespace in the id"),
        pytest.param({"unknown_field": 3}, "Extra inputs", id="unknown field"),
    ],
)
def test_a_malformed_path_is_rejected(overrides: dict[str, object], expected: str) -> None:
    fields: dict[str, object] = {
        "id": "p0000",
        "edge_ids": ["e_one", "e_two"],
        "node_ids": ["n_entry", "n_middle", "n_obj"],
        "entry_id": "n_entry",
        "objective_id": "n_obj",
        "weight": 10.0,
    }

    with pytest.raises(ValidationError, match=expected):
        Path.model_validate({**fields, **overrides})


def test_a_path_cannot_be_mutated_after_construction() -> None:
    path = build_path()

    with pytest.raises(ValidationError, match="frozen"):
        path.weight = 99.0


def test_a_path_set_rejects_duplicate_path_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate path ids: p0000"):
        PathSet(paths=[build_path("p0000"), build_path("p0000")], truncated=False)


def test_a_truncated_path_set_without_a_reason_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must carry a truncation_reason"):
        PathSet(paths=[build_path()], truncated=True)


def test_a_truncated_path_set_with_an_empty_reason_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must carry a truncation_reason"):
        PathSet(paths=[build_path()], truncated=True, truncation_reason="")


def test_a_path_set_must_state_whether_it_is_complete() -> None:
    """`truncated` has no default, so a partial set cannot be built that looks complete."""
    with pytest.raises(ValidationError, match="truncated"):
        PathSet.model_validate({"paths": []})


def test_total_weight_adds_every_path_up() -> None:
    path_set = PathSet(
        paths=[build_path("p0000", weight=10.0), build_path("p0001", weight=2.5)],
        truncated=False,
    )

    assert path_set.total_weight == 12.5


def test_total_weight_of_an_empty_set_is_zero() -> None:
    assert PathSet(paths=[], truncated=False).total_weight == 0.0


def test_by_objective_groups_paths_and_omits_unreached_objectives() -> None:
    path_set = PathSet(
        paths=[
            build_path("p0000", objective="n_cloud"),
            build_path("p0001", objective="n_cloud"),
            build_path("p0002", objective="n_database"),
        ],
        truncated=False,
    )

    grouped = path_set.by_objective()

    assert sorted(grouped) == ["n_cloud", "n_database"]
    assert [path.id for path in grouped["n_cloud"]] == ["p0000", "p0001"]
    assert [path.id for path in grouped["n_database"]] == ["p0002"]


def test_weights_by_id_keys_every_weight_to_its_path() -> None:
    path_set = PathSet(
        paths=[build_path("p0000", weight=10.0), build_path("p0001", weight=4.0)],
        truncated=False,
    )

    assert path_set.weights_by_id() == {"p0000": 10.0, "p0001": 4.0}


def test_a_path_set_survives_a_round_trip_through_json() -> None:
    path_set = PathSet(
        paths=[build_path()],
        truncated=True,
        truncation_reason="stopped at the max_paths cap of 1",
        graph_id="synthetic-abcd1234",
    )

    assert PathSet.model_validate_json(path_set.model_dump_json()) == path_set
