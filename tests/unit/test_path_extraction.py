"""Tests for path extraction.

Two of these carry most of the weight. `test_an_observed_only_route_reaches_nothing` is the
project's central rule at the point it matters most: an edge nobody proved cannot put a path
into the answer. And `test_every_preset_extracts_exactly_the_ground_truth_paths` checks the
extractor against the generator's constructed answers, which come from somewhere this code
cannot reach — so a bug here cannot corrupt its own expectation.
"""

import pytest
from pydantic import ValidationError

from lumon.generate import PRESETS, generate
from lumon.model import AttackGraph, Edge, EdgeType, Evidence, Node, NodeType, PathSet
from lumon.paths import extract_paths

PRESET_NAMES = sorted(PRESETS)


def entry(node_id: str) -> Node:
    return Node(id=node_id, type=NodeType.ENTRY_POINT, label=node_id)


def service(node_id: str) -> Node:
    return Node(id=node_id, type=NodeType.SERVICE, label=node_id)


def objective(node_id: str, weight: float = 10.0) -> Node:
    return Node(id=node_id, type=NodeType.OBJECTIVE, label=node_id, weight=weight)


def link(
    edge_id: str,
    source: str,
    target: str,
    evidence: Evidence = Evidence.VALIDATED,
    edge_type: EdgeType = EdgeType.REACHES,
) -> Edge:
    return Edge(id=edge_id, source=source, target=target, type=edge_type, evidence=evidence)


def node_sequences(path_set: PathSet) -> set[tuple[str, ...]]:
    return {tuple(path.node_ids) for path in path_set.paths}


def build_three_route_graph() -> AttackGraph:
    """One entry, three alternative middle hops, one objective. Exactly three paths."""
    return AttackGraph(
        nodes=[entry("n_in"), service("n_a"), service("n_b"), service("n_c"), objective("n_obj")],
        edges=[
            link("e_in_a", "n_in", "n_a"),
            link("e_in_b", "n_in", "n_b"),
            link("e_in_c", "n_in", "n_c"),
            link("e_a_obj", "n_a", "n_obj"),
            link("e_b_obj", "n_b", "n_obj"),
            link("e_c_obj", "n_c", "n_obj"),
        ],
        metadata={"graph_id": "three-route"},
    )


def test_a_graph_with_three_routes_returns_exactly_those_three() -> None:
    path_set = extract_paths(build_three_route_graph())

    assert node_sequences(path_set) == {
        ("n_in", "n_a", "n_obj"),
        ("n_in", "n_b", "n_obj"),
        ("n_in", "n_c", "n_obj"),
    }
    assert path_set.truncated is False
    assert path_set.truncation_reason is None


def test_paths_are_numbered_in_the_order_they_are_returned() -> None:
    path_set = extract_paths(build_three_route_graph())

    assert [path.id for path in path_set.paths] == ["p0000", "p0001", "p0002"]


def test_the_graph_id_travels_with_the_path_set() -> None:
    """So that pairing a path set with the wrong graph later on is detectable."""
    assert extract_paths(build_three_route_graph()).graph_id == "three-route"


def test_a_graph_with_no_graph_id_produces_a_path_set_with_none() -> None:
    graph = AttackGraph(
        nodes=[entry("n_in"), objective("n_obj")],
        edges=[link("e_in_obj", "n_in", "n_obj")],
    )

    assert extract_paths(graph).graph_id is None


def test_unvalidated_edges_never_appear_in_a_path() -> None:
    """Observed and inferred edges run alongside validated ones here, offering shortcuts the
    extractor must refuse to take."""
    graph = AttackGraph(
        nodes=[entry("n_in"), service("n_a"), objective("n_obj")],
        edges=[
            link("e_in_a", "n_in", "n_a"),
            link("e_a_obj", "n_a", "n_obj"),
            link("e_observed", "n_in", "n_obj", evidence=Evidence.OBSERVED),
            link("e_inferred", "n_in", "n_obj", evidence=Evidence.INFERRED),
        ],
    )

    path_set = extract_paths(graph)

    assert node_sequences(path_set) == {("n_in", "n_a", "n_obj")}
    assert {edge_id for path in path_set.paths for edge_id in path.edge_ids} == {
        "e_in_a",
        "e_a_obj",
    }


