import math
from decimal import localcontext
from random import Random
from unittest.mock import patch

import pytest
from ortools.sat.python import cp_model

from lumon.coverage import CoverageMatrix
from lumon.generate import REALISTIC, generate
from lumon.interventions import synthesize
from lumon.model import CostTier, PathSet
from lumon.solve import (
    InfeasibleError,
    OptimalityGuarantee,
    Solution,
    SolverError,
    solve_budgeted_max_coverage,
    solve_min_cost_cover,
)
from lumon.solve.ilp import DEFAULT_TIME_LIMIT_SECONDS
from tests.brute_force import brute_force_budgeted_max_coverage, brute_force_min_cost_cover
from tests.unit.test_brute_force import InterventionSpec, _matrix


def _small_matrix(seed: int) -> CoverageMatrix:
    random = Random(seed)
    weights = {f"p{index}": float(random.randint(1, 10)) for index in range(2 + seed % 4)}
    interventions: list[InterventionSpec] = [
        (
            f"i{index}",
            {path_id for path_id in weights if random.choice([False, True])}
            or {random.choice(list(weights))},
            random.choice(list(CostTier)),
        )
        for index in range(3 + seed % 5)
    ]
    interventions.append(("full-cover", set(weights), CostTier.HIGH))
    return _matrix(weights, interventions)


def _assert_matches_matrix(matrix: CoverageMatrix, solution: Solution) -> None:
    selected_ids = solution.selected_intervention_ids
    covered_ids = sorted(
        {
            path_id
            for intervention_id in selected_ids
            for path_id in matrix.paths_covered_by(intervention_id)
        }
    )
    assert selected_ids == sorted(set(selected_ids))
    assert solution.total_cost == math.fsum(
        float(matrix.intervention_costs[index])
        for index, intervention_id in enumerate(matrix.intervention_ids)
        if intervention_id in selected_ids
    )
    assert solution.covered_path_ids == covered_ids
    assert solution.covered_weight == matrix.weight_covered_by(selected_ids)
    assert solution.uncovered_path_ids == sorted(set(matrix.path_ids) - set(covered_ids))
    assert solution.is_full_cover == matrix.is_full_cover(selected_ids)
    assert solution.solver_name == "cp_sat"
    assert solution.wall_time_seconds >= 0.0
    assert solution.notes is not None
    assert f"matrix_fingerprint={matrix.fingerprint}" in solution.notes


def _assert_matches_oracle_objective(actual: float, expected: float) -> None:
    assert actual == pytest.approx(expected, abs=1e-12, rel=0)


def _solve(matrix: CoverageMatrix, is_budgeted: bool, time_limit_seconds: float) -> Solution:
    if is_budgeted:
        return solve_budgeted_max_coverage(matrix, 3.0, time_limit_seconds)
    return solve_min_cost_cover(matrix, time_limit_seconds)


@pytest.mark.parametrize("seed", range(10))
def test_min_cost_cover_matches_brute_force(seed: int) -> None:
    matrix = _small_matrix(seed)

    solution = solve_min_cost_cover(matrix)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    _assert_matches_oracle_objective(
        solution.total_cost, brute_force_min_cost_cover(matrix).total_cost
    )
    assert matrix.is_full_cover(solution.selected_intervention_ids)
    _assert_matches_matrix(matrix, solution)


@pytest.mark.parametrize("seed", range(10))
def test_budgeted_max_coverage_matches_brute_force(seed: int) -> None:
    matrix = _small_matrix(seed)
    budget = float(seed % 8)

    solution = solve_budgeted_max_coverage(matrix, budget)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    _assert_matches_oracle_objective(
        solution.covered_weight, brute_force_budgeted_max_coverage(matrix, budget).covered_weight
    )
    assert solution.total_cost <= budget
    _assert_matches_matrix(matrix, solution)


def test_cheapest_full_cover_is_not_the_smallest() -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 1.0, "p2": 1.0},
        [
            ("low-a", {"p0"}, CostTier.LOW),
            ("low-b", {"p1"}, CostTier.LOW),
            ("low-c", {"p2"}, CostTier.LOW),
            ("high", {"p0", "p1", "p2"}, CostTier.HIGH),
        ],
    )

    solution = solve_min_cost_cover(matrix)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    _assert_matches_oracle_objective(
        solution.total_cost, brute_force_min_cost_cover(matrix).total_cost
    )
    assert solution.total_cost == 3.0
    assert solution.selected_intervention_ids == ["low-a", "low-b", "low-c"]
    _assert_matches_matrix(matrix, solution)


