"""Unvalidated routes to test after applying a selected portfolio."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lumon.model.enums import Evidence
from lumon.model.graph import Edge, EntityId
from lumon.model.path import Path


class SubstituteApplicability(BaseModel):
    """A reviewed assumption about one change's effect on a substitute edge."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intervention_id: EntityId
    substitute_edge_id: EntityId
    is_blocked: bool
    justification: str = Field(min_length=1)

    @field_validator("justification")
    @classmethod
    def _validate_justification(cls, justification: str) -> str:
        if not justification.strip():
            raise ValueError("justification must contain non-whitespace text")
        return justification


class BypassHypothesis(BaseModel):
    """One edge substitution, not a confirmed entry-to-objective route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    rule: Literal["entry_substitution", "vulnerability_substitution"]
    original_path: Path
    replaced_edge_id: EntityId
    substitute_edge: Edge
    assumptions: list[str] = Field(min_length=1)

    @field_validator("assumptions")
    @classmethod
    def _validate_assumptions(cls, assumptions: list[str]) -> list[str]:
        if any(not assumption.strip() for assumption in assumptions):
            raise ValueError("each assumption must contain non-whitespace text")
        return assumptions

    @model_validator(mode="after")
    def _validate_substitution(self) -> Self:
        if self.substitute_edge.evidence is Evidence.VALIDATED:
            raise ValueError("a validated substitute belongs in validated-path analysis")
        if self.original_path.edge_ids.count(self.replaced_edge_id) != 1:
            raise ValueError("replaced_edge_id must occur exactly once in the original path")
        return self

    @property
    def candidate_edge_ids(self) -> list[str]:
        return [
            self.substitute_edge.id if edge_id == self.replaced_edge_id else edge_id
            for edge_id in self.original_path.edge_ids
        ]

    @property
    def retained_fraction(self) -> float:
        return (len(self.original_path.edge_ids) - 1) / len(self.original_path.edge_ids)

    @property
    def ranking_score(self) -> float:
        return self.original_path.weight * self.retained_fraction


class HypothesisQueue(BaseModel):
    """Bounded candidates for one input matrix and explicit portfolio.

    An empty queue does not establish that no bypasses exist.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    matrix_fingerprint: str = Field(min_length=1)
    selected_intervention_ids: list[EntityId]
    hypotheses: list[BypassHypothesis]
    max_hypotheses: int = Field(gt=0)
    truncated: bool


def hypothesis_statement(hypothesis: BypassHypothesis) -> str:
    """Use this wording in every renderer, including for observed substitutes."""
    return (
        f"Hypothesis {hypothesis.id}: replace {hypothesis.replaced_edge_id} on "
        f"path {hypothesis.original_path.id} with {hypothesis.substitute_edge.id} "
        f"({hypothesis.substitute_edge.evidence.value}) to test a candidate route to "
        f"{hypothesis.original_path.objective_id}. This route is unvalidated. "
        "Recommend validation; actual execution and intervention side effects remain untested."
    )
