"""Tests for the synthetic attack graph generator.

The generator knows its answers by construction, so most of these tests check that what it
claimed is genuinely *present in* the graph, rather than deriving the claim from the graph and
comparing it to itself.

`validated_node_sequences` is the one place enumeration happens. It re-derives the path set
with NetworkX's simple-path search and confirms it matches the constructed ground truth
exactly. That is still the safe direction: the expectation comes from the construction, and
NetworkX is not code this project is testing. Once task 05 lands, its extractor gets checked
against the same ground truth, and it must not be substituted in here.
"""

import itertools
from collections import Counter

import networkx as nx
import pytest
from pydantic import ValidationError

from lumon.generate import PRESETS, REALISTIC, GeneratorParams, GroundTruth, generate
from lumon.io import check_invariants, to_networkx
from lumon.model import AttackGraph, Evidence, NodeType

PRESET_NAMES = sorted(PRESETS)


def validated_node_sequences(graph: AttackGraph) -> set[tuple[str, ...]]:
    """Every entry-to-objective simple path over validated edges alone, found independently
    of anything the generator recorded."""
    view = to_networkx(graph, validated_only=True)
    return {
        tuple(sequence)
        for entry in graph.entry_points()
        for objective in graph.objectives()
        for sequence in nx.all_simple_paths(view, entry.id, objective.id)
    }


def test_the_same_seed_produces_a_byte_identical_graph() -> None:
    first_graph, first_truth = generate(REALISTIC)
    second_graph, second_truth = generate(REALISTIC)

    assert first_graph.model_dump_json() == second_graph.model_dump_json()
    assert first_truth == second_truth


def test_different_seeds_produce_different_graphs() -> None:
    first_graph, _ = generate(GeneratorParams(seed=11))
    second_graph, _ = generate(GeneratorParams(seed=12))

    assert first_graph.model_dump_json() != second_graph.model_dump_json()


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_every_preset_generates_a_clean_graph(name: str) -> None:
    graph, _ = generate(PRESETS[name])

    assert check_invariants(graph).violations == []


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_every_ground_truth_path_is_a_chain_of_validated_edges(name: str) -> None:
    """Confirms the truth is present in the graph. Every consecutive pair in a claimed path
    has to be an actual validated edge, and the ends have to be an entry and an objective."""
    graph, truth = generate(PRESETS[name])
    validated_pairs = {(edge.source, edge.target) for edge in graph.validated_edges()}

    for sequence in truth.path_node_sequences:
        assert set(itertools.pairwise(sequence)) <= validated_pairs
        assert graph.node_by_id(sequence[0]).type is NodeType.ENTRY_POINT
        assert graph.node_by_id(sequence[-1]).type is NodeType.OBJECTIVE


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_validated_edges_alone_produce_exactly_the_ground_truth_paths(name: str) -> None:
    """The load-bearing test: no decoy edge invents a validated path, and no validated path
    exists that the generator failed to record."""
    graph, truth = generate(PRESETS[name])

    assert validated_node_sequences(graph) == {tuple(path) for path in truth.path_node_sequences}


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_every_planted_chokepoint_lies_on_every_path(name: str) -> None:
    _, truth = generate(PRESETS[name])

    assert truth.planted_chokepoint_ids != []
    for chokepoint in truth.planted_chokepoint_ids:
        assert all(chokepoint in sequence for sequence in truth.path_node_sequences)
    assert truth.minimum_chokepoint_cover_size == 1


@pytest.mark.parametrize("name", PRESET_NAMES)
def test_every_decoy_edge_follows_a_route_the_validated_graph_already_has(name: str) -> None:
    """The rule that makes decoys safe: a non-validated edge only ever names a transition the
    validated backbone can already make, so it adds no reachability of its own."""
    graph, _ = generate(PRESETS[name])
    view = to_networkx(graph, validated_only=True)
    decoys = [edge for edge in graph.edges if edge.evidence is not Evidence.VALIDATED]

    assert decoys != []
    for edge in decoys:
        assert nx.has_path(view, edge.source, edge.target)