def test_an_observed_only_route_reaches_nothing() -> None:
    """The rule the whole project rests on. `n_leak` is reachable only across an edge somebody
    saw but never exercised, so Lumon must report no path to it at all — not a hedged one."""
    graph = AttackGraph(
        nodes=[entry("n_in"), service("n_a"), objective("n_cloud"), objective("n_leak")],
        edges=[
            link("e_in_a", "n_in", "n_a"),
            link("e_a_cloud", "n_a", "n_cloud"),
            link("e_a_leak", "n_a", "n_leak", evidence=Evidence.OBSERVED),
        ],
    )

    path_set = extract_paths(graph)

    assert sorted(path_set.by_objective()) == ["n_cloud"]
    assert all(path.objective_id != "n_leak" for path in path_set.paths)


def test_two_edge_types_between_one_pair_produce_two_distinct_paths() -> None:
    """Same nodes, different techniques. An intervention may sever one and leave the other, so
    collapsing them would hide a route from the solver."""
    graph = AttackGraph(
        nodes=[entry("n_in"), service("n_a"), objective("n_obj")],
        edges=[
            link("e_reaches", "n_in", "n_a", edge_type=EdgeType.REACHES),
            link("e_accesses", "n_in", "n_a", edge_type=EdgeType.CAN_ACCESS),
            link("e_a_obj", "n_a", "n_obj"),
        ],
    )

    path_set = extract_paths(graph)

    assert node_sequences(path_set) == {("n_in", "n_a", "n_obj")}
    assert [path.edge_ids for path in path_set.paths] == [
        ["e_accesses", "e_a_obj"],
        ["e_reaches", "e_a_obj"],
    ]


def test_a_cycle_neither_hangs_nor_repeats_a_node() -> None:
    graph = AttackGraph(
        nodes=[entry("n_in"), service("n_a"), service("n_b"), objective("n_obj")],
        edges=[
            link("e_in_a", "n_in", "n_a"),
            link("e_a_b", "n_a", "n_b"),
            link("e_b_a", "n_b", "n_a"),
            link("e_a_obj", "n_a", "n_obj"),
            link("e_b_obj", "n_b", "n_obj"),
        ],
    )

    path_set = extract_paths(graph)

    assert node_sequences(path_set) == {
        ("n_in", "n_a", "n_obj"),
        ("n_in", "n_a", "n_b", "n_obj"),
    }
    for path in path_set.paths:
        assert len(set(path.node_ids)) == len(path.node_ids)


def build_long_and_short_graph() -> AttackGraph:
    """One direct hop to the objective and one three-hop detour to the same place."""
    return AttackGraph(
        nodes=[entry("n_in"), service("n_a"), service("n_b"), objective("n_obj")],
        edges=[
            link("e_in_obj", "n_in", "n_obj"),
            link("e_in_a", "n_in", "n_a"),
            link("e_a_b", "n_a", "n_b"),
            link("e_b_obj", "n_b", "n_obj"),
        ],
    )


@pytest.mark.parametrize(
    ("max_depth", "expected"),
    [
        pytest.param(1, {("n_in", "n_obj")}, id="only the direct hop fits"),
        pytest.param(2, {("n_in", "n_obj")}, id="the detour is still one hop too long"),
        pytest.param(
            3,
            {("n_in", "n_obj"), ("n_in", "n_a", "n_b", "n_obj")},
            id="both fit",
        ),
    ],
)
def test_max_depth_excludes_paths_with_too_many_hops(
    max_depth: int, expected: set[tuple[str, ...]]
) -> None:
    """`max_depth` counts hops, so a path may cross at most that many edges."""
    path_set = extract_paths(build_long_and_short_graph(), max_depth=max_depth)

    assert node_sequences(path_set) == expected


def test_the_depth_bound_does_not_claim_truncation() -> None:
    """Deliberate: `truncated` means enumeration stopped early. Proving that no longer route
    exists is not something the extractor can do cheaply, so it does not pretend to."""
    path_set = extract_paths(build_long_and_short_graph(), max_depth=1)

    assert path_set.truncated is False


def test_hitting_max_paths_truncates_loudly() -> None:
    path_set = extract_paths(build_three_route_graph(), max_paths=2)

    assert len(path_set.paths) == 2
    assert path_set.truncated is True
    assert path_set.truncation_reason is not None
    assert "max_paths cap of 2" in path_set.truncation_reason
    assert "'n_in' -> 'n_obj'" in path_set.truncation_reason


