"""Slow exact solvers used as an independent answer key."""

import math
from itertools import combinations
from time import perf_counter

from lumon.coverage import CoverageMatrix
from lumon.solve import InfeasibleError, OptimalityGuarantee, Solution

BRUTE_FORCE_MAX_INTERVENTIONS = 20


class InstanceTooLargeError(Exception):
    """The instance exceeds the brute-force solver's hard cap."""


def brute_force_min_cost_cover(matrix: CoverageMatrix) -> Solution:
    """Return the cheapest full cover.

    Callers must verify the matrix fingerprint against its original inputs before
    calling when those inputs may have changed.
    """
    started_at = perf_counter()
    _check_size(matrix)

    uncoverable_path_ids = matrix.uncoverable_path_ids()
    if uncoverable_path_ids:
        raise InfeasibleError(uncoverable_path_ids)

    intervention_ids = tuple(sorted(matrix.intervention_ids))
    costs = _costs_by_id(matrix)
    best_ids = intervention_ids
    best_key = (_total_cost(best_ids, costs), len(best_ids), best_ids)

    # a bigger set can still be cheaper
    for subset_size in range(len(intervention_ids) + 1):
        for selected_ids in combinations(intervention_ids, subset_size):
            if not matrix.is_full_cover(selected_ids):
                continue

            key = (_total_cost(selected_ids, costs), subset_size, selected_ids)
            if key < best_key:
                best_ids = selected_ids
                best_key = key

    return Solution.from_matrix(
        matrix,
        best_ids,
        solver_name="brute_force",
        guarantee=OptimalityGuarantee.EXACT,
        wall_time_seconds=perf_counter() - started_at,
    )


def brute_force_budgeted_max_coverage(
    matrix: CoverageMatrix,
    budget: float,
) -> Solution:
    """Return the maximum-weight cover within a budget.

    Callers must verify the matrix fingerprint against its original inputs before
    calling when those inputs may have changed.
    """
    started_at = perf_counter()
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("budget must be finite and greater than or equal to 0")
    _check_size(matrix)

    intervention_ids = tuple(sorted(matrix.intervention_ids))
    costs = _costs_by_id(matrix)
    best_ids: tuple[str, ...] = ()
    best_key = (0.0, 0.0, 0, best_ids)

    for subset_size in range(len(intervention_ids) + 1):
        for selected_ids in combinations(intervention_ids, subset_size):
            total_cost = _total_cost(selected_ids, costs)
            if total_cost > budget:
                continue

            key = (
                -matrix.weight_covered_by(selected_ids),
                total_cost,
                subset_size,
                selected_ids,
            )
            if key < best_key:
                best_ids = selected_ids
                best_key = key

    return Solution.from_matrix(
        matrix,
        best_ids,
        solver_name="brute_force",
        guarantee=OptimalityGuarantee.EXACT,
        wall_time_seconds=perf_counter() - started_at,
    )


def _check_size(matrix: CoverageMatrix) -> None:
    intervention_count = len(matrix.intervention_ids)
    if intervention_count > BRUTE_FORCE_MAX_INTERVENTIONS:
        raise InstanceTooLargeError(
            "brute force supports at most "
            f"{BRUTE_FORCE_MAX_INTERVENTIONS} interventions; received {intervention_count}"
        )


def _costs_by_id(matrix: CoverageMatrix) -> dict[str, float]:
    return {
        intervention_id: float(matrix.intervention_costs[index])
        for index, intervention_id in enumerate(matrix.intervention_ids)
    }


def _total_cost(
    selected_ids: tuple[str, ...],
    costs: dict[str, float],
) -> float:
    return math.fsum(costs[intervention_id] for intervention_id in selected_ids)
