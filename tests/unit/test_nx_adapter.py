from pathlib import Path

import pytest

from lumon.io import load_graph, to_networkx
from lumon.model import AttackGraph, Evidence


@pytest.fixture
def graph(graphs_dir: Path) -> AttackGraph:
    return load_graph(graphs_dir / "valid_small.json")


def test_every_node_and_edge_survives_conversion(graph: AttackGraph) -> None:
    converted = to_networkx(graph)

    assert converted.number_of_nodes() == len(graph.nodes)
    assert converted.number_of_edges() == len(graph.edges)


def test_nodes_carry_the_full_node(graph: AttackGraph) -> None:
    converted = to_networkx(graph)

    assert converted.nodes["n_cloud"]["node"] == graph.node_by_id("n_cloud")


def test_validated_only_drops_weaker_edges_and_keeps_every_node(graph: AttackGraph) -> None:
    converted = to_networkx(graph, validated_only=True)

    assert converted.number_of_nodes() == len(graph.nodes)
    assert converted.number_of_edges() == len(graph.validated_edges())
    assert all(
        data["edge"].evidence is Evidence.VALIDATED for *_, data in converted.edges(data=True)
    )


def test_parallel_edges_between_one_pair_both_survive(graph: AttackGraph) -> None:
    converted = to_networkx(graph)

    assert converted.number_of_edges("n_identity", "n_cloud") == 2


def test_edges_are_retrievable_by_edge_id(graph: AttackGraph) -> None:
    converted = to_networkx(graph)

    assert converted.edges["n_identity", "n_cloud", "e_identity_access"][
        "edge"
    ] == graph.edge_by_id("e_identity_access")
