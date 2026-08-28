import pytest
from pydantic import ValidationError

from lumon.model import AttackGraph, Edge, EdgeType, Evidence, Node, NodeType


def _build_graph() -> AttackGraph:
    return AttackGraph(
        nodes=[
            Node(id="n_entry", type=NodeType.ENTRY_POINT, label="internet-facing ingress"),
            Node(id="n_service", type=NodeType.SERVICE, label="checkout-api"),
            Node(id="n_vuln", type=NodeType.VULNERABILITY, label="unauthenticated RCE"),
            Node(id="n_identity", type=NodeType.IDENTITY, label="checkout-api service account"),
            Node(id="n_cred", type=NodeType.CREDENTIAL, label="cloud key in mounted secret"),
            Node(id="n_cloud", type=NodeType.OBJECTIVE, label="cloud account", weight=10.0),
        ],
        edges=[
            Edge(
                id="e_reach",
                source="n_entry",
                target="n_service",
                type=EdgeType.REACHES,
                evidence=Evidence.VALIDATED,
            ),
            Edge(
                id="e_exploit",
                source="n_service",
                target="n_identity",
                type=EdgeType.EXPLOITS,
                evidence=Evidence.VALIDATED,
                enabled_by="n_vuln",
            ),
            Edge(
                id="e_read",
                source="n_identity",
                target="n_cred",
                type=EdgeType.READS,
                evidence=Evidence.VALIDATED,
            ),
            Edge(
                id="e_auth",
                source="n_cred",
                target="n_cloud",
                type=EdgeType.AUTHENTICATES_AS,
                evidence=Evidence.VALIDATED,
            ),
            Edge(
                id="e_observed",
                source="n_service",
                target="n_cloud",
                type=EdgeType.CAN_ACCESS,
                evidence=Evidence.OBSERVED,
            ),
            Edge(
                id="e_inferred",
                source="n_identity",
                target="n_cloud",
                type=EdgeType.CAN_ACCESS,
                evidence=Evidence.INFERRED,
            ),
        ],
        metadata={"graph_id": "demo-001"},
    )


def test_accessors_return_the_right_things() -> None:
    graph = _build_graph()

    assert graph.node_by_id("n_cloud").label == "cloud account"
    assert graph.edge_by_id("e_exploit").enabled_by == "n_vuln"
    assert [node.id for node in graph.nodes_of_type(NodeType.CREDENTIAL)] == ["n_cred"]
    assert [edge.id for edge in graph.edges_of_type(EdgeType.CAN_ACCESS)] == [
        "e_observed",
        "e_inferred",
    ]
    assert [node.id for node in graph.entry_points()] == ["n_entry"]
    assert [node.id for node in graph.objectives()] == ["n_cloud"]


def test_lookups_raise_key_error_for_unknown_ids() -> None:
    graph = _build_graph()

    with pytest.raises(KeyError):
        graph.node_by_id("n_missing")
    with pytest.raises(KeyError):
        graph.edge_by_id("e_missing")


def test_validated_edges_excludes_observed_and_inferred() -> None:
    graph = _build_graph()

    assert [edge.id for edge in graph.validated_edges()] == [
        "e_reach",
        "e_exploit",
        "e_read",
        "e_auth",
    ]


def test_objective_without_weight_is_rejected() -> None:
    with pytest.raises(ValidationError, match="weight greater than 0"):
        Node(id="n_cloud", type=NodeType.OBJECTIVE, label="cloud account")


@pytest.mark.parametrize("weight", [0.0, -1.0])
def test_objective_with_non_positive_weight_is_rejected(weight: float) -> None:
    with pytest.raises(ValidationError, match="weight greater than 0"):
        Node(id="n_cloud", type=NodeType.OBJECTIVE, label="cloud account", weight=weight)


def test_non_objective_with_weight_is_rejected() -> None:
    with pytest.raises(ValidationError, match="may not carry a weight"):
        Node(id="n_service", type=NodeType.SERVICE, label="checkout-api", weight=10.0)


def test_self_loop_edge_is_rejected() -> None:
    with pytest.raises(ValidationError, match="self-loop"):
        Edge(
            id="e_loop",
            source="n_service",
            target="n_service",
            type=EdgeType.REACHES,
            evidence=Evidence.VALIDATED,
        )


def test_duplicate_node_ids_are_rejected() -> None:
    node = Node(id="n_service", type=NodeType.SERVICE, label="checkout-api")

    with pytest.raises(ValidationError, match="duplicate node ids: n_service"):
        AttackGraph(nodes=[node, node], edges=[])


def test_duplicate_edge_ids_are_rejected() -> None:
    edge = Edge(
        id="e_reach",
        source="n_entry",
        target="n_service",
        type=EdgeType.REACHES,
        evidence=Evidence.VALIDATED,
    )

    with pytest.raises(ValidationError, match="duplicate edge ids: e_reach"):
        AttackGraph(nodes=[], edges=[edge, edge])


@pytest.mark.parametrize("bad_id", ["", " ", "n service", "n_service\n"])
def test_empty_or_whitespace_ids_are_rejected(bad_id: str) -> None:
    with pytest.raises(ValidationError, match="non-empty and contain no whitespace"):
        Node(id=bad_id, type=NodeType.SERVICE, label="checkout-api")

    with pytest.raises(ValidationError, match="non-empty and contain no whitespace"):
        Edge(
            id=bad_id,
            source="n_entry",
            target="n_service",
            type=EdgeType.REACHES,
            evidence=Evidence.VALIDATED,
        )


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Node(  # type: ignore[call-arg]
            id="n_service",
            type=NodeType.SERVICE,
            label="checkout-api",
            severity="high",
        )


def test_model_fields_cannot_be_reassigned() -> None:
    graph = _build_graph()

    with pytest.raises(ValidationError, match="frozen"):
        graph.nodes[0].label = "renamed"
    with pytest.raises(ValidationError, match="frozen"):
        graph.edges[0].evidence = Evidence.INFERRED


def test_json_round_trip_preserves_the_graph() -> None:
    graph = _build_graph()

    assert AttackGraph.model_validate_json(graph.model_dump_json()) == graph


def test_graph_allows_dangling_edges() -> None:
    graph = AttackGraph(
        nodes=[Node(id="n_entry", type=NodeType.ENTRY_POINT, label="ingress")],
        edges=[
            Edge(
                id="e_reach",
                source="n_entry",
                target="n_absent",
                type=EdgeType.REACHES,
                evidence=Evidence.VALIDATED,
            )
        ],
    )

    assert graph.edge_by_id("e_reach").target == "n_absent"
