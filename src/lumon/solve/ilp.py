"""CP-SAT solvers for severing weighted validated attack paths.

Minimum-cost full cover is weighted set cover; budgeted severance is budgeted
maximum coverage. Both are NP-hard. Exact solves are expected to be practical
for tens of validated paths and around 100 interventions, not guaranteed to
finish for every instance. Every solve has a finite time limit.

Coefficients use decimal thousandths, scaled by 1000. Finer precision is rejected
instead of rounded. The current cost tiers 1, 3, and 9 convert exactly. Results
retain the original matrix values, and reported cost must not exceed the budget.
"""

import math
from fractions import Fraction
from time import perf_counter

import numpy as np
from numpy.typing import NDArray
from ortools.sat.python import cp_model

from lumon.coverage import CoverageMatrix
from lumon.solve.solution import InfeasibleError, OptimalityGuarantee, Solution

DEFAULT_TIME_LIMIT_SECONDS = 30.0
_INTEGER_SCALE = 1000
_RANDOM_SEED = 0
# Leave room for CP-SAT's intermediate bound calculations.
_MAX_SCALED_TOTAL = cp_model.INT_MAX // 2


class SolverError(Exception):
    """CP-SAT could not return a usable intervention portfolio."""


def solve_min_cost_cover(
    matrix: CoverageMatrix,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
) -> Solution:
    """Find the cheapest portfolio severing every validated path.

    Callers must verify the matrix fingerprint against its original inputs before
    solving when those inputs may have changed. Costs must use decimal thousandths.
    EXACT means CP-SAT proved optimality; a feasible unproven result is UNKNOWN.
    Completed searches are deterministic; wall-clock cutoffs need not be.
    """
    uncoverable_path_ids = matrix.uncoverable_path_ids()
    if uncoverable_path_ids:
        raise InfeasibleError(uncoverable_path_ids)

    costs = _scale_coefficients(matrix.intervention_ids, matrix.intervention_costs, "cost")
    model = cp_model.CpModel()
    selected = {
        intervention_id: model.new_bool_var(intervention_id)
        for intervention_id in matrix.intervention_ids
    }
    for path_id in matrix.path_ids:
        model.add(sum(selected[item] for item in matrix.interventions_covering(path_id)) >= 1)
    model.minimize(sum(costs[item] * variable for item, variable in selected.items()))

    return _solve(matrix, model, selected, time_limit_seconds)


def solve_budgeted_max_coverage(
    matrix: CoverageMatrix,
    budget: float,
    time_limit_seconds: float = DEFAULT_TIME_LIMIT_SECONDS,
) -> Solution:
    """Maximize severed validated path weight without exceeding the supplied budget.

    Callers must verify the matrix fingerprint against its original inputs before
    solving when those inputs may have changed. Costs and weights must use decimal
    thousandths. Budgets may have finer precision and are never rounded upward.
    EXACT means CP-SAT proved optimality; a feasible unproven result is UNKNOWN.
    Completed searches are deterministic; wall-clock cutoffs need not be.
    """
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("budget must be finite and greater than or equal to 0")

    costs = _scale_coefficients(matrix.intervention_ids, matrix.intervention_costs, "cost")
    weights = _scale_coefficients(matrix.path_ids, matrix.path_weights, "weight")
    # Costs are integer thousandths. Flooring this ceiling preserves affordability;
    # a budget above the entire catalog cost adds no further feasible selections.
    scaled_budget = min(math.floor(Fraction(str(budget)) * _INTEGER_SCALE), sum(costs.values()))
    model = cp_model.CpModel()
    selected = {
        intervention_id: model.new_bool_var(intervention_id)
        for intervention_id in matrix.intervention_ids
    }
    covered = {path_id: model.new_bool_var(f"covered:{path_id}") for path_id in matrix.path_ids}
    model.add(sum(costs[item] * variable for item, variable in selected.items()) <= scaled_budget)
    for path_id, variable in covered.items():
        model.add(
            variable <= sum(selected[item] for item in matrix.interventions_covering(path_id))
        )
    model.maximize(sum(weights[path_id] * variable for path_id, variable in covered.items()))
    if not matrix.path_ids:
        model.add(sum(selected.values()) == 0)

    solution = _solve(matrix, model, selected, time_limit_seconds)
    if solution.total_cost > budget:
        raise SolverError(
            "the selected portfolio exceeds the supplied budget when evaluated with "
            "the original matrix costs; decimal scaling cannot preserve this budget boundary"
        )
    return solution


def _scale_coefficients(
    ids: list[str],
    values: NDArray[np.float64],
    kind: str,
) -> dict[str, int]:
    scaled_values: dict[str, int] = {}
    for item_id, value in zip(ids, values, strict=True):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{kind} for {item_id!r} must be finite and greater than 0")
        # Interpret decimal text exactly, independent of binary multiplication
        # and the caller's decimal arithmetic context.
        scaled = Fraction(str(float(value))) * _INTEGER_SCALE
        if scaled.denominator != 1:
            raise ValueError(
                f"{kind} for {item_id!r} is {value}; supported precision is 0.001; "
                "values are not rounded"
            )
        scaled_values[item_id] = scaled.numerator

    if sum(scaled_values.values()) > _MAX_SCALED_TOTAL:
        raise ValueError(f"scaled {kind} total exceeds CP-SAT's safe integer range")
    return scaled_values


def _solve(
    matrix: CoverageMatrix,
    model: cp_model.CpModel,
    selected: dict[str, cp_model.IntVar],
    time_limit_seconds: float,
) -> Solution:
    if not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("time limit must be finite and greater than 0")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = _RANDOM_SEED
    started_at = perf_counter()
    status = solver.solve(model)
    wall_time_seconds = perf_counter() - started_at
    notes = None
    match status:
        case cp_model.OPTIMAL:
            guarantee = OptimalityGuarantee.EXACT
        case cp_model.FEASIBLE:
            guarantee = OptimalityGuarantee.UNKNOWN
            notes = (
                f"time limit of {time_limit_seconds:g} seconds ended without an optimality proof; "
                "the selected portfolio is feasible but is not proven best"
            )
        case cp_model.INFEASIBLE:
            raise SolverError(
                "CP-SAT reported infeasibility despite the model's feasibility checks"
            )
        case cp_model.MODEL_INVALID:
            raise SolverError(f"CP-SAT model is invalid: {model.validate()}")
        case cp_model.UNKNOWN:
            raise SolverError(
                f"no solution was found within the time limit of {time_limit_seconds:g}s"
            )
        case _:
            raise SolverError(f"unexpected CP-SAT status: {status}")

    return Solution.from_matrix(
        matrix,
        [item_id for item_id, variable in selected.items() if solver.boolean_value(variable)],
        solver_name="cp_sat",
        guarantee=guarantee,
        wall_time_seconds=wall_time_seconds,
        notes=notes,
    )
