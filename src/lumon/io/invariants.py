"""Semantic validation for attack graphs."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from lumon.model import AttackGraph, Edge, EdgeType, Evidence, Node, NodeType

ENABLER_TYPES = frozenset({NodeType.VULNERABILITY, NodeType.CREDENTIAL})
CROSSES_BOUNDARY_ATTRIBUTE = "crosses_boundary"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class Violation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    severity: Severity
    message: str
    subject_id: str | None = None


class InvariantReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    violations: list[Violation]

    @property
    def errors(self) -> list[Violation]:
        return [violation for violation in self.violations if violation.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Violation]:
        return [
            violation for violation in self.violations if violation.severity is Severity.WARNING
        ]

    @property
    def is_usable(self) -> bool:
        return not self.errors


class GraphInvariantError(Exception):
    """Graph is not usable for analysis."""


def check_invariants(graph: AttackGraph) -> InvariantReport:
    """Return all semantic violations without raising."""
    return InvariantReport(
        violations=[
            *_check_graph_completeness(graph),
            *_check_edge_endpoints(graph),
            *_check_edge_enablers(graph),
            *_check_boundary_crossings(graph),
            *_check_node_connectivity(graph),
        ]
    )


def assert_usable(graph: AttackGraph) -> None:
    """Raise if the graph has any error-level violations."""
    report = check_invariants(graph)
    if not report.is_usable:
        listed = "\n".join(
            f"  {violation.code}: {violation.message}" for violation in report.errors
        )
        raise GraphInvariantError(f"graph is not usable for analysis:\n{listed}")


def _check_graph_completeness(graph: AttackGraph) -> list[Violation]:
    violations: list[Violation] = []
    if not graph.entry_points():
        violations.append(
            Violation(
                code="NO_ENTRY_POINTS",
                severity=Severity.ERROR,
                message="graph has no entry point nodes, so no attack path can start",
            )
        )
    if not graph.objectives():
        violations.append(
            Violation(
                code="NO_OBJECTIVES",
                severity=Severity.ERROR,
                message="graph has no objective nodes, so no attack path has a destination",
            )
        )
    if not graph.validated_edges():
        violations.append(
            Violation(
                code="NO_VALIDATED_EDGES",
                severity=Severity.ERROR,
                message=(
                    "graph has no validated edges, and only a validated edge may affect a result"
                ),
            )
        )
    return violations


def _check_edge_endpoints(graph: AttackGraph) -> list[Violation]:
    node_ids = {node.id for node in graph.nodes}
    violations: list[Violation] = []
    for edge in graph.edges:
        if edge.source not in node_ids:
            violations.append(
                _edge_error(
                    "DANGLING_EDGE_SOURCE", edge.id, f"starts at {edge.source!r}, not a node"
                )
            )
        if edge.target not in node_ids:
            violations.append(
                _edge_error("DANGLING_EDGE_TARGET", edge.id, f"ends at {edge.target!r}, not a node")
            )
    return violations


def _check_edge_enablers(graph: AttackGraph) -> list[Violation]:
    node_types = {node.id: node.type for node in graph.nodes}
    return [
        violation
        for edge in graph.edges
        if (violation := _check_edge_enabler(edge, node_types)) is not None
    ]


def _check_edge_enabler(edge: Edge, node_types: dict[str, NodeType]) -> Violation | None:
    if edge.enabled_by is None:
        if _is_validated_exploit(edge):
            return _edge_error(
                "EXPLOITS_WITHOUT_ENABLED_BY", edge.id, "has no enabled_by vulnerability"
            )
        return None

    enabler_type = node_types.get(edge.enabled_by)
    if enabler_type is None:
        return _edge_error(
            "DANGLING_ENABLED_BY", edge.id, f"is enabled by {edge.enabled_by!r}, not a node"
        )
    if _is_validated_exploit(edge) and enabler_type is not NodeType.VULNERABILITY:
        return _edge_error(
            "EXPLOITS_ENABLED_BY_NON_VULNERABILITY",
            edge.id,
            f"is a validated exploit enabled by {edge.enabled_by!r}, a {enabler_type} node",
        )
    if enabler_type in ENABLER_TYPES:
        return None
    return Violation(
        code="ENABLED_BY_WRONG_TYPE",
        severity=Severity.WARNING,
        message=(
            f"edge {edge.id!r} is enabled by {edge.enabled_by!r}, which is a "
            f"{enabler_type} node; only a vulnerability or a credential enables a transition"
        ),
        subject_id=edge.id,
    )


def _is_validated_exploit(edge: Edge) -> bool:
    return edge.evidence is Evidence.VALIDATED and edge.type is EdgeType.EXPLOITS


def _check_boundary_crossings(graph: AttackGraph) -> list[Violation]:
    node_types = {node.id: node.type for node in graph.nodes}
    return [
        violation
        for edge in graph.validated_edges()
        if edge.type is EdgeType.REACHES
        if (violation := _check_boundary_crossing(edge, node_types)) is not None
    ]


def _check_boundary_crossing(edge: Edge, node_types: dict[str, NodeType]) -> Violation | None:
    boundary_id = edge.attributes.get(CROSSES_BOUNDARY_ATTRIBUTE)
    if boundary_id is None:
        return None
    boundary_type = node_types.get(boundary_id)
    if boundary_type is None:
        return _edge_error(
            "DANGLING_CROSSES_BOUNDARY",
            edge.id,
            f"crosses boundary {boundary_id!r}, not a node",
        )
    if boundary_type is NodeType.BOUNDARY:
        return None
    return Violation(
        code="CROSSES_BOUNDARY_WRONG_TYPE",
        severity=Severity.WARNING,
        message=(
            f"edge {edge.id!r} says it crosses {boundary_id!r}, which is a "
            f"{boundary_type} node; crosses_boundary must name a boundary node"
        ),
        subject_id=edge.id,
    )


def _check_node_connectivity(graph: AttackGraph) -> list[Violation]:
    referenced = {
        node_id
        for edge in graph.edges
        for node_id in (edge.source, edge.target, edge.enabled_by)
        if node_id is not None
    } | {
        boundary_id
        for edge in graph.edges
        if edge.type is EdgeType.REACHES
        if (boundary_id := edge.attributes.get(CROSSES_BOUNDARY_ATTRIBUTE)) is not None
    }
    validated_sources = {edge.source for edge in graph.validated_edges()}
    validated_targets = {edge.target for edge in graph.validated_edges()}

    violations: list[Violation] = []
    for node in graph.nodes:
        if node.id not in referenced:
            violations.append(_node_warning("ORPHAN_NODE", node, "is referenced by no edge"))
        if node.type is NodeType.OBJECTIVE and node.id not in validated_targets:
            violations.append(
                _node_warning("UNREACHABLE_OBJECTIVE", node, "has no inbound validated edge")
            )
        if node.type is NodeType.ENTRY_POINT and node.id not in validated_sources:
            violations.append(
                _node_warning("DEAD_ENTRY_POINT", node, "has no outbound validated edge")
            )
    return violations


def _edge_error(code: str, edge_id: str, problem: str) -> Violation:
    return Violation(
        code=code,
        severity=Severity.ERROR,
        message=f"edge {edge_id!r} {problem}",
        subject_id=edge_id,
    )


def _node_warning(code: str, node: Node, problem: str) -> Violation:
    return Violation(
        code=code,
        severity=Severity.WARNING,
        message=f"{node.type} node {node.id!r} {problem}",
        subject_id=node.id,
    )
