import pytest

from lumon.coverage import CoverageMatrix
from lumon.model import (
    AttackGraph,
    Cost,
    CostSource,
    CostTier,
    Edge,
    EdgeType,
    Evidence,
    Intervention,
    InterventionCatalog,
    InterventionClass,
    Node,
    NodeType,
    Path,
    PathSet,
)
from lumon.solve import InfeasibleError, OptimalityGuarantee, Solution
from tests.brute_force import (
    BRUTE_FORCE_MAX_INTERVENTIONS,
    InstanceTooLargeError,
    brute_force_budgeted_max_coverage,
    brute_force_min_cost_cover,
)

InterventionSpec = tuple[str, set[str], CostTier]


def _matrix(
    path_weights: dict[str, float],
    interventions: list[InterventionSpec],
) -> CoverageMatrix:
    graph = AttackGraph(
        nodes=[
            Node(id="entry", type=NodeType.ENTRY_POINT, label="entry"),
            *[
                Node(
                    id=f"objective-{path_id}",
                    type=NodeType.OBJECTIVE,
                    label=path_id,
                    weight=weight,
                )
                for path_id, weight in path_weights.items()
            ],
        ],
        edges=[
            Edge(
                id=f"edge-{path_id}",
                source="entry",
                target=f"objective-{path_id}",
                type=EdgeType.REACHES,
                evidence=Evidence.VALIDATED,
            )
            for path_id in path_weights
        ],
    )
    path_set = PathSet(
        paths=[
            Path(
                id=path_id,
                edge_ids=[f"edge-{path_id}"],
                node_ids=["entry", f"objective-{path_id}"],
                entry_id="entry",
                objective_id=f"objective-{path_id}",
                weight=weight,
            )
            for path_id, weight in path_weights.items()
        ],
        truncated=False,
    )
    catalog = InterventionCatalog(
        interventions=[
            Intervention(
                id=intervention_id,
                name=intervention_id,
                intervention_class=InterventionClass.ACCESS_CONTROL_ADD,
                removes_edge_ids=frozenset(f"edge-{path_id}" for path_id in covered_path_ids),
                cost=Cost(
                    tier=cost_tier,
                    source=CostSource.ASSUMED_DEFAULT,
                    justification="test cost",
                ),
            )
            for intervention_id, covered_path_ids, cost_tier in interventions
        ]
    )
    return CoverageMatrix(path_set, catalog, graph)


def test_min_cost_cover_matches_a_hand_computed_answer() -> None:
    matrix = _matrix(
        {"p0": 5.0, "p1": 3.0, "p2": 2.0},
        [
            ("a", {"p0", "p1"}, CostTier.LOW),
            ("b", {"p2"}, CostTier.MEDIUM),
            ("c", {"p0", "p1", "p2"}, CostTier.HIGH),
        ],
    )

    solution = brute_force_min_cost_cover(matrix)

    assert solution.selected_intervention_ids == ["a", "b"]
    assert solution.total_cost == 4.0
    assert solution.covered_path_ids == ["p0", "p1", "p2"]
    assert solution.covered_weight == 10.0
    assert solution.uncovered_path_ids == []
    assert solution.is_full_cover is True
    assert solution.solver_name == "brute_force"
    assert solution.guarantee is OptimalityGuarantee.EXACT
    assert solution.wall_time_seconds >= 0.0
    assert solution.notes == f"matrix_fingerprint={matrix.fingerprint}"


def test_cheapest_full_cover_is_not_assumed_to_be_the_smallest() -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 1.0, "p2": 1.0},
        [
            ("low-a", {"p0"}, CostTier.LOW),
            ("low-b", {"p1"}, CostTier.LOW),
            ("low-c", {"p2"}, CostTier.LOW),
            ("high", {"p0", "p1", "p2"}, CostTier.HIGH),
        ],
    )

    solution = brute_force_min_cost_cover(matrix)

    assert solution.selected_intervention_ids == ["low-a", "low-b", "low-c"]
    assert solution.total_cost == 3.0


def test_instance_above_the_hard_cap_is_rejected_by_both_variants() -> None:
    actual_size = BRUTE_FORCE_MAX_INTERVENTIONS + 1
    matrix = _matrix(
        {"p0": 1.0},
        [(f"i{index:02d}", {"p0"}, CostTier.LOW) for index in range(actual_size)],
    )

    with pytest.raises(
        InstanceTooLargeError,
        match=rf"{BRUTE_FORCE_MAX_INTERVENTIONS} interventions; received {actual_size}",
    ):
        brute_force_min_cost_cover(matrix)

    with pytest.raises(
        InstanceTooLargeError,
        match=rf"{BRUTE_FORCE_MAX_INTERVENTIONS} interventions; received {actual_size}",
    ):
        brute_force_budgeted_max_coverage(matrix, 0.0)


def test_uncoverable_path_raises_with_its_id() -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 1.0},
        [("only-p0", {"p0"}, CostTier.LOW)],
    )

    with pytest.raises(InfeasibleError) as raised:
        brute_force_min_cost_cover(matrix)

    assert raised.value.uncoverable_path_ids == ["p1"]
    assert "p1" in str(raised.value)


def test_budgeted_variant_accepts_an_exact_budget_boundary() -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 2.0},
        [
            ("low", {"p0"}, CostTier.LOW),
            ("medium", {"p1"}, CostTier.MEDIUM),
        ],
    )

    solution = brute_force_budgeted_max_coverage(matrix, 4.0)

    assert solution.selected_intervention_ids == ["low", "medium"]
    assert solution.total_cost == 4.0
    assert solution.covered_weight == 3.0
    assert solution.is_full_cover is True
    assert solution.guarantee is OptimalityGuarantee.EXACT


