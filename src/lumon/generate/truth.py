"""The answers the generator knows because it built them.

Everything in this model is **constructed**, never computed. The generator does not run
Lumon's path extraction or Lumon's solver and then write down what they said; it lays out the
graph in a shape whose answers follow from the layout, and records them as it goes.

That distinction is the whole reason this module exists. Task 10 verifies the solvers against
hundreds of generated instances. If the expected answer on each instance came from running
our own code, those tests would be marking their own homework: a bug in path extraction would
corrupt the expectation and the test would still pass. Ground truth has to come from
somewhere the code under test cannot reach.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class GroundTruth(BaseModel):
    """What is true about a generated graph, known before anything analyses it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path_node_sequences: list[list[str]]
    """Every validated entry-to-objective path, as an ordered list of node ids. This is the
    complete set, not a sample: validated edges only ever run between consecutive layers, so
    a path is exactly one choice of node per layer and nothing else can be one."""

    planted_chokepoint_ids: list[str]
    """Nodes the generator narrowed a whole layer down to. Each lies on every path in
    `path_node_sequences`."""

    minimum_chokepoint_cover_size: int
    """The fewest planted chokepoints that together touch every path.

    It is 1 whenever any chokepoint was planted, and 0 otherwise. That is not a shortcut, it
    is what the construction means: a chokepoint is the sole connection between two
    consecutive layers, so every path already runs through every one of them, and any single
    chokepoint on its own therefore covers the lot.
    """

    objective_weights: dict[str, float]
    """The weight drawn for each objective node, by node id."""

    @model_validator(mode="after")
    def _check_cover_fits_the_planted_chokepoints(self) -> Self:
        if not 0 <= self.minimum_chokepoint_cover_size <= len(self.planted_chokepoint_ids):
            raise ValueError(
                f"minimum_chokepoint_cover_size {self.minimum_chokepoint_cover_size} is not "
                f"between 0 and the {len(self.planted_chokepoint_ids)} planted chokepoints"
            )
        return self
