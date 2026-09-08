"""Deterministically synthesize changes from validated attacker transitions.

A boundary crossing is a property of traversal. A ``REACHES`` edge crosses a boundary
only when its ``crosses_boundary`` attribute names that boundary. Ending at a boundary
does not count as crossing it.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import cast

from lumon.interventions.defaults import DEFAULT_COSTS
from lumon.io.invariants import CROSSES_BOUNDARY_ATTRIBUTE, assert_usable
from lumon.model import (
    AttackGraph,
    Edge,
    EdgeType,
    Intervention,
    InterventionCatalog,
    InterventionClass,
    NodeType,
)

type _GroupKey = tuple[InterventionClass, str]

_NAME_PREFIXES = {
    InterventionClass.VULNERABILITY_PATCH: "Patch vulnerability",
    InterventionClass.ACCESS_CONTROL_ADD: "Add access control at",
    InterventionClass.IDENTITY_PERMISSION_REDUCTION: "Downscope identity",
    InterventionClass.CREDENTIAL_REMOVAL: "Remove credential",
    InterventionClass.NETWORK_SEGMENTATION: "Segment boundary",
    InterventionClass.CONTAINER_HARDENING: "Harden container or host",
    InterventionClass.EXECUTION_CONTEXT_REBIND: "Rebind execution context",
}


@dataclass(frozen=True)
class _Candidate:
    intervention_class: InterventionClass
    target_node_id: str
    removes_edge_ids: frozenset[str]

    @property
    def name(self) -> str:
        return f"{_NAME_PREFIXES[self.intervention_class]} {self.target_node_id}"


def synthesize(graph: AttackGraph) -> InterventionCatalog:
    """Return the deterministic intervention catalog for a usable graph."""
    assert_usable(graph)
    candidates = sorted(_deduplicate(_build_candidates(graph)), key=_candidate_sort_key)
    return InterventionCatalog(
        interventions=[
            Intervention(
                id=f"INT-{index:03d}",
                name=candidate.name,
                intervention_class=candidate.intervention_class,
                removes_edge_ids=candidate.removes_edge_ids,
                cost=DEFAULT_COSTS[candidate.intervention_class],
                target_node_id=candidate.target_node_id,
            )
            for index, candidate in enumerate(candidates)
        ]
    )


def _build_candidates(graph: AttackGraph) -> list[_Candidate]:
    return [
        _Candidate(
            intervention_class=intervention_class,
            target_node_id=target_node_id,
            removes_edge_ids=frozenset(edge_ids),
        )
        for (intervention_class, target_node_id), edge_ids in _collect_edge_groups(graph).items()
    ]


def _collect_edge_groups(graph: AttackGraph) -> dict[_GroupKey, set[str]]:
    groups: defaultdict[_GroupKey, set[str]] = defaultdict(set)
    boundary_ids = {node.id for node in graph.nodes if node.type is NodeType.BOUNDARY}
    for edge in graph.validated_edges():
        for key in _groups_for_edge(edge, boundary_ids):
            groups[key].add(edge.id)
    return dict(groups)


def _groups_for_edge(edge: Edge, boundary_ids: set[str]) -> tuple[_GroupKey, ...]:
    match edge.type:
        case EdgeType.EXPLOITS:
            return ((InterventionClass.VULNERABILITY_PATCH, cast(str, edge.enabled_by)),)
        case EdgeType.REACHES:
            groups = ((InterventionClass.ACCESS_CONTROL_ADD, edge.target),)
            boundary_id = edge.attributes.get(CROSSES_BOUNDARY_ATTRIBUTE)
            if boundary_id in boundary_ids:
                return (*groups, (InterventionClass.NETWORK_SEGMENTATION, boundary_id))
            return groups
        case EdgeType.CAN_ACCESS:
            return ((InterventionClass.IDENTITY_PERMISSION_REDUCTION, edge.source),)
        case EdgeType.READS:
            return ((InterventionClass.CREDENTIAL_REMOVAL, edge.target),)
        case EdgeType.AUTHENTICATES_AS:
            return ((InterventionClass.CREDENTIAL_REMOVAL, edge.source),)
        case EdgeType.ESCAPES:
            return ((InterventionClass.CONTAINER_HARDENING, edge.source),)
        case EdgeType.EXECUTES_AS:
            return ((InterventionClass.EXECUTION_CONTEXT_REBIND, edge.source),)


def _deduplicate(candidates: list[_Candidate]) -> list[_Candidate]:
    unique: dict[tuple[InterventionClass, frozenset[str]], _Candidate] = {}
    for candidate in sorted(candidates, key=_candidate_sort_key):
        key = candidate.intervention_class, candidate.removes_edge_ids
        unique.setdefault(key, candidate)
    return list(unique.values())


def _candidate_sort_key(candidate: _Candidate) -> tuple[str, str, tuple[str, ...]]:
    return (
        candidate.intervention_class.value,
        candidate.target_node_id,
        tuple(sorted(candidate.removes_edge_ids)),
    )