@pytest.mark.parametrize(("depth", "branching"), [(1, 2), (3, 2), (3, 4), (5, 3)])
def test_node_and_edge_counts_scale_with_depth_and_branching(depth: int, branching: int) -> None:
    """Counts are stated here independently of the generator. With no chokepoint every
    intermediate layer is `branching` wide, which makes all three formulas closed form."""
    params = GeneratorParams(
        seed=7,
        n_entry_points=2,
        n_objectives=3,
        depth=depth,
        branching=branching,
        n_planted_chokepoints=0,
        observed_edge_ratio=0.0,
        inferred_edge_ratio=0.0,
    )

    graph, truth = generate(params)

    assert len(graph.nodes) == 2 + depth * branching + 3
    assert len(graph.edges) == 2 * branching + (depth - 1) * branching**2 + branching * 3
    assert len(truth.path_node_sequences) == 2 * branching**depth * 3


def test_realistic_sits_at_engagement_scale() -> None:
    _, truth = generate(REALISTIC)

    assert 30 <= len(truth.path_node_sequences) <= 50


def test_non_validated_edges_appear_in_the_declared_ratios() -> None:
    params = GeneratorParams(
        seed=8,
        n_entry_points=3,
        n_objectives=3,
        depth=4,
        branching=3,
        observed_edge_ratio=0.25,
        inferred_edge_ratio=0.5,
    )

    graph, _ = generate(params)

    counted = Counter(edge.evidence for edge in graph.edges)
    validated = counted[Evidence.VALIDATED]
    assert counted[Evidence.OBSERVED] == round(0.25 * validated)
    assert counted[Evidence.INFERRED] == round(0.5 * validated)
    assert counted[Evidence.OBSERVED] / validated == pytest.approx(0.25, abs=0.05)
    assert counted[Evidence.INFERRED] / validated == pytest.approx(0.5, abs=0.05)


def test_a_graph_can_be_generated_with_no_decoy_edges_at_all() -> None:
    params = GeneratorParams(seed=14, observed_edge_ratio=0.0, inferred_edge_ratio=0.0)

    graph, _ = generate(params)

    assert graph.edges == graph.validated_edges()


def test_objective_weights_stay_inside_the_requested_range() -> None:
    params = GeneratorParams(seed=9, n_objectives=8, objective_weight_range=(3, 5))

    graph, truth = generate(params)

    assert truth.objective_weights == {node.id: node.weight for node in graph.objectives()}
    assert all(3 <= weight <= 5 for weight in truth.objective_weights.values())


def test_a_graph_with_no_planted_chokepoint_reports_no_cover() -> None:
    graph, truth = generate(GeneratorParams(seed=10, n_planted_chokepoints=0))

    assert truth.planted_chokepoint_ids == []
    assert truth.minimum_chokepoint_cover_size == 0
    assert validated_node_sequences(graph) == {tuple(path) for path in truth.path_node_sequences}


def test_graph_id_distinguishes_shapes_that_share_a_seed() -> None:
    """Two graphs from one seed but different shapes are different graphs, and their ids have
    to say so, or a stale pairing of a graph with a path set would go unnoticed."""
    first_graph, _ = generate(GeneratorParams(seed=13, depth=2))
    second_graph, _ = generate(GeneratorParams(seed=13, depth=3))

    assert first_graph.metadata["graph_id"] != second_graph.metadata["graph_id"]


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="seed is required"),
        pytest.param({"seed": 1, "n_entry_points": 0}, id="needs an entry point"),
        pytest.param({"seed": 1, "n_objectives": 0}, id="needs an objective"),
        pytest.param({"seed": 1, "depth": 0}, id="needs a hop"),
        pytest.param({"seed": 1, "branching": 0}, id="needs a route"),
        pytest.param({"seed": 1, "depth": 3, "n_planted_chokepoints": 4}, id="chokepoints exceed"),
        pytest.param({"seed": 1, "observed_edge_ratio": 1.5}, id="ratio above one"),
        pytest.param({"seed": 1, "inferred_edge_ratio": -0.1}, id="ratio below zero"),
        pytest.param({"seed": 1, "objective_weight_range": (0, 5)}, id="weight of zero"),
        pytest.param({"seed": 1, "objective_weight_range": (5, 1)}, id="range backwards"),
        pytest.param({"seed": 1, "unknown_knob": 3}, id="unknown field"),
    ],
)
def test_invalid_params_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GeneratorParams.model_validate(overrides)


def test_a_chokepoint_cover_larger_than_the_planted_set_is_rejected() -> None:
    with pytest.raises(ValidationError, match="minimum_chokepoint_cover_size"):
        GroundTruth(
            path_node_sequences=[["n_entry_00", "n_obj_00"]],
            planted_chokepoint_ids=[],
            minimum_chokepoint_cover_size=1,
            objective_weights={"n_obj_00": 1.0},
        )
