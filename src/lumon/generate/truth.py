"""Expected results derived from graph construction, not path extraction."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class GroundTruth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path_node_sequences: list[list[str]]
    planted_chokepoint_ids: list[str]
    minimum_chokepoint_cover_size: int
    objective_weights: dict[str, float]

    @model_validator(mode="after")
    def _validate_cover_size(self) -> Self:
        if not 0 <= self.minimum_chokepoint_cover_size <= len(self.planted_chokepoint_ids):
            raise ValueError(
                f"minimum_chokepoint_cover_size {self.minimum_chokepoint_cover_size} is not "
                f"between 0 and the {len(self.planted_chokepoint_ids)} planted chokepoints"
            )
        return self