def test_equal_results_use_the_documented_tie_breaking() -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 1.0, "p2": 1.0},
        [
            ("low-a", {"p0"}, CostTier.LOW),
            ("low-b", {"p1"}, CostTier.LOW),
            ("low-c", {"p2"}, CostTier.LOW),
            ("medium-z", {"p0", "p1", "p2"}, CostTier.MEDIUM),
            ("medium-a", {"p0", "p1", "p2"}, CostTier.MEDIUM),
        ],
    )

    for _ in range(5):
        assert brute_force_min_cost_cover(matrix).selected_intervention_ids == ["medium-a"]
        assert brute_force_budgeted_max_coverage(
            matrix,
            3.0,
        ).selected_intervention_ids == ["medium-a"]


def test_budgeted_tie_prefers_lower_cost() -> None:
    matrix = _matrix(
        {"p0": 1.0, "p1": 1.0},
        [
            ("low-a", {"p0"}, CostTier.LOW),
            ("low-b", {"p1"}, CostTier.LOW),
            ("medium", {"p0", "p1"}, CostTier.MEDIUM),
        ],
    )

    solution = brute_force_budgeted_max_coverage(matrix, 3.0)

    assert solution.selected_intervention_ids == ["low-a", "low-b"]
    assert solution.total_cost == 2.0


@pytest.mark.parametrize(
    "budget",
    [
        pytest.param(-1.0, id="negative"),
        pytest.param(float("inf"), id="positive infinity"),
        pytest.param(float("-inf"), id="negative infinity"),
        pytest.param(float("nan"), id="not a number"),
    ],
)
def test_budget_must_be_finite_and_non_negative(budget: float) -> None:
    matrix = _matrix(
        {"p0": 1.0},
        [("low", {"p0"}, CostTier.LOW)],
    )

    with pytest.raises(ValueError, match="finite and greater than or equal to 0"):
        brute_force_budgeted_max_coverage(matrix, budget)


def test_zero_budget_returns_an_empty_exact_solution() -> None:
    matrix = _matrix(
        {"p0": 1.0},
        [("low", {"p0"}, CostTier.LOW)],
    )

    solution = brute_force_budgeted_max_coverage(matrix, 0.0)

    assert solution.selected_intervention_ids == []
    assert solution.total_cost == 0.0
    assert solution.covered_path_ids == []
    assert solution.covered_weight == 0.0
    assert solution.uncovered_path_ids == ["p0"]
    assert solution.is_full_cover is False
    assert solution.guarantee is OptimalityGuarantee.EXACT


def test_budgeted_cover_prefers_weight_over_path_count() -> None:
    matrix = _matrix(
        {"heavy": 10.0, "light-a": 2.0, "light-b": 2.0},
        [
            ("heavy-fix", {"heavy"}, CostTier.MEDIUM),
            ("light-a-fix", {"light-a"}, CostTier.LOW),
            ("light-b-fix", {"light-b"}, CostTier.LOW),
            ("all-paths", {"heavy", "light-a", "light-b"}, CostTier.HIGH),
        ],
    )

    solution = brute_force_budgeted_max_coverage(matrix, 3.0)

    assert solution.selected_intervention_ids == ["heavy-fix"]
    assert solution.total_cost == 3.0
    assert solution.covered_path_ids == ["heavy"]
    assert solution.covered_weight == 10.0
    assert solution.uncovered_path_ids == ["light-a", "light-b"]
    assert solution.is_full_cover is False
    assert solution.guarantee is OptimalityGuarantee.EXACT


def test_empty_path_set_returns_an_empty_exact_solution() -> None:
    matrix = _matrix({}, [])

    for solution in [
        brute_force_min_cost_cover(matrix),
        brute_force_budgeted_max_coverage(matrix, 0.0),
    ]:
        assert solution.selected_intervention_ids == []
        assert solution.total_cost == 0.0
        assert solution.covered_path_ids == []
        assert solution.covered_weight == 0.0
        assert solution.uncovered_path_ids == []
        assert solution.is_full_cover is True
        assert solution.guarantee is OptimalityGuarantee.EXACT


def test_empty_catalog_leaves_every_path_uncovered() -> None:
    matrix = _matrix({"z": 2.0, "a": 1.0}, [])

    with pytest.raises(InfeasibleError) as raised:
        brute_force_min_cost_cover(matrix)

    assert raised.value.uncoverable_path_ids == ["a", "z"]

    solution = brute_force_budgeted_max_coverage(matrix, 3.0)

    assert solution.selected_intervention_ids == []
    assert solution.total_cost == 0.0
    assert solution.covered_weight == 0.0
    assert solution.uncovered_path_ids == ["a", "z"]
    assert solution.is_full_cover is False
    assert solution.guarantee is OptimalityGuarantee.EXACT


def test_solution_counts_overlap_once_and_preserves_notes() -> None:
    matrix = _matrix(
        {"p1": 2.0, "p0": 5.0, "p2": 3.0},
        [
            ("z", {"p0", "p1"}, CostTier.LOW),
            ("a", {"p1"}, CostTier.LOW),
        ],
    )

    solution = Solution.from_matrix(
        matrix,
        ["z", "a"],
        solver_name="test",
        guarantee=OptimalityGuarantee.UNKNOWN,
        wall_time_seconds=0.0,
        notes="time limit reached",
    )

    assert solution.selected_intervention_ids == ["a", "z"]
    assert solution.total_cost == 2.0
    assert solution.covered_path_ids == ["p0", "p1"]
    assert solution.covered_weight == 7.0
    assert solution.uncovered_path_ids == ["p2"]
    assert solution.is_full_cover is False
    assert solution.guarantee is OptimalityGuarantee.UNKNOWN
    assert solution.notes == f"time limit reached; matrix_fingerprint={matrix.fingerprint}"
