import statistics
from collections import Counter
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from lumon.model import PathSet


class PathStats(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path_count: int
    distinct_entries: int
    distinct_objectives: int
    min_path_length: int | None
    median_path_length: float | None
    max_path_length: int | None
    total_weight: float
    most_common_edge_id: str | None
    most_common_edge_count: int

    @model_validator(mode="after")
    def _validate_empty_stats(self) -> Self:
        has_paths = self.path_count > 0
        is_defined = all(
            figure is not None
            for figure in (
                self.min_path_length,
                self.median_path_length,
                self.max_path_length,
                self.most_common_edge_id,
            )
        )
        if has_paths != is_defined:
            raise ValueError(
                "path length and most-common-edge figures are defined exactly when the path "
                "set holds at least one path"
            )
        return self


def summarize(path_set: PathSet) -> PathStats:
    lengths = [len(path.edge_ids) for path in path_set.paths]
    appearances = Counter(edge_id for path in path_set.paths for edge_id in path.edge_ids)
    # Break ties by edge ID so repeated runs return the same summary.
    most_common = (
        min(appearances.items(), key=lambda item: (-item[1], item[0])) if appearances else None
    )

    return PathStats(
        path_count=len(path_set.paths),
        distinct_entries=len({path.entry_id for path in path_set.paths}),
        distinct_objectives=len({path.objective_id for path in path_set.paths}),
        min_path_length=min(lengths) if lengths else None,
        median_path_length=statistics.median(lengths) if lengths else None,
        max_path_length=max(lengths) if lengths else None,
        total_weight=path_set.total_weight,
        most_common_edge_id=most_common[0] if most_common else None,
        most_common_edge_count=most_common[1] if most_common else 0,
    )
