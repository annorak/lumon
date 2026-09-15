"""Check shrinking with a broken toy and replay reviewed full-cover examples."""

import json
import math
from pathlib import Path

from hypothesis import find, settings

from lumon.coverage import CoverageMatrix
from lumon.model import CostTier
from lumon.solve import OptimalityGuarantee, solve_min_cost_cover
from tests.brute_force import brute_force_min_cost_cover
from tests.property.strategies import CoverageCase, build_matrix, matrix_cases


def _broken_single_change_cost(matrix: CoverageMatrix) -> float:
    """Wrong on purpose: prefer one full-cover change over cheaper combinations."""
    if not matrix.path_ids:
        return 0.0
    single_change_costs = [
        float(matrix.intervention_costs[index])
        for index, item in enumerate(matrix.intervention_ids)
        if matrix.is_full_cover([item])
    ]
    if single_change_costs:
        return min(single_change_costs)
    return math.fsum(matrix.intervention_costs)


def _is_counterexample(case: CoverageCase) -> bool:
    matrix = build_matrix(case)
    expected = brute_force_min_cost_cover(matrix)
    assert expected.guarantee is OptimalityGuarantee.EXACT
    return _broken_single_change_cost(matrix) > expected.total_cost


def test_broken_toy_shrinks_to_at_most_three_interventions() -> None:
    counterexample = find(
        matrix_cases(is_feasible=True, min_paths=1),
        _is_counterexample,
        settings=settings(),
    )

    assert len(counterexample.rows) <= 3
    assert _is_counterexample(counterexample)


def test_saved_full_cover_regressions() -> None:
    examples = sorted((Path(__file__).parent / "regression").glob("*.json"))
    assert examples, "the reviewed regression corpus must not be empty"

    for path in examples:
        example = json.loads(path.read_text())
        case = CoverageCase(
            rows=example["rows"],
            costs=[CostTier(value) for value in example["costs"]],
            weights=example["weights"],
        )
        matrix = build_matrix(case)
        assert len(matrix.intervention_ids) <= 12
        for solve in (solve_min_cost_cover, brute_force_min_cost_cover):
            solution = solve(matrix)
            assert solution.guarantee is OptimalityGuarantee.EXACT
            assert solution.is_full_cover
            assert solution.total_cost == example["expected_cost"]
            assert solution.selected_intervention_ids == example["expected_selected_ids"]
