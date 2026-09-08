"""Summarize which validated paths the intervention catalog can sever."""

from pydantic import BaseModel, ConfigDict

from lumon.coverage.matrix import CoverageMatrix


class CoverageReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    intervention_count: int
    path_count: int
    density: float
    uncoverable_path_ids: list[str]
    uncoverable_total_weight: float
    redundant_intervention_ids: list[str]
    dominated_intervention_ids: list[str]
    full_severance_feasible: bool


def summarize(matrix: CoverageMatrix) -> CoverageReport:
    dense = matrix.to_dense()
    uncoverable_path_ids = matrix.uncoverable_path_ids()
    uncoverable_path_id_set = set(uncoverable_path_ids)
    uncoverable_total_weight = float(
        sum(
            float(weight)
            for index, weight in enumerate(matrix.path_weights)
            if matrix.path_ids[index] in uncoverable_path_id_set
        )
    )
    density = float(dense.sum()) / dense.size if dense.size else 0.0

    return CoverageReport(
        intervention_count=len(matrix.intervention_ids),
        path_count=len(matrix.path_ids),
        density=density,
        uncoverable_path_ids=uncoverable_path_ids,
        uncoverable_total_weight=uncoverable_total_weight,
        redundant_intervention_ids=matrix.redundant_intervention_ids(),
        dominated_intervention_ids=matrix.dominated_intervention_ids(),
        full_severance_feasible=not uncoverable_path_ids,
    )
