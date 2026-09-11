from time import perf_counter

from lumon.coverage import CoverageMatrix
from lumon.generate import REALISTIC, generate
from lumon.interventions import synthesize
from lumon.paths import extract_paths
from lumon.solve import (
    OptimalityGuarantee,
    solve_budgeted_max_coverage,
    solve_min_cost_cover,
)


def test_realistic_pipeline_reaches_exact_solutions_under_one_second() -> None:
    started = perf_counter()
    graph, _ = generate(REALISTIC)
    path_set = extract_paths(graph)
    catalog = synthesize(graph)
    matrix = CoverageMatrix(path_set, catalog, graph)
    matrix.verify_fingerprint(path_set, catalog)

    full_cover = solve_min_cost_cover(matrix)
    budgeted = solve_budgeted_max_coverage(matrix, budget=1.0)
    elapsed = perf_counter() - started

    assert full_cover.guarantee == OptimalityGuarantee.EXACT
    assert full_cover.is_full_cover
    assert budgeted.guarantee == OptimalityGuarantee.EXACT
    assert budgeted.total_cost <= 1.0
    assert elapsed < 1.0, f"REALISTIC pipeline took {elapsed:.3f} seconds"
