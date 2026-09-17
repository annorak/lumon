"""Focused minimum-cost full-cover checks for the demo release."""

import math
from itertools import product

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from lumon.coverage import CoverageMatrix
from lumon.generate import GeneratorParams, generate
from lumon.interventions import synthesize
from lumon.io import check_invariants
from lumon.model import CostTier, Evidence
from lumon.paths import extract_paths
from lumon.solve import InfeasibleError, OptimalityGuarantee, Solution, solve_min_cost_cover
from tests.brute_force import brute_force_min_cost_cover
from tests.property.strategies import CoverageCase, build_matrix, generated_params, matrix_cases


def _assert_result(case: CoverageCase, matrix: CoverageMatrix, solution: Solution) -> None:
    selected_ids = solution.selected_intervention_ids
    assert selected_ids == sorted(set(selected_ids))
    assert set(selected_ids) <= set(matrix.intervention_ids)
    selected_rows = [index for index in range(len(case.rows)) if f"i{index:03d}" in selected_ids]
    covered_columns = [
        column
        for column in range(len(case.weights))
        if any(case.rows[row][column] for row in selected_rows)
    ]
    covered_ids = [f"p{column:03d}" for column in covered_columns]
    uncovered_ids = [
        f"p{column:03d}" for column in range(len(case.weights)) if column not in covered_columns
    ]

    assert solution.covered_path_ids == covered_ids
    assert solution.uncovered_path_ids == uncovered_ids
    assert solution.total_cost == math.fsum(case.costs[row].numeric_value for row in selected_rows)
    assert solution.covered_weight == sum(case.weights[column] for column in covered_columns)
    assert solution.is_full_cover == (not uncovered_ids)
    assert matrix.is_full_cover(selected_ids) == solution.is_full_cover
    assert solution.notes == f"matrix_fingerprint={matrix.fingerprint}"


@example(case=CoverageCase([], [], []))
@example(case=CoverageCase([[]], [CostTier.LOW], []))
@example(
    case=CoverageCase(
        [[True, True], [True, True], [False, False]],
        [CostTier.LOW, CostTier.LOW, CostTier.HIGH],
        [1, 1],
    )
)
@given(case=matrix_cases(is_feasible=True))
def test_p1_p7_cp_sat_full_cover_is_consistent_and_repeatable(case: CoverageCase) -> None:
    matrix = build_matrix(case)
    first = solve_min_cost_cover(matrix)
    repeated = solve_min_cost_cover(matrix)

    for solution in (first, repeated):
        assert solution.guarantee is OptimalityGuarantee.EXACT
        _assert_result(case, matrix, solution)
        assert solution.is_full_cover
    assert repeated.selected_intervention_ids == first.selected_intervention_ids
    assert repeated.total_cost == first.total_cost


