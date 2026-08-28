"""Extract simple validated paths from an attack graph."""

import itertools
from collections.abc import Iterator
from typing import NamedTuple, cast

import networkx as nx

from lumon.io import to_networkx
from lumon.model import AttackGraph, Path, PathSet


class _PathCandidate(NamedTuple):
    entry_id: str
    objective_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    weight: float


def extract_paths(graph: AttackGraph, max_paths: int = 5000, max_depth: int = 12) -> PathSet:
    """Extract validated paths within the given count and depth limits.

    Hitting `max_paths` marks the result as truncated. `max_depth` is a search bound and does
    not mark the result as truncated.
    """
    validated_graph = to_networkx(graph, validated_only=True)
    # Read one extra path so exactly max_paths results are not marked as truncated.
    candidates = list(
        itertools.islice(_enumerate_paths(graph, validated_graph, max_depth), max_paths + 1)
    )
    is_truncated = len(candidates) > max_paths
    selected_candidates = sorted(candidates[:max_paths], key=_path_sort_key)

    return PathSet(
        paths=[
            Path(
                id=f"p{index:04d}",
                edge_ids=list(candidate.edge_ids),
                node_ids=list(candidate.node_ids),
                entry_id=candidate.entry_id,
                objective_id=candidate.objective_id,
                weight=candidate.weight,
            )
            for index, candidate in enumerate(selected_candidates)
        ],
        truncated=is_truncated,
        truncation_reason=_truncation_reason(candidates[-1], max_paths) if is_truncated else None,
        graph_id=graph.metadata.get("graph_id"),
    )


def _enumerate_paths(
    graph: AttackGraph, validated_graph: nx.MultiDiGraph, max_depth: int
) -> Iterator[_PathCandidate]:
    for entry in sorted(graph.entry_points(), key=lambda node: node.id):
        for objective in sorted(graph.objectives(), key=lambda node: node.id):
            # Objective validation guarantees that weight is set.
            weight = cast(float, objective.weight)
            walks = nx.all_simple_edge_paths(
                validated_graph, entry.id, objective.id, cutoff=max_depth
            )
            for walk in walks:
                yield _PathCandidate(
                    entry_id=entry.id,
                    objective_id=objective.id,
                    node_ids=(entry.id, *(target for _, target, _ in walk)),
                    edge_ids=tuple(edge_id for _, _, edge_id in walk),
                    weight=weight,
                )


def _path_sort_key(candidate: _PathCandidate) -> tuple[str, str, int, tuple[str, ...]]:
    return (candidate.entry_id, candidate.objective_id, len(candidate.edge_ids), candidate.edge_ids)


def _truncation_reason(overflow: _PathCandidate, max_paths: int) -> str:
    return (
        f"stopped at the max_paths cap of {max_paths} while enumerating "
        f"{overflow.entry_id!r} -> {overflow.objective_id!r}; this graph holds more validated "
        "paths than this set contains, so nothing computed from it covers all of them"
    )
