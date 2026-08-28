"""Models for validated attack paths."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lumon.model.graph import EntityId, reject_duplicate_ids


class Path(BaseModel):
    """One entry-to-objective route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    edge_ids: list[str] = Field(min_length=1)
    node_ids: list[str]
    entry_id: str
    objective_id: str
    weight: float = Field(gt=0)

    @model_validator(mode="after")
    def _validate_sequences(self) -> Self:
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
    """Paths extracted from one graph and whether `max_paths` stopped enumeration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: list[Path]
    truncated: bool
    truncation_reason: str | None = None
    graph_id: str | None = None

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> Self:
        reject_duplicate_ids([path.id for path in self.paths], "path")
        return self

    @model_validator(mode="after")
    def _validate_truncation_reason(self) -> Self:
        if self.truncated and not self.truncation_reason:
            raise ValueError(
                "a truncated path set must carry a truncation_reason naming the cap it hit, "
                "or a reader cannot tell how much of the graph went unexamined"
            )
        return self

    @property
    def total_weight(self) -> float:
        """Sum path weights, including repeated objectives."""
        return sum(path.weight for path in self.paths)

    def by_objective(self) -> dict[str, list[Path]]:
        grouped: dict[str, list[Path]] = {}
        for path in self.paths:
            grouped.setdefault(path.objective_id, []).append(path)
        return grouped

    def weights_by_id(self) -> dict[str, float]:
        return {path.id: path.weight for path in self.paths}
