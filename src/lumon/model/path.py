"""A route an attacker proved, and the set of routes the optimizer reasons about.

A `Path` is the unit everything downstream counts. The coverage matrix gets one column per
path, the frontier reports the fraction of weighted paths a portfolio severs, and the bypass
queue is phrased relative to the paths a fix removes. A path therefore stores **both** its
node sequence and its edge sequence: interventions remove edges, while a human reading the
report follows nodes.

Only validated edges ever appear in here. `lumon.paths.extract` is the one thing that builds
these, and it builds them from the validated-only view of the graph. Because validation is a
sample of reachability rather than a census, a complete `PathSet` still describes *validated
reachability* and never "every path that exists."

Note that `Path` shadows `pathlib.Path`. Import it as `from lumon.model import Path` in
modules that do not touch the filesystem, and alias one of the two where they meet.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lumon.model.graph import EntityId, reject_duplicate_ids


class Path(BaseModel):
    """One entry-to-objective route over validated edges alone.

    `node_ids` and `edge_ids` are two descriptions of the same walk and are kept in step by
    the validator below, so a consumer may use whichever one suits it without re-deriving the
    other from the graph.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    edge_ids: list[str] = Field(min_length=1)
    node_ids: list[str]
    entry_id: str
    objective_id: str
    # The weight of the objective this path reaches: what the business loses if it falls.
    weight: float = Field(gt=0)

    @model_validator(mode="after")
    def _check_the_two_sequences_describe_one_walk(self) -> Self:
        if len(self.node_ids) != len(self.edge_ids) + 1:
            raise ValueError(
                f"path {self.id!r} has {len(self.edge_ids)} edges, so it needs "
                f"{len(self.edge_ids) + 1} nodes, not {len(self.node_ids)}"
            )
        if self.node_ids[0] != self.entry_id:
            raise ValueError(
                f"path {self.id!r} starts at {self.node_ids[0]!r}, not at its entry "
                f"{self.entry_id!r}"
            )
        if self.node_ids[-1] != self.objective_id:
            raise ValueError(
                f"path {self.id!r} ends at {self.node_ids[-1]!r}, not at its objective "
                f"{self.objective_id!r}"
            )
        return self


class PathSet(BaseModel):
    """Every validated path found in one graph — and whether that "every" is honest.

    `truncated` has no default on purpose. Building a `PathSet` forces you to say whether the
    enumeration finished, because the one thing this type must never do is hand back a partial
    result that looks complete. A report claiming "these fixes sever everything" over 5,000 of
    8,000 paths is worse than no report at all.

    `graph_id` copies the graph's `metadata["graph_id"]`, so pairing a path set with the wrong
    graph later on is detectable rather than silent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: list[Path]
    truncated: bool
    truncation_reason: str | None = None
    graph_id: str | None = None

    @model_validator(mode="after")
    def _check_ids_unique(self) -> Self:
        reject_duplicate_ids([path.id for path in self.paths], "path")
        return self

    @model_validator(mode="after")
    def _check_truncation_is_explained(self) -> Self:
        if self.truncated and not self.truncation_reason:
            raise ValueError(
                "a truncated path set must carry a truncation_reason naming the cap it hit, "
                "or a reader cannot tell how much of the graph went unexamined"
            )
        return self

    @property
    def total_weight(self) -> float:
        """The weight of every path added up. The denominator for "severed 81% of weighted
        validated paths" — note that a path is counted once per route, so a heavy objective
        reachable by many routes weighs more than one reachable by a single route."""
        return sum(path.weight for path in self.paths)

    def by_objective(self) -> dict[str, list[Path]]:
        """The paths grouped by the objective they reach. Objectives no validated path reaches
        do not appear at all."""
        grouped: dict[str, list[Path]] = {}
        for path in self.paths:
            grouped.setdefault(path.objective_id, []).append(path)
        return grouped

    def weights_by_id(self) -> dict[str, float]:
        """Path weights keyed by path id, which is the shape the solver's objective wants."""
        return {path.id: path.weight for path in self.paths}