def test_uncoverable_paths_raise_before_cp_sat_runs() -> None:
    matrix = _matrix(
        {"z": 1.0, "covered": 2.0, "a": 3.0},
        [("fix", {"covered"}, CostTier.LOW)],
    )

    with (
        patch.object(cp_model.CpSolver, "solve") as solve,
        pytest.raises(InfeasibleError) as raised,
    ):
        solve_min_cost_cover(matrix)

    assert raised.value.uncoverable_path_ids == ["a", "z"]
    assert "a" in str(raised.value)
    assert "z" in str(raised.value)
    solve.assert_not_called()


@pytest.mark.parametrize(
    "budget",
    [0.0, 0.9999, 1.0, 1.9999, 3.0, math.nextafter(4.0, -math.inf), 4.0, 4.0001, 1e308],
)
def test_budget_boundary_never_allows_overspend(budget: float) -> None:
    matrix = _matrix(
        {"p0": 0.125, "p1": 0.25},
        [("low", {"p0"}, CostTier.LOW), ("medium", {"p1"}, CostTier.MEDIUM)],
    )

    solution = solve_budgeted_max_coverage(matrix, budget)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    assert solution.total_cost <= budget
    _assert_matches_oracle_objective(
        solution.covered_weight, brute_force_budgeted_max_coverage(matrix, budget).covered_weight
    )
    if budget < 1.0:
        assert solution.selected_intervention_ids == []
    _assert_matches_matrix(matrix, solution)


@pytest.mark.parametrize("has_interventions", [False, True])
def test_empty_paths_return_empty_exact_solutions(has_interventions: bool) -> None:
    matrix = _matrix({}, [])
    if has_interventions:
        graph, _ = generate(REALISTIC)
        catalog = synthesize(graph)
        assert catalog.interventions
        matrix = CoverageMatrix(PathSet(paths=[], truncated=False), catalog, graph)

    for solution in [solve_min_cost_cover(matrix), solve_budgeted_max_coverage(matrix, 9.0)]:
        assert solution.guarantee is OptimalityGuarantee.EXACT
        assert solution.selected_intervention_ids == []
        assert solution.is_full_cover
        _assert_matches_matrix(matrix, solution)


def test_empty_catalog_returns_exact_zero_budgeted_coverage() -> None:
    matrix = _matrix({"p0": 1.0}, [])

    solution = solve_budgeted_max_coverage(matrix, 3.0)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    assert solution.selected_intervention_ids == []
    assert solution.covered_weight == 0.0
    assert solution.uncovered_path_ids == ["p0"]
    _assert_matches_matrix(matrix, solution)


def test_budgeted_coverage_keeps_uncoverable_paths_uncovered() -> None:
    matrix = _matrix(
        {"coverable": 2.0, "uncoverable": 5.0},
        [("fix", {"coverable"}, CostTier.LOW)],
    )

    solution = solve_budgeted_max_coverage(matrix, 1.0)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    _assert_matches_oracle_objective(
        solution.covered_weight, brute_force_budgeted_max_coverage(matrix, 1.0).covered_weight
    )
    assert solution.covered_weight == 2.0
    assert solution.uncovered_path_ids == ["uncoverable"]
    _assert_matches_matrix(matrix, solution)


@pytest.mark.parametrize("budget", [-1.0, math.inf, -math.inf, math.nan])
def test_invalid_budget_is_rejected_before_solving(budget: float) -> None:
    with (
        patch.object(cp_model.CpSolver, "solve") as solve,
        pytest.raises(ValueError, match="budget"),
    ):
        solve_budgeted_max_coverage(_matrix({}, []), budget)
    solve.assert_not_called()


@pytest.mark.parametrize("is_budgeted", [False, True])
@pytest.mark.parametrize("time_limit", [0.0, -1.0, math.inf, -math.inf, math.nan])
def test_invalid_time_limit_is_rejected_before_solving(
    is_budgeted: bool,
    time_limit: float,
) -> None:
    with (
        patch.object(cp_model.CpSolver, "solve") as solve,
        pytest.raises(ValueError, match="time limit"),
    ):
        _solve(_matrix({}, []), is_budgeted, time_limit)
    solve.assert_not_called()


