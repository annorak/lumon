from pathlib import Path

import pytest

from lumon.io import GraphInvariantError, Severity, Violation, assert_usable, check_invariants
from lumon.io.loader import load_graph
from lumon.model import AttackGraph, Edge, EdgeType, Evidence, Node, NodeType

ENTRY = Node(id="n_entry", type=NodeType.ENTRY_POINT, label="internet-facing ingress")
SERVICE = Node(id="n_service", type=NodeType.SERVICE, label="checkout-api")
CLOUD = Node(id="n_cloud", type=NodeType.OBJECTIVE, label="production cloud account", weight=10.0)


def _edge(
    edge_id: str,
    source: str,
    target: str,
    evidence: Evidence = Evidence.VALIDATED,
    enabled_by: str | None = None,
    edge_type: EdgeType = EdgeType.REACHES,
    attributes: dict[str, str] | None = None,
) -> Edge:
    return Edge(
        id=edge_id,
        source=source,
        target=target,
        type=edge_type,
        evidence=evidence,
        enabled_by=enabled_by,
        attributes={} if attributes is None else attributes,
    )


def _violations_with_code(graph: AttackGraph, code: str) -> list[Violation]:
    return [violation for violation in check_invariants(graph).violations if violation.code == code]


def test_dangling_edge_source() -> None:
    graph = AttackGraph(nodes=[ENTRY, CLOUD], edges=[_edge("e_reach", "n_absent", "n_cloud")])

    [violation] = _violations_with_code(graph, "DANGLING_EDGE_SOURCE")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id == "e_reach"


def test_dangling_edge_target() -> None:
    graph = AttackGraph(nodes=[ENTRY, CLOUD], edges=[_edge("e_reach", "n_entry", "n_absent")])

    [violation] = _violations_with_code(graph, "DANGLING_EDGE_TARGET")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id == "e_reach"


def test_dangling_enabled_by() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, CLOUD],
        edges=[_edge("e_reach", "n_entry", "n_cloud", enabled_by="n_absent")],
    )

    [violation] = _violations_with_code(graph, "DANGLING_ENABLED_BY")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id == "e_reach"


def test_no_entry_points() -> None:
    graph = AttackGraph(nodes=[SERVICE, CLOUD], edges=[_edge("e_access", "n_service", "n_cloud")])

    [violation] = _violations_with_code(graph, "NO_ENTRY_POINTS")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id is None


def test_no_objectives(graphs_dir: Path) -> None:
    graph = load_graph(graphs_dir / "no_objective.json")

    [violation] = _violations_with_code(graph, "NO_OBJECTIVES")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id is None


def test_no_validated_edges() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, CLOUD],
        edges=[_edge("e_reach", "n_entry", "n_cloud", evidence=Evidence.OBSERVED)],
    )

    [violation] = _violations_with_code(graph, "NO_VALIDATED_EDGES")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id is None


def test_orphan_node() -> None:
    graph = _graph_with_orphan()

    [violation] = _violations_with_code(graph, "ORPHAN_NODE")
    assert violation.severity is Severity.WARNING
    assert violation.subject_id == "n_service"


def test_unreachable_objective() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, SERVICE, CLOUD],
        edges=[
            _edge("e_reach", "n_entry", "n_service"),
            _edge("e_access", "n_service", "n_cloud", evidence=Evidence.OBSERVED),
        ],
    )

    [violation] = _violations_with_code(graph, "UNREACHABLE_OBJECTIVE")
    assert violation.severity is Severity.WARNING
    assert violation.subject_id == "n_cloud"


def test_dead_entry_point() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, SERVICE, CLOUD],
        edges=[
            _edge("e_reach", "n_entry", "n_service", evidence=Evidence.OBSERVED),
            _edge("e_access", "n_service", "n_cloud"),
        ],
    )

    [violation] = _violations_with_code(graph, "DEAD_ENTRY_POINT")
    assert violation.severity is Severity.WARNING
    assert violation.subject_id == "n_entry"


def test_enabled_by_wrong_type() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, SERVICE, CLOUD],
        edges=[_edge("e_reach", "n_entry", "n_cloud", enabled_by="n_service")],
    )

    [violation] = _violations_with_code(graph, "ENABLED_BY_WRONG_TYPE")
    assert violation.severity is Severity.WARNING
    assert violation.subject_id == "e_reach"


def test_validated_exploit_without_enabled_by_is_an_error() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, CLOUD],
        edges=[
            _edge(
                "e_exploit",
                "n_entry",
                "n_cloud",
                edge_type=EdgeType.EXPLOITS,
            )
        ],
    )

    [violation] = _violations_with_code(graph, "EXPLOITS_WITHOUT_ENABLED_BY")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id == "e_exploit"


