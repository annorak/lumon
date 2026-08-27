"""Whether a graph is usable for analysis, and what is wrong with it if it is not.

Checking **returns a report and never raises**, because a malformed graph is not a crash,
it is a quietly wrong answer. Consider an edge whose target is `n_clod` where the author
meant `n_cloud`. Nothing fails: the graph loads, the path enumerator simply never finds a
route to the objective, the solver dutifully severs the paths it was given, and the report
says the environment has fewer attack paths than it really does. Under-reporting risk is the
worst thing this system can do. So a caller gets the whole list of problems at once, decides
what to do about it, and can hand that list back to whoever supplied the graph.

`assert_usable` is the strict door, for callers that want the pipeline to stop instead.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from lumon.model import AttackGraph, Node, NodeType

ENABLER_TYPES = frozenset({NodeType.VULNERABILITY, NodeType.CREDENTIAL})
"""The node types that can make a transition possible. An edge's `enabled_by` naming
anything else is a modelling mistake rather than a broken reference."""


class Severity(StrEnum):
    """`ERROR` means analysis over this graph would produce a wrong answer. `WARNING` means
    the graph is analysable but something in it is probably not what its author intended."""

    ERROR = "error"
    WARNING = "warning"


class Violation(BaseModel):
    """One thing wrong with a graph. `subject_id` is the node or edge at fault, or `None`
    for a problem with the graph as a whole."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    severity: Severity
    message: str
    subject_id: str | None = None


class InvariantReport(BaseModel):
    """Everything `check_invariants` found."""

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
        """True when nothing found would make the analysis wrong. Warnings do not block."""
        return not self.errors


class GraphInvariantError(Exception):
    """A graph failed at least one `ERROR` invariant."""


def check_invariants(graph: AttackGraph) -> InvariantReport:
    """Everything wrong with this graph. Never raises — see the module docstring."""
    return InvariantReport(
        violations=[
            *_check_graph_completeness(graph),
            *_check_edge_endpoints(graph),
            *_check_edge_enablers(graph),
            *_check_node_connectivity(graph),
        ]
    )


def assert_usable(graph: AttackGraph) -> None:
    """Raise `GraphInvariantError` listing every error, if the graph is not usable."""
    report = check_invariants(graph)
    if not report.is_usable:
        listed = "\n".join(
            f"  {violation.code}: {violation.message}" for violation in report.errors
        )
        raise GraphInvariantError(f"graph is not usable for analysis:\n{listed}")


def _check_graph_completeness(graph: AttackGraph) -> list[Violation]:
    """The three things without which there is nothing to analyse: somewhere to start,
    somewhere worth reaching, and a transition an attacker actually proved."""
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
    """Edges pointing at nodes the graph does not contain. This is the check the whole module
    exists for: an unresolvable endpoint silently deletes an attack path."""
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
    """Edges whose `enabled_by` does not resolve, or resolves to something that cannot make a
    transition possible."""
    node_types = {node.id: node.type for node in graph.nodes}
    violations: list[Violation] = []
    for edge in graph.edges:
        if edge.enabled_by is None:
            continue
        enabler_type = node_types.get(edge.enabled_by)
        if enabler_type is None:
            violations.append(
                _edge_error(
                    "DANGLING_ENABLED_BY", edge.id, f"is enabled by {edge.enabled_by!r}, not a node"
                )
            )
        elif enabler_type not in ENABLER_TYPES:
            violations.append(
                Violation(
                    code="ENABLED_BY_WRONG_TYPE",
                    severity=Severity.WARNING,
                    message=(
                        f"edge {edge.id!r} is enabled by {edge.enabled_by!r}, which is a "
                        f"{enabler_type} node; only a vulnerability or a credential enables "
                        "a transition"
                    ),
                    subject_id=edge.id,
                )
            )
    return violations


def _check_node_connectivity(graph: AttackGraph) -> list[Violation]:
    """Nodes not wired into anything the analysis will traverse. All warnings: the graph is
    still analysable as it stands, and each of these usually means it is incomplete.

    A node counts as referenced if any edge names it as source, target, *or* `enabled_by`.
    Vulnerability nodes are only ever named by `enabled_by`, so leaving that out would flag
    every one of them and make the warning worthless.
    """
    referenced = {
        node_id
        for edge in graph.edges
        for node_id in (edge.source, edge.target, edge.enabled_by)
        if node_id is not None
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
