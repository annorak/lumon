"""Generate a bounded test queue using entry and vulnerability substitution."""

import hashlib
import json
import math
from collections.abc import Iterator
from itertools import pairwise, product
from typing import Literal

from lumon.coverage import CoverageMatrix
from lumon.io import assert_usable
from lumon.model import (
    AttackGraph,
    Edge,
    EdgeType,
    Evidence,
    InterventionCatalog,
    NodeType,
    PathSet,
)
from lumon.model.hypothesis import BypassHypothesis, HypothesisQueue, SubstituteApplicability


def generate_hypotheses(
    graph: AttackGraph,
    paths: PathSet,
    catalog: InterventionCatalog,
    matrix: CoverageMatrix,
    selected_intervention_ids: list[str],
    applicability: list[SubstituteApplicability],
    *,
    max_hypotheses: int,
) -> HypothesisQueue:
    """Return unvalidated candidates, never a claim that all bypasses were found.

    Regenerate from the graph on every call. The matrix fingerprint does not
    include observed or inferred edges. Applicability must be reviewed explicitly
    for each selected change and otherwise viable substitute.

    Rank observed before inferred, then by descending objective weight times
    retained fraction, with stable identifier tie-breakers. Candidate identity
    is the rule, objective ID, and complete candidate edge sequence.
    Supplied path weights must be finite.
    """
    if max_hypotheses < 1:
        raise ValueError("max_hypotheses must be greater than zero")
    assert_usable(graph)
    matrix.verify_fingerprint(paths, catalog)
    _validate_paths_and_removals(graph, paths, catalog)
    interventions = catalog.by_id()
    selected_ids = sorted(set(selected_intervention_ids))
    unknown_ids = sorted(set(selected_ids) - interventions.keys())
    if unknown_ids:
        raise ValueError(f"unknown selected intervention IDs: {', '.join(unknown_ids)}")
    removed_ids = {
        edge_id
        for selected_id in selected_ids
        for edge_id in interventions[selected_id].removes_edge_ids
    }
    effects = _index_applicability(applicability, graph, catalog)
    candidates: dict[str, BypassHypothesis] = {}
    for hypothesis in _enumerate_candidates(graph, paths, removed_ids, selected_ids, effects):
        candidates.setdefault(hypothesis.id, hypothesis)

    ranked = sorted(candidates.values(), key=_ranking_key)
    return HypothesisQueue(
        matrix_fingerprint=matrix.fingerprint,
        selected_intervention_ids=selected_ids,
        hypotheses=ranked[:max_hypotheses],
        max_hypotheses=max_hypotheses,
        truncated=len(ranked) > max_hypotheses,
    )


def _enumerate_candidates(
    graph: AttackGraph,
    paths: PathSet,
    removed_ids: set[str],
    selected_ids: list[str],
    effects: dict[tuple[str, str], SubstituteApplicability],
) -> Iterator[BypassHypothesis]:
    node_types = {node.id: node.type for node in graph.nodes}
    edges = {edge.id: edge for edge in graph.edges}
    known_routes = {tuple(path.edge_ids) for path in paths.paths}

    # The smallest original path ID represents duplicate candidate routes.
    for path in sorted(paths.paths, key=lambda item: item.id):
        removed_positions = [
            index for index, edge_id in enumerate(path.edge_ids) if edge_id in removed_ids
        ]
        for index, substitute in product(removed_positions, graph.edges):
            replaced_id = path.edge_ids[index]
            rule = _match_rule(edges[replaced_id], substitute, index, node_types)
            if rule is None:
                continue
            candidate_ids = tuple(
                substitute.id if edge_id == replaced_id else edge_id for edge_id in path.edge_ids
            )
            candidate_nodes = [
                substitute.source if index == 0 else path.entry_id,
                *path.node_ids[1:],
            ]
            if len(set(candidate_nodes)) != len(candidate_nodes):
                continue
            if substitute.evidence is Evidence.VALIDATED and candidate_ids not in known_routes:
                raise ValueError(
                    f"validated substitute {substitute.id!r} exposes a route absent from "
                    f"the supplied paths: {candidate_ids!r}; review validated-path analysis"
                )
            if substitute.evidence is Evidence.VALIDATED:
                continue
            if not removed_ids.isdisjoint(candidate_ids):
                continue
            records = _get_applicability(substitute.id, selected_ids, effects)
            if any(record.is_blocked for record in records):
                continue
            identity = (rule, path.objective_id, candidate_ids)
            encoded = json.dumps(identity, separators=(",", ":")).encode("utf-8")
            yield BypassHypothesis(
                id=f"HYP-{hashlib.sha256(encoded).hexdigest()}",
                rule=rule,
                original_path=path,
                replaced_edge_id=replaced_id,
                substitute_edge=substitute,
                assumptions=[
                    "Retained transitions are assumed usable after the selected changes.",
                    *[
                        f"{record.intervention_id} is modeled not to block "
                        f"{substitute.id}: {record.justification}"
                        for record in records
                    ],
                    "Actual execution and intervention side effects remain untested.",
                ],
            )


