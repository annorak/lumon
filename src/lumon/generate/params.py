from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GeneratorParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seed: int = Field(description="Seed for deterministic random choices")
    n_entry_points: int = Field(default=2, ge=1)
    n_objectives: int = Field(default=2, ge=1)
    depth: int = Field(
        default=3,
        ge=1,
        description="Number of intermediate layers. Every path has depth + 1 edges",
    )
    branching: int = Field(
        default=2,
        ge=1,
        description="Number of nodes in each intermediate layer without a chokepoint",
    )
    n_planted_chokepoints: int = Field(
        default=1,
        ge=0,
        description="Number of intermediate layers narrowed to one node",
    )
    observed_edge_ratio: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Observed decoy edges as a fraction of validated edges",
    )
    inferred_edge_ratio: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Inferred decoy edges as a fraction of validated edges",
    )
    objective_weight_range: tuple[int, int] = Field(
        default=(1, 10), description="Inclusive range for objective weights"
    )

    @model_validator(mode="after")
    def _validate_chokepoint_count(self) -> Self:
        if self.n_planted_chokepoints > self.depth:
            raise ValueError(
                f"n_planted_chokepoints ({self.n_planted_chokepoints}) exceeds depth "
                f"({self.depth}); each chokepoint narrows one intermediate layer"
            )
        return self

    @model_validator(mode="after")
    def _validate_weight_range(self) -> Self:
        low, high = self.objective_weight_range
        if low < 1:
            raise ValueError(f"objective_weight_range starts at {low}; weights must exceed 0")
        if high < low:
            raise ValueError(f"objective_weight_range {self.objective_weight_range} is backwards")
        return self
