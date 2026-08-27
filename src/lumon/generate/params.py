"""What shape of synthetic attack graph to build.

Every field here is a knob on *structure*, because structure is the only thing the ground
truth is derived from. Nothing here is a knob on realism: these graphs exist to be varied,
valid, and to have known answers, not to look like a real network.

The shape is always a layered DAG — one layer of entry points, then `depth` intermediate
layers, then one layer of objectives — and a validated edge only ever runs from one layer to
the next. That single restriction is what makes the path set a closed-form product over the
layer widths instead of something you would have to go looking for in the graph.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GeneratorParams(BaseModel):
    """The size and shape of one synthetic attack graph.

    A planted chokepoint is an intermediate layer narrowed to a single node. Since validated
    edges only run between consecutive layers, every path has to pass through that node,
    which is what makes it a chokepoint by construction rather than by discovery.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: int
    """Drives every random choice the generator makes. Same seed, same graph, forever."""

    n_entry_points: int = Field(default=2, ge=1)
    n_objectives: int = Field(default=2, ge=1)
    depth: int = Field(default=3, ge=1)
    """Intermediate hops on every path. Path length in edges is always `depth + 1`."""

    branching: int = Field(default=2, ge=1)
    """Width of an intermediate layer that is not a chokepoint: the alternate routes."""

    n_planted_chokepoints: int = Field(default=1, ge=0)
    """How many intermediate layers are narrowed to one node. Zero is allowed and useful:
    it produces a graph with no forced chokepoint, which is a shape later stages need."""

    observed_edge_ratio: float = Field(default=0.2, ge=0.0, le=1.0)
    """Decoy `OBSERVED` edges to add, as a fraction of the validated edge count."""

    inferred_edge_ratio: float = Field(default=0.1, ge=0.0, le=1.0)
    """Decoy `INFERRED` edges to add, as a fraction of the validated edge count."""

    objective_weight_range: tuple[int, int] = (1, 10)
    """Inclusive range each objective's weight is drawn from."""

    @model_validator(mode="after")
    def _check_chokepoints_fit_within_depth(self) -> Self:
        """Each chokepoint consumes one intermediate layer, so there cannot be more of them
        than there are layers to narrow."""
        if self.n_planted_chokepoints > self.depth:
            raise ValueError(
                f"n_planted_chokepoints ({self.n_planted_chokepoints}) exceeds depth "
                f"({self.depth}); each chokepoint narrows one intermediate layer"
            )
        return self

    @model_validator(mode="after")
    def _check_weight_range_is_ordered_and_positive(self) -> Self:
        low, high = self.objective_weight_range
        if low < 1:
            raise ValueError(f"objective_weight_range starts at {low}; weights must exceed 0")
        if high < low:
            raise ValueError(f"objective_weight_range {self.objective_weight_range} is backwards")
        return self