def _match_rule(
    original: Edge, substitute: Edge, index: int, node_types: dict[str, NodeType]
) -> Literal["entry_substitution", "vulnerability_substitution"] | None:
    if original.type is not substitute.type or original.target != substitute.target:
        return None
    if (
        index == 0
        and original.type is EdgeType.REACHES
        and node_types[original.source] is NodeType.ENTRY_POINT
        and node_types[original.target] is NodeType.SERVICE
        and node_types[substitute.source] is NodeType.ENTRY_POINT
        and substitute.source != original.source
    ):
        return "entry_substitution"
    if (
        original.type is EdgeType.EXPLOITS
        and substitute.source == original.source
        and substitute.enabled_by is not None
        and node_types[substitute.enabled_by] is NodeType.VULNERABILITY
        and substitute.enabled_by != original.enabled_by
    ):
        return "vulnerability_substitution"
    return None


def _validate_paths_and_removals(
    graph: AttackGraph, paths: PathSet, catalog: InterventionCatalog
) -> None:
    edges = {edge.id: edge for edge in graph.validated_edges()}
    nodes = {node.id: node for node in graph.nodes}
    referenced_ids = {edge_id for path in paths.paths for edge_id in path.edge_ids} | {
        edge_id
        for intervention in catalog.interventions
        for edge_id in intervention.removes_edge_ids
    }
    invalid_ids = sorted(referenced_ids - edges.keys())
    if invalid_ids:
        raise ValueError(
            "paths or interventions reference non-validated or missing edges: "
            + ", ".join(invalid_ids)
        )
    for path in paths.paths:
        if not math.isfinite(path.weight):
            raise ValueError(f"path {path.id!r} needs a finite weight for bypass ranking")
        transitions = [(edges[edge_id].source, edges[edge_id].target) for edge_id in path.edge_ids]
        if (
            transitions != list(pairwise(path.node_ids))
            or len(set(path.node_ids)) != len(path.node_ids)
            or nodes[path.entry_id].type is not NodeType.ENTRY_POINT
            or nodes[path.objective_id].type is not NodeType.OBJECTIVE
            or path.weight != nodes[path.objective_id].weight
        ):
            raise ValueError(
                f"path {path.id!r} does not match a simple validated entry-to-objective "
                "route and its objective weight in the current graph"
            )


def _index_applicability(
    applicability: list[SubstituteApplicability],
    graph: AttackGraph,
    catalog: InterventionCatalog,
) -> dict[tuple[str, str], SubstituteApplicability]:
    intervention_ids = {intervention.id for intervention in catalog.interventions}
    substitute_ids = {edge.id for edge in graph.edges if edge.evidence is not Evidence.VALIDATED}
    effects: dict[tuple[str, str], SubstituteApplicability] = {}
    for record in applicability:
        key = (record.intervention_id, record.substitute_edge_id)
        if record.intervention_id not in intervention_ids:
            raise ValueError(
                f"applicability references unknown intervention {record.intervention_id!r}"
            )
        if record.substitute_edge_id not in substitute_ids:
            raise ValueError(
                "applicability requires an observed or inferred edge: "
                f"{record.substitute_edge_id!r}"
            )
        if key in effects:
            raise ValueError(f"duplicate applicability record: {key!r}")
        effects[key] = record
    return effects


def _get_applicability(
    substitute_id: str,
    selected_ids: list[str],
    effects: dict[tuple[str, str], SubstituteApplicability],
) -> list[SubstituteApplicability]:
    missing = [
        selected_id for selected_id in selected_ids if (selected_id, substitute_id) not in effects
    ]
    if missing:
        raise ValueError(
            f"review applicability of {', '.join(missing)} to substitute {substitute_id!r}; "
            "missing records do not mean the substitute is unaffected"
        )
    return [effects[(selected_id, substitute_id)] for selected_id in selected_ids]


def _ranking_key(
    hypothesis: BypassHypothesis,
) -> tuple[bool, float, str, str, tuple[str, ...], str, str, str]:
    return (
        hypothesis.substitute_edge.evidence is Evidence.INFERRED,
        -hypothesis.ranking_score,
        hypothesis.original_path.objective_id,
        hypothesis.rule,
        tuple(hypothesis.candidate_edge_ids),
        hypothesis.original_path.id,
        hypothesis.replaced_edge_id,
        hypothesis.substitute_edge.id,
    )