def test_a_set_that_exactly_fills_the_cap_is_not_called_truncated() -> None:
    """Nothing was dropped, so nothing may be flagged. A false truncation sends a reviewer
    hunting for paths that never existed."""
    path_set = extract_paths(build_three_route_graph(), max_paths=3)

    assert len(path_set.paths) == 3
    assert path_set.truncated is False


def test_a_path_carries_the_weight_of_the_objective_it_reaches() -> None:
    graph = AttackGraph(
        nodes=[entry("n_in"), objective("n_cloud", weight=10.0), objective("n_db", weight=2.5)],
        edges=[
            link("e_in_cloud", "n_in", "n_cloud"),
            link("e_in_db", "n_in", "n_db"),
        ],
    )

    path_set = extract_paths(graph)

    assert {path.objective_id: path.weight for path in path_set.paths} == {
        "n_cloud": 10.0,
        "n_db": 2.5,
    }
    assert path_set.total_weight == 12.5


def test_two_runs_over_one_graph_produce_identical_output() -> None:
    graph, _ = generate(PRESETS["WIDE"])

    first = extract_paths(graph)
    second = extract_paths(graph)

    assert first.model_dump_json() == second.model_dump_json()


def test_paths_are_sorted_by_entry_then_objective_then_length_then_edges() -> None:
    graph = AttackGraph(
        nodes=[
            entry("n_in_b"),
            entry("n_in_a"),
            service("n_mid"),
            objective("n_obj_b"),
            objective("n_obj_a"),
        ],
        edges=[
            link("e_a_mid", "n_in_a", "n_mid"),
            link("e_b_mid", "n_in_b", "n_mid"),
            link("e_mid_obja", "n_mid", "n_obj_a"),
            link("e_mid_objb", "n_mid", "n_obj_b"),
            link("e_a_obja", "n_in_a", "n_obj_a"),
        ],
    )

    path_set = extract_paths(graph)

    assert [(path.entry_id, path.objective_id, len(path.edge_ids)) for path in path_set.paths] == [
        ("n_in_a", "n_obj_a", 1),
        ("n_in_a", "n_obj_a", 2),
        ("n_in_a", "n_obj_b", 2),
        ("n_in_b", "n_obj_a", 2),
        ("n_in_b", "n_obj_b", 2),
    ]


def test_a_graph_with_no_validated_route_to_any_objective_yields_an_empty_set() -> None:
    graph = AttackGraph(
        nodes=[entry("n_in"), objective("n_obj")],
        edges=[link("e_in_obj", "n_in", "n_obj", evidence=Evidence.INFERRED)],
    )

    path_set = extract_paths(graph)

    assert path_set.paths == []
    assert path_set.truncated is False


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_every_preset_extracts_exactly_the_ground_truth_paths(name: str) -> None:
    """The key integration test. The generator constructed these answers from the layout it
    built, never by running this code, so the expectation cannot inherit a bug from the
    extractor it is checking."""
    graph, truth = generate(PRESETS[name])

    path_set = extract_paths(graph)

    assert node_sequences(path_set) == {tuple(sequence) for sequence in truth.path_node_sequences}
    assert len(path_set.paths) == len(truth.path_node_sequences)
    assert path_set.truncated is False


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_every_extracted_path_weighs_what_its_objective_is_worth(name: str) -> None:
    graph, truth = generate(PRESETS[name])

    path_set = extract_paths(graph)

    assert all(path.weight == truth.objective_weights[path.objective_id] for path in path_set.paths)


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_every_extracted_path_walks_only_validated_edges(name: str) -> None:
    graph, _ = generate(PRESETS[name])
    validated_ids = {edge.id for edge in graph.validated_edges()}

    path_set = extract_paths(graph)

    assert {edge_id for path in path_set.paths for edge_id in path.edge_ids} <= validated_ids


def test_a_truncated_path_set_without_a_reason_cannot_be_built() -> None:
    """The extractor always supplies one. This is the guard for anyone hand-building a set."""
    with pytest.raises(ValidationError, match="must carry a truncation_reason"):
        PathSet(paths=[], truncated=True)
