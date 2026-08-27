"""Turning an attack graph into the set of validated paths the optimizer reasons about.

Two rules govern this module, and both are load-bearing for the project rather than
implementation detail.

**Only validated edges are ever traversed.** Enumeration runs over
`to_networkx(graph, validated_only=True)`, so an `OBSERVED` or `INFERRED` edge cannot put a
path into the result no matter how plausible the route it names. Those edges are held back
whole for task 13, which turns them into bypass hypotheses — routes to go and test, never
routes we claim exist. If an unvalidated edge could reach the solver, every severance claim
Lumon makes would rest on something nobody proved.

**Truncation is loud.** The enumeration is capped, and when a cap stops it early the returned
`PathSet` says so and says which cap and where. Quietly returning 5,000 of 8,000 paths would
produce a report reading "these fixes sever everything" while 3,000 paths sat unexamined.

The path count is also why an NP-hard optimization is fine downstream: real engagements report
validated paths in the tens, because validating one is expensive and only proven routes get
reported.
"""

import itertools
from collections.abc import Iterator
from typing import NamedTuple, cast

import networkx as nx

from lumon.io import to_networkx
from lumon.model import AttackGraph, Path, PathSet


class _Candidate(NamedTuple):
    """One enumerated path, before the set is sorted and ids are handed out."""

    entry_id: str
    objective_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    weight: float


def extract_paths(graph: AttackGraph, max_paths: int = 5000, max_depth: int = 12) -> PathSet:
    """Every simple path from an entry point to an objective, over validated edges alone.

    "Simple" means no node repeats, so a cycle in the graph cannot produce an infinite family
    of paths or hang the search. `max_depth` is a hop count: a path may cross at most that many
    edges, and therefore visit at most `max_depth + 1` nodes. A route longer than that is not
    reported and does not set `truncated` — the depth bound is a declared search parameter,
    not an early stop, and proving that no longer route exists is not something this function
    can do cheaply. `max_paths` is the early stop, and it does set `truncated`.

    The result is scoped to *validated reachability*. It is not the set of all paths through
    the environment, and nothing built on top of it may say that it is.
    """
    view = to_networkx(graph, validated_only=True)
    # One past the cap, so a graph holding exactly `max_paths` paths is reported complete
    # rather than being flagged for a truncation that never happened.
    found = list(itertools.islice(_enumerate(graph, view, max_depth), max_paths + 1))
    is_truncated = len(found) > max_paths
    kept = sorted(found[:max_paths], key=_ordering)

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
            for index, candidate in enumerate(kept)
        ],
        truncated=is_truncated,
        truncation_reason=_describe_truncation(found[-1], max_paths) if is_truncated else None,
        graph_id=graph.metadata.get("graph_id"),
    )


def _enumerate(graph: AttackGraph, view: nx.MultiDiGraph, max_depth: int) -> Iterator[_Candidate]:
    """Every validated entry-to-objective path, yielded one at a time so a caller can stop.

    The search is over *edge* sequences rather than node sequences, because a node sequence is
    not a path on its own: two nodes can be joined by more than one validated edge, and an
    identity that both `reaches` and `can_access` a cloud account is two different attacker
    techniques. An intervention may sever one and leave the other standing, so collapsing them
    would hide a route the solver has to account for.

    Entries and objectives are walked in id order, so what this yields depends on the graph and
    nothing else.
    """
    for entry in sorted(graph.entry_points(), key=lambda node: node.id):
        for objective in sorted(graph.objectives(), key=lambda node: node.id):
            # `Node` requires a weight on every objective. The cast states that for mypy; it
            # is not a fallback for one that is missing.
            weight = cast(float, objective.weight)
            walks = nx.all_simple_edge_paths(view, entry.id, objective.id, cutoff=max_depth)
            for walk in walks:
                yield _Candidate(
                    entry_id=entry.id,
                    objective_id=objective.id,
                    node_ids=(entry.id, *(target for _, target, _ in walk)),
                    edge_ids=tuple(edge_id for _, _, edge_id in walk),
                    weight=weight,
                )


def _ordering(candidate: _Candidate) -> tuple[str, str, int, tuple[str, ...]]:
    """The sort that makes two runs over one graph produce byte-identical output, so a path
    set can be diffed against an earlier one and the difference means something."""
    return (candidate.entry_id, candidate.objective_id, len(candidate.edge_ids), candidate.edge_ids)


def _describe_truncation(overflow: _Candidate, max_paths: int) -> str:
    """Why enumeration stopped, naming the cap and where it bit, so a reader can raise the cap
    and re-run rather than guessing at how much was left behind."""
    return (
        f"stopped at the max_paths cap of {max_paths} while enumerating "
        f"{overflow.entry_id!r} -> {overflow.objective_id!r}; this graph holds more validated "
        "paths than this set contains, so nothing computed from it covers all of them"
    )