def test_validated_exploit_requires_a_vulnerability_enabler() -> None:
    credential = Node(id="n_credential", type=NodeType.CREDENTIAL, label="credential")
    graph = AttackGraph(
        nodes=[ENTRY, CLOUD, credential],
        edges=[
            _edge(
                "e_exploit",
                "n_entry",
                "n_cloud",
                enabled_by="n_credential",
                edge_type=EdgeType.EXPLOITS,
            )
        ],
    )

    [violation] = _violations_with_code(graph, "EXPLOITS_ENABLED_BY_NON_VULNERABILITY")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id == "e_exploit"


def test_non_validated_exploit_may_omit_enabled_by() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, CLOUD],
        edges=[
            _edge("e_reach", "n_entry", "n_cloud"),
            _edge(
                "e_observed_exploit",
                "n_entry",
                "n_cloud",
                evidence=Evidence.OBSERVED,
                edge_type=EdgeType.EXPLOITS,
            ),
        ],
    )

    assert _violations_with_code(graph, "EXPLOITS_WITHOUT_ENABLED_BY") == []


def test_crosses_boundary_must_reference_a_node() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, CLOUD],
        edges=[
            _edge(
                "e_cross",
                "n_entry",
                "n_cloud",
                attributes={"crosses_boundary": "n_absent"},
            )
        ],
    )

    [violation] = _violations_with_code(graph, "DANGLING_CROSSES_BOUNDARY")
    assert violation.severity is Severity.ERROR
    assert violation.subject_id == "e_cross"


def test_crosses_boundary_warns_when_the_node_is_not_a_boundary() -> None:
    graph = AttackGraph(
        nodes=[ENTRY, SERVICE, CLOUD],
        edges=[
            _edge(
                "e_cross",
                "n_entry",
                "n_cloud",
                attributes={"crosses_boundary": "n_service"},
            )
        ],
    )

    [violation] = _violations_with_code(graph, "CROSSES_BOUNDARY_WRONG_TYPE")
    assert violation.severity is Severity.WARNING
    assert violation.subject_id == "e_cross"


def test_crosses_boundary_counts_as_a_node_reference() -> None:
    boundary = Node(id="n_boundary", type=NodeType.BOUNDARY, label="boundary")
    graph = AttackGraph(
        nodes=[ENTRY, boundary, CLOUD],
        edges=[
            _edge(
                "e_cross",
                "n_entry",
                "n_cloud",
                attributes={"crosses_boundary": "n_boundary"},
            )
        ],
    )

    assert _violations_with_code(graph, "ORPHAN_NODE") == []


def test_a_vulnerability_or_credential_enabler_is_accepted(graphs_dir: Path) -> None:
    graph = load_graph(graphs_dir / "valid_small.json")

    assert {edge.enabled_by for edge in graph.edges} == {None, "n_vuln", "n_cred"}
    assert _violations_with_code(graph, "ENABLED_BY_WRONG_TYPE") == []


def test_a_clean_graph_has_no_violations(graphs_dir: Path) -> None:
    report = check_invariants(load_graph(graphs_dir / "valid_small.json"))

    assert report.violations == []
    assert report.is_usable is True


def test_warnings_alone_leave_the_graph_usable() -> None:
    report = check_invariants(_graph_with_orphan())

    assert report.errors == []
    assert [violation.code for violation in report.warnings] == ["ORPHAN_NODE"]
    assert report.is_usable is True


def test_any_error_makes_the_graph_unusable(graphs_dir: Path) -> None:
    report = check_invariants(load_graph(graphs_dir / "dangling_edge.json"))

    assert [violation.code for violation in report.errors] == ["DANGLING_EDGE_TARGET"]
    assert report.is_usable is False


def test_a_dangling_edge_hides_the_path_rather_than_crashing(graphs_dir: Path) -> None:
    report = check_invariants(load_graph(graphs_dir / "dangling_edge.json"))

    assert {violation.code for violation in report.warnings} == {
        "ORPHAN_NODE",
        "UNREACHABLE_OBJECTIVE",
    }


def test_assert_usable_raises_on_an_error_and_lists_it(graphs_dir: Path) -> None:
    graph = load_graph(graphs_dir / "dangling_edge.json")

    with pytest.raises(GraphInvariantError, match="DANGLING_EDGE_TARGET"):
        assert_usable(graph)


def test_assert_usable_is_silent_when_there_are_only_warnings() -> None:
    assert_usable(_graph_with_orphan())


def _graph_with_orphan() -> AttackGraph:
    return AttackGraph(
        nodes=[ENTRY, SERVICE, CLOUD], edges=[_edge("e_reach", "n_entry", "n_cloud")]
    )
