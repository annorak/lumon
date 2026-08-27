"""Tests for the path set summary.

These numbers are a sanity check for a human, not an input to anything, so what matters is
that they are honest about an empty set and stable when there is a tie.
"""

import pytest
from pydantic import ValidationError

from lumon.model import Path, PathSet
from lumon.paths import PathStats, summarize


def build_path(path_id: str, node_ids: list[str], edge_ids: list[str], weight: float) -> Path:
    return Path(
        id=path_id,
        edge_ids=edge_ids,
        node_ids=node_ids,
        entry_id=node_ids[0],
        objective_id=node_ids[-1],
        weight=weight,
    )


def build_path_set() -> PathSet:
    """Two entries, two objectives, lengths 1, 2 and 3. `e_shared` sits on two of the three."""
    return PathSet(
        paths=[
            build_path("p0000", ["n_in_a", "n_cloud"], ["e_direct"], 10.0),
            build_path("p0001", ["n_in_a", "n_mid", "n_cloud"], ["e_shared", "e_up"], 10.0),
            build_path(
                "p0002", ["n_in_b", "n_mid", "n_low", "n_db"], ["e_shared", "e_down", "e_out"], 2.0
            ),
        ],
        truncated=False,
    )


def test_a_summary_counts_paths_entries_and_objectives() -> None:
    stats = summarize(build_path_set())

    assert stats.path_count == 3
    assert stats.distinct_entries == 2
    assert stats.distinct_objectives == 2


def test_a_summary_reports_path_lengths_in_hops() -> None:
    stats = summarize(build_path_set())

    assert stats.min_path_length == 1
    assert stats.median_path_length == 2.0
    assert stats.max_path_length == 3


def test_a_summary_totals_the_weight_of_every_path() -> None:
    assert summarize(build_path_set()).total_weight == 22.0


def test_a_summary_names_the_edge_the_most_paths_run_through() -> None:
    """A preview of the chokepoint structure the solver finds properly later."""
    stats = summarize(build_path_set())

    assert stats.most_common_edge_id == "e_shared"
    assert stats.most_common_edge_count == 2


def test_a_tie_on_the_most_common_edge_breaks_on_the_lowest_id() -> None:
    """Two edges appear once each, so without a stated rule the answer would depend on dict
    ordering and two runs could disagree."""
    path_set = PathSet(
        paths=[
            build_path("p0000", ["n_in", "n_obj"], ["e_zebra"], 1.0),
            build_path("p0001", ["n_in", "n_obj"], ["e_alpha"], 1.0),
        ],
        truncated=False,
    )

    assert summarize(path_set).most_common_edge_id == "e_alpha"


def test_an_empty_path_set_reports_no_lengths_rather_than_zeroes() -> None:
    """A graph where no validated route reaches an objective has no shortest path. Saying it
    is 0 hops would be a false statement dressed up as a tidy default."""
    stats = summarize(PathSet(paths=[], truncated=False))

    assert stats.path_count == 0
    assert stats.distinct_entries == 0
    assert stats.distinct_objectives == 0
    assert stats.min_path_length is None
    assert stats.median_path_length is None
    assert stats.max_path_length is None
    assert stats.total_weight == 0.0
    assert stats.most_common_edge_id is None
    assert stats.most_common_edge_count == 0


def test_a_summary_leaves_the_path_set_alone() -> None:
    path_set = build_path_set()

    summarize(path_set)

    assert path_set == build_path_set()


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"path_count": 0}, id="claims to be empty but reports lengths"),
        pytest.param({"min_path_length": None}, id="reports a length it does not have"),
        pytest.param({"most_common_edge_id": None}, id="names no edge despite having paths"),
    ],
)
def test_a_summary_that_contradicts_its_own_path_count_is_rejected(
    overrides: dict[str, object],
) -> None:
    fields: dict[str, object] = {
        "path_count": 3,
        "distinct_entries": 2,
        "distinct_objectives": 2,
        "min_path_length": 1,
        "median_path_length": 2.0,
        "max_path_length": 3,
        "total_weight": 22.0,
        "most_common_edge_id": "e_shared",
        "most_common_edge_count": 2,
    }

    with pytest.raises(ValidationError, match="defined exactly when"):
        PathStats.model_validate({**fields, **overrides})
