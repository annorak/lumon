"""A one-glance description of a path set, for sanity checks before anything expensive runs.

Nothing downstream depends on these numbers. They exist so that a person handed a path set can
tell in a second whether it looks like the environment they were expecting — 40 paths across 2
objectives is an engagement, 40 paths across 1 entry point is probably a graph missing half its
edges.
"""

import statistics
from collections import Counter
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from lumon.model import PathSet


class PathStats(BaseModel):
    """What one path set looks like at a glance.

    The four nullable fields are `None` exactly when the set has no paths in it, which is a
    legitimate result: a graph where no validated route reaches any objective has no shortest
    path, and reporting a length of 0 would be a false statement rather than a tidy default.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path_count: int
    distinct_entries: int
    distinct_objectives: int
    # Lengths are hop counts, matching `extract_paths`'s `max_depth`.
    min_path_length: int | None
    median_path_length: float | None
    max_path_length: int | None
    total_weight: float
    most_common_edge_id: str | None
    most_common_edge_count: int

    @model_validator(mode="after")
    def _check_undefined_figures_match_an_empty_set(self) -> Self:
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
    """Describe a path set without changing it.

    `most_common_edge_id` is a preview of the chokepoint structure the solver later finds
    properly: an edge sitting on many paths is an edge that one intervention could sever many
    paths by removing. It is a sanity check, not a recommendation — nothing may be ranked or
    chosen from it. Ties break on the lowest edge id so the answer is stable across runs.
    """
    lengths = [len(path.edge_ids) for path in path_set.paths]
    appearances = Counter(edge_id for path in path_set.paths for edge_id in path.edge_ids)
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