@settings(max_examples=settings().max_examples // 4)
@given(case=matrix_cases(is_feasible=True))
def test_p2_p7_brute_force_agrees_on_cost_and_repeats_its_selection(case: CoverageCase) -> None:
    matrix = build_matrix(case)
    assert len(matrix.intervention_ids) <= 12
    actual = solve_min_cost_cover(matrix)
    expected = brute_force_min_cost_cover(matrix)
    repeated = brute_force_min_cost_cover(matrix)

    for solution in (actual, expected, repeated):
        assert solution.guarantee is OptimalityGuarantee.EXACT
        _assert_result(case, matrix, solution)
        assert solution.is_full_cover
    assert actual.total_cost == pytest.approx(expected.total_cost, abs=1e-12, rel=0)
    assert repeated.selected_intervention_ids == expected.selected_intervention_ids
    assert repeated.total_cost == expected.total_cost


@given(case=matrix_cases(min_paths=1), data=st.data())
def test_p8_infeasibility_names_exactly_the_uncoverable_paths(
    case: CoverageCase, data: st.DataObject
) -> None:
    missing_column = data.draw(st.integers(0, len(case.weights) - 1))
    rows = [row.copy() for row in case.rows]
    for row in rows:
        row[missing_column] = False
    matrix = build_matrix(CoverageCase(rows, case.costs, case.weights))
    expected = [
        f"p{column:03d}"
        for column in range(len(case.weights))
        if not any(row[column] for row in rows)
    ]

    assert expected
    for solve in (solve_min_cost_cover, brute_force_min_cost_cover):
        with pytest.raises(InfeasibleError) as raised:
            solve(matrix)
        assert raised.value.uncoverable_path_ids == expected
        assert str(raised.value) == (
            "full severance is infeasible; uncoverable validated path ids: " + ", ".join(expected)
        )


@settings(max_examples=settings().max_examples // 4)
@given(
    case=matrix_cases(max_interventions=11, min_interventions=1, min_paths=1, is_feasible=True),
    data=st.data(),
)
def test_p9_a_strictly_dominated_change_cannot_improve_minimum_cost(
    case: CoverageCase, data: st.DataObject
) -> None:
    rows = [row.copy() for row in case.rows]
    rows[0][0] = True
    costs = case.costs.copy()
    costs[0] = data.draw(st.sampled_from([CostTier.LOW, CostTier.MEDIUM]))
    base = CoverageCase(rows, costs, case.weights)
    retained_columns = data.draw(
        st.lists(st.booleans(), min_size=len(case.weights), max_size=len(case.weights))
    )
    dominated_row = [
        is_covered and is_retained
        for is_covered, is_retained in zip(rows[0], retained_columns, strict=True)
    ]
    dominated_row[0] = False
    higher_cost = CostTier.MEDIUM if costs[0] is CostTier.LOW else CostTier.HIGH
    extended = CoverageCase([*rows, dominated_row], [*costs, higher_cost], case.weights)
    before = build_matrix(base)
    after = build_matrix(extended)

    assert len(after.intervention_ids) <= 12
    assert {i for i, value in enumerate(dominated_row) if value} < {
        i for i, value in enumerate(rows[0]) if value
    }
    assert higher_cost.numeric_value > costs[0].numeric_value
    for solve in (solve_min_cost_cover, brute_force_min_cost_cover):
        original = solve(before)
        added = solve(after)
        assert original.guarantee is OptimalityGuarantee.EXACT
        assert added.guarantee is OptimalityGuarantee.EXACT
        _assert_result(base, before, original)
        _assert_result(extended, after, added)
        assert original.is_full_cover and added.is_full_cover
        assert added.total_cost == pytest.approx(original.total_cost, abs=1e-12, rel=0)


@given(params=generated_params())
def test_p10_generated_graphs_keep_their_paths_through_the_real_pipeline(
    params: GeneratorParams,
) -> None:
    graph, truth = generate(params)
    assert check_invariants(graph).violations == []
    paths = extract_paths(graph)
    assert not paths.truncated
    assert sorted(path.node_ids for path in paths.paths) == truth.path_node_sequences
    assert all(len(path.edge_ids) == params.depth + 1 for path in paths.paths)
    assert [path.weight for path in paths.paths] == [
        truth.objective_weights[path.objective_id] for path in paths.paths
    ]
    validated_ids = {edge.id for edge in graph.edges if edge.evidence is Evidence.VALIDATED}
    assert all(set(path.edge_ids) <= validated_ids for path in paths.paths)

    catalog = synthesize(graph)
    matrix = CoverageMatrix(paths, catalog, graph)
    matrix.verify_fingerprint(paths, catalog)
    solution = solve_min_cost_cover(matrix)
    assert solution.guarantee is OptimalityGuarantee.EXACT
    interventions_by_id = catalog.by_id()
    selected = [interventions_by_id[item] for item in solution.selected_intervention_ids]
    removed_edges = {edge_id for item in selected for edge_id in item.removes_edge_ids}

    assert all(removed_edges.intersection(path.edge_ids) for path in paths.paths)
    assert solution.covered_path_ids == sorted(path.id for path in paths.paths)
    assert solution.uncovered_path_ids == []
    assert solution.is_full_cover
    assert solution.covered_weight == sum(
        truth.objective_weights[path.objective_id] for path in paths.paths
    )
    assert solution.total_cost == math.fsum(item.cost.tier.numeric_value for item in selected)
    assert solution.notes == f"matrix_fingerprint={matrix.fingerprint}"


@pytest.mark.parametrize(("row_count", "column_count"), tuple(product((0, 1, 12), (0, 1, 8))))
@given(data=st.data())
def test_strategy_supports_empty_single_and_larger_dimensions(
    row_count: int, column_count: int, data: st.DataObject
) -> None:
    case = data.draw(
        matrix_cases(
            min_interventions=row_count,
            max_interventions=row_count,
            min_paths=column_count,
            max_paths=column_count,
        )
    )
    matrix = build_matrix(case)

    assert len(case.costs) == row_count
    assert len(case.weights) == column_count
    assert all(weight >= 1 for weight in case.weights)
    assert matrix.to_dense().shape == (row_count, column_count)
    assert matrix.to_dense().tolist() == case.rows
    assert list(matrix.intervention_costs) == [tier.numeric_value for tier in case.costs]
    assert list(matrix.path_weights) == case.weights


def test_known_optimum_counts_overlapping_selected_changes_once() -> None:
    case = CoverageCase(
        rows=[[True, True, False], [False, True, True], [True, True, True]],
        costs=[CostTier.LOW, CostTier.LOW, CostTier.HIGH],
        weights=[5, 3, 2],
    )
    matrix = build_matrix(case)

    for solve in (solve_min_cost_cover, brute_force_min_cost_cover):
        solution = solve(matrix)
        assert solution.guarantee is OptimalityGuarantee.EXACT
        assert solution.selected_intervention_ids == ["i000", "i001"]
        assert solution.total_cost == 2.0
        assert solution.covered_weight == 10.0
        _assert_result(case, matrix, solution)