@pytest.mark.parametrize("is_budgeted", [False, True])
@pytest.mark.parametrize("status", [cp_model.OPTIMAL, cp_model.FEASIBLE])
@pytest.mark.parametrize("time_limit", [DEFAULT_TIME_LIMIT_SECONDS, 2.5])
def test_solution_status_and_requested_search_settings(
    is_budgeted: bool,
    status: cp_model.CpSolverStatus,
    time_limit: float,
) -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 2.0},
        [("a", {"p0"}, CostTier.LOW), ("b", {"p0", "p1"}, CostTier.LOW)],
    )
    with (
        patch.object(cp_model.CpSolver, "solve", autospec=True, return_value=status) as solve,
        patch.object(
            cp_model.CpSolver,
            "boolean_value",
            side_effect=lambda variable: variable.name == "b",
        ),
    ):
        solution = _solve(matrix, is_budgeted, time_limit)

    solve.assert_called_once()
    solver = solve.call_args.args[0]
    assert solver.parameters.max_time_in_seconds == time_limit
    assert solver.parameters.num_search_workers == 1
    assert solver.parameters.random_seed == 0
    assert solution.selected_intervention_ids == ["b"]
    if status == cp_model.OPTIMAL:
        assert solution.guarantee is OptimalityGuarantee.EXACT
    else:
        assert solution.guarantee is OptimalityGuarantee.UNKNOWN
        assert solution.notes is not None
        assert "time limit" in solution.notes.lower()
        assert "optimal" in solution.notes.lower()
    _assert_matches_matrix(matrix, solution)


@pytest.mark.parametrize("is_budgeted", [False, True])
@pytest.mark.parametrize(
    ("status", "message"),
    [
        (cp_model.INFEASIBLE, "(?i)infeasib"),
        (cp_model.MODEL_INVALID, "controlled validation error"),
        (cp_model.UNKNOWN, "(?i)time limit"),
    ],
)
def test_error_statuses_never_read_a_selection(
    is_budgeted: bool,
    status: cp_model.CpSolverStatus,
    message: str,
) -> None:
    matrix = _matrix({"p0": 1.0}, [("fix", {"p0"}, CostTier.LOW)])
    with (
        patch.object(cp_model.CpSolver, "solve", return_value=status) as solve,
        patch.object(cp_model.CpSolver, "boolean_value") as boolean_value,
        patch.object(cp_model.CpModel, "validate", return_value="controlled validation error"),
        pytest.raises(SolverError, match=message),
    ):
        _solve(matrix, is_budgeted, 2.5)

    solve.assert_called_once()
    boolean_value.assert_not_called()


@pytest.mark.parametrize("is_budgeted", [False, True])
def test_completed_searches_repeat_the_same_selection(is_budgeted: bool) -> None:
    matrix = _matrix(
        {"p0": 1.0},
        [("b", {"p0"}, CostTier.LOW), ("a", {"p0"}, CostTier.LOW)],
    )
    first = _solve(matrix, is_budgeted, DEFAULT_TIME_LIMIT_SECONDS)
    assert first.guarantee is OptimalityGuarantee.EXACT
    _assert_matches_matrix(matrix, first)

    for _ in range(3):
        repeated = _solve(matrix, is_budgeted, DEFAULT_TIME_LIMIT_SECONDS)
        assert repeated.guarantee is OptimalityGuarantee.EXACT
        assert repeated.total_cost == first.total_cost
        assert repeated.selected_intervention_ids == first.selected_intervention_ids
        _assert_matches_matrix(matrix, repeated)


@pytest.mark.parametrize("heavy_weight", [1.002, 1.004])
def test_thousandth_weights_preserve_the_objective_order(heavy_weight: float) -> None:
    matrix = _matrix(
        {"light": 1.001, "heavy": heavy_weight},
        [("light-fix", {"light"}, CostTier.LOW), ("heavy-fix", {"heavy"}, CostTier.LOW)],
    )

    solution = solve_budgeted_max_coverage(matrix, 1.0)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    _assert_matches_oracle_objective(
        solution.covered_weight, brute_force_budgeted_max_coverage(matrix, 1.0).covered_weight
    )
    assert solution.selected_intervention_ids == ["heavy-fix"]
    _assert_matches_matrix(matrix, solution)


