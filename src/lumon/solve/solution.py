"""Shared result types for intervention portfolio solvers."""

import math
from collections.abc import Iterable
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator

from lumon.coverage import CoverageMatrix


class OptimalityGuarantee(StrEnum):
    """What a solver can prove about its result."""

    EXACT = "exact"
    UNKNOWN = "unknown"


class InfeasibleError(Exception):
    """Full severance is impossible for one or more validated paths."""

    def __init__(self, uncoverable_path_ids: Iterable[str]) -> None:
        self.uncoverable_path_ids = sorted(uncoverable_path_ids)
        super().__init__(
            "full severance is infeasible; uncoverable validated path ids: "
            f"{', '.join(self.uncoverable_path_ids)}"
        )


class Solution(BaseModel):
    """One solver-selected intervention portfolio and its guarantee."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selected_intervention_ids: list[str]
    total_cost: float
    covered_path_ids: list[str]
    covered_weight: float
    uncovered_path_ids: list[str]
    is_full_cover: bool
    solver_name: str
    guarantee: OptimalityGuarantee
    wall_time_seconds: float
    notes: str | None = None

    @field_validator(
        "selected_intervention_ids",
        "covered_path_ids",
        "uncovered_path_ids",
    )
    @classmethod
    def _validate_sorted_unique_ids(cls, ids: list[str]) -> list[str]:
        if ids != sorted(set(ids)):
            raise ValueError("solution id lists must be sorted and contain no duplicates")
        return ids

    @classmethod
    def from_matrix(
        cls,
        matrix: CoverageMatrix,
        selected_intervention_ids: Iterable[str],
        *,
        solver_name: str,
        guarantee: OptimalityGuarantee,
        wall_time_seconds: float,
        notes: str | None = None,
    ) -> Self:
        """Build a result whose derived values all come from one matrix."""
        selected_ids = sorted(selected_intervention_ids)
        costs_by_id = {
            intervention_id: float(matrix.intervention_costs[index])
            for index, intervention_id in enumerate(matrix.intervention_ids)
        }
        # overlapping fixes still count each path once
        covered_path_id_set = {
            path_id
            for intervention_id in selected_ids
            for path_id in matrix.paths_covered_by(intervention_id)
        }
        covered_path_ids = sorted(covered_path_id_set)
        uncovered_path_ids = sorted(set(matrix.path_ids) - covered_path_id_set)
        fingerprint_note = f"matrix_fingerprint={matrix.fingerprint}"
        solution_notes = fingerprint_note if notes is None else f"{notes}; {fingerprint_note}"

        return cls(
            selected_intervention_ids=selected_ids,
            total_cost=math.fsum(costs_by_id[item] for item in selected_ids),
            covered_path_ids=covered_path_ids,
            covered_weight=matrix.weight_covered_by(selected_ids),
            uncovered_path_ids=uncovered_path_ids,
            is_full_cover=not uncovered_path_ids,
            solver_name=solver_name,
            guarantee=guarantee,
            wall_time_seconds=wall_time_seconds,
            notes=solution_notes,
        )