@pytest.mark.parametrize("is_reversed", [False, True])
def test_decimal_objective_ties_allow_only_float_summation_noise(is_reversed: bool) -> None:
    interventions: list[InterventionSpec] = [
        ("split", {"a", "b"}, CostTier.LOW),
        ("single", {"c"}, CostTier.LOW),
    ]
    if is_reversed:
        interventions.reverse()
    matrix = _matrix({"a": 0.1, "b": 0.2, "c": 0.3}, interventions)

    solution = solve_budgeted_max_coverage(matrix, 1.0)

    assert solution.guarantee is OptimalityGuarantee.EXACT
    _assert_matches_oracle_objective(
        solution.covered_weight, brute_force_budgeted_max_coverage(matrix, 1.0).covered_weight
    )
    assert solution.total_cost <= 1.0
    _assert_matches_matrix(matrix, solution)


def test_thousandth_costs_preserve_order_and_budget_boundary() -> None:
    matrix = _matrix(
        {"p0": 1.0},
        [("cheap", {"p0"}, CostTier.LOW), ("expensive", {"p0"}, CostTier.LOW)],
    )
    matrix.intervention_costs[:] = [1.001, 1.004]

    for solution in [
        solve_min_cost_cover(matrix),
        solve_budgeted_max_coverage(matrix, 1.001),
        solve_budgeted_max_coverage(matrix, 1.0039),
    ]:
        assert solution.guarantee is OptimalityGuarantee.EXACT
        assert solution.selected_intervention_ids == ["cheap"]
        assert solution.total_cost == 1.001
        _assert_matches_matrix(matrix, solution)


@pytest.mark.parametrize("field", ["intervention_costs", "path_weights"])
def test_decimal_context_does_not_change_scaling_or_precision_validation(field: str) -> None:
    matrix = _matrix(
        {"light": 1.001, "heavy": 1.004},
        [("cheap", {"light"}, CostTier.LOW), ("expensive", {"heavy"}, CostTier.LOW)],
    )
    matrix.intervention_costs[:] = [1.001, 1.004]

    with localcontext() as context:
        context.prec = 3
        for budget, selected_id in [(1.0039, "cheap"), (1.004, "expensive")]:
            solution = solve_budgeted_max_coverage(matrix, budget)
            assert solution.guarantee is OptimalityGuarantee.EXACT
            assert solution.selected_intervention_ids == [selected_id]
            assert solution.total_cost <= budget
            _assert_matches_matrix(matrix, solution)

        getattr(matrix, field)[0] = 1.0001
        with pytest.raises(ValueError, match="supported precision"):
            solve_budgeted_max_coverage(matrix, 1.004)


@pytest.mark.parametrize("field", ["intervention_costs", "path_weights"])
@pytest.mark.parametrize("value", [1.0001, 0.0, -1.0, math.inf, math.nan, 1e308])
def test_unsupported_coefficients_raise_before_solving(field: str, value: float) -> None:
    matrix = _matrix({"p0": 1.0}, [("fix", {"p0"}, CostTier.LOW)])
    getattr(matrix, field)[0] = value

    with patch.object(cp_model.CpSolver, "solve") as solve, pytest.raises(ValueError):
        _solve(matrix, field == "path_weights", DEFAULT_TIME_LIMIT_SECONDS)
    solve.assert_not_called()


@pytest.mark.parametrize("field", ["intervention_costs", "path_weights"])
def test_unsafe_scaled_coefficient_sum_is_rejected(field: str) -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 1.0},
        [("a", {"p0"}, CostTier.LOW), ("b", {"p1"}, CostTier.LOW)],
    )
    getattr(matrix, field)[:] = [4e15, 4e15]

    with patch.object(cp_model.CpSolver, "solve") as solve, pytest.raises(ValueError):
        _solve(matrix, field == "path_weights", DEFAULT_TIME_LIMIT_SECONDS)
    solve.assert_not_called()


def test_original_float_total_above_budget_raises_without_tolerance() -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 1.0},
        [("a", {"p0"}, CostTier.LOW), ("b", {"p1"}, CostTier.LOW)],
    )
    matrix.intervention_costs[:] = [0.1, 0.2]
    assert math.fsum(matrix.intervention_costs) > 0.3

    with pytest.raises(SolverError, match=r"(?i)budget"):
        solve_budgeted_max_coverage(matrix, 0.3)
