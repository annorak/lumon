from typing import NamedTuple

import pytest

from lumon.coverage import CoverageMatrix, StaleMatrixError, summarize
from lumon.generate import REALISTIC, generate
from lumon.interventions import synthesize
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
from lumon.paths import extract_paths


class _CoverageCase(NamedTuple):
    graph: AttackGraph
    path_set: PathSet
    catalog: InterventionCatalog
    matrix: CoverageMatrix


def _path(index: int) -> Path:
    objective_id = f"objective-{index}"
    return Path(
        id=f"p{index}",
        edge_ids=[f"e{index}"],
        node_ids=["entry", objective_id],
        entry_id="entry",
        objective_id=objective_id,
        weight=float(index + 1),
    )


def _intervention(
    intervention_id: str,
    edge_ids: set[str],
    cost_tier: CostTier,
) -> Intervention:
    return Intervention(
        id=intervention_id,
        name=intervention_id,
        intervention_class=InterventionClass.ACCESS_CONTROL_ADD,
        removes_edge_ids=frozenset(edge_ids),
        cost=Cost(
            tier=cost_tier,
            source=CostSource.ASSUMED_DEFAULT,
            justification="test cost",
        ),
    )


def _build_case() -> _CoverageCase:
    graph = AttackGraph(
        nodes=[
            Node(
                id="entry",
                type=NodeType.ENTRY_POINT,
                label="entry",
            ),
            *[
                Node(
                    id=f"objective-{index}",
                    type=NodeType.OBJECTIVE,
                    label=f"objective {index}",
                    weight=float(index + 1),
                )
                for index in range(8)
            ],
        ],
        edges=[
            Edge(
                id=f"e{index}",
                source="entry",
                target=f"objective-{index}",
                type=EdgeType.REACHES,
                evidence=Evidence.VALIDATED,
            )
            for index in range(8)
        ],
        metadata={"graph_id": "coverage-test"},
    )
    path_set = PathSet(
        paths=[_path(index) for index in range(6)],
        truncated=False,
        graph_id="coverage-test",
    )
    catalog = InterventionCatalog(
        interventions=[
            _intervention("i0", {"e0", "e1", "e2"}, CostTier.LOW),
            _intervention("i1", {"e2", "e3"}, CostTier.MEDIUM),
            _intervention("i2", {"e3", "e4", "e5"}, CostTier.HIGH),
            _intervention("i3", {"e6"}, CostTier.LOW),
        ]
    )
    return _CoverageCase(
        graph=graph,
        path_set=path_set,
        catalog=catalog,
        matrix=CoverageMatrix(path_set, catalog, graph),
    )


@pytest.fixture
def coverage_case() -> _CoverageCase:
    return _build_case()


def test_hand_computed_matrix_matches_cell_by_cell(
    coverage_case: _CoverageCase,
) -> None:
    expected = [
        [True, True, True, False, False, False],
        [False, False, True, True, False, False],
        [False, False, False, True, True, True],
        [False, False, False, False, False, False],
    ]

    assert coverage_case.matrix.intervention_ids == ["i0", "i1", "i2", "i3"]
    assert coverage_case.matrix.path_ids == [
        "p0",
        "p1",
        "p2",
        "p3",
        "p4",
        "p5",
    ]
    assert coverage_case.matrix.path_weights.tolist() == [
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
        6.0,
    ]
    assert coverage_case.matrix.intervention_costs.tolist() == [
        1.0,
        3.0,
        9.0,
        1.0,
    ]
    assert coverage_case.matrix.to_dense().tolist() == expected

    for row, intervention in enumerate(coverage_case.catalog.interventions):
        for column, path in enumerate(coverage_case.path_set.paths):
            assert coverage_case.matrix.covers(intervention.id, path.id) is expected[row][column]


def test_directional_queries_are_consistent(
    coverage_case: _CoverageCase,
) -> None:
    matrix = coverage_case.matrix

    assert matrix.paths_covered_by("i1") == ["p2", "p3"]
    assert matrix.interventions_covering("p2") == ["i0", "i1"]

    for intervention_id in matrix.intervention_ids:
        covered_path_ids = matrix.paths_covered_by(intervention_id)
        for path_id in matrix.path_ids:
            assert (path_id in covered_path_ids) is (
                intervention_id in matrix.interventions_covering(path_id)
            )


def test_uncoverable_path_is_reported_with_its_weight(
    coverage_case: _CoverageCase,
) -> None:
    path_set = PathSet(
        paths=[*coverage_case.path_set.paths, _path(7)],
        truncated=False,
        graph_id="coverage-test",
    )
    matrix = CoverageMatrix(
        path_set,
        coverage_case.catalog,
        coverage_case.graph,
    )
    report = summarize(matrix)

    assert matrix.uncoverable_path_ids() == ["p7"]
    assert report.uncoverable_path_ids == ["p7"]
    assert report.uncoverable_total_weight == 8.0
    assert report.full_severance_feasible is False


def test_redundant_intervention_is_reported(
    coverage_case: _CoverageCase,
) -> None:
    assert coverage_case.matrix.redundant_intervention_ids() == ["i3"]


def test_domination_requires_a_strict_improvement(
    coverage_case: _CoverageCase,
) -> None:
    catalog = InterventionCatalog(
        interventions=[
            _intervention("a", {"e0", "e1"}, CostTier.LOW),
            _intervention("b", {"e0", "e1"}, CostTier.LOW),
            _intervention("c", {"e0"}, CostTier.MEDIUM),
            _intervention("d", {"e0", "e1"}, CostTier.HIGH),
        ]
    )
    matrix = CoverageMatrix(
        coverage_case.path_set,
        catalog,
        coverage_case.graph,
    )

    assert matrix.dominated_intervention_ids() == ["c", "d"]


def test_full_cover_requires_every_path(
    coverage_case: _CoverageCase,
) -> None:
    assert coverage_case.matrix.is_full_cover(["i0", "i2"]) is True
    assert coverage_case.matrix.is_full_cover(["i0", "i1"]) is False


def test_covered_weight_does_not_double_count_overlaps(
    coverage_case: _CoverageCase,
) -> None:
    assert coverage_case.matrix.weight_covered_by(["i0", "i1"]) == 10.0


def test_to_dense_returns_a_copy(
    coverage_case: _CoverageCase,
) -> None:
    dense = coverage_case.matrix.to_dense()
    dense[0, 0] = False

    assert coverage_case.matrix.covers("i0", "p0") is True


def test_fingerprint_accepts_unchanged_inputs_and_rejects_an_appended_path(
    coverage_case: _CoverageCase,
) -> None:
    coverage_case.matrix.verify_fingerprint(
        coverage_case.path_set,
        coverage_case.catalog,
    )

    coverage_case.path_set.paths.append(_path(7))

    with pytest.raises(StaleMatrixError, match="rebuild"):
        coverage_case.matrix.verify_fingerprint(
            coverage_case.path_set,
            coverage_case.catalog,
        )


def test_fingerprint_detects_reordering(
    coverage_case: _CoverageCase,
) -> None:
    coverage_case.path_set.paths.reverse()

    with pytest.raises(StaleMatrixError, match="rebuild"):
        coverage_case.matrix.verify_fingerprint(
            coverage_case.path_set,
            coverage_case.catalog,
        )


def test_fingerprint_detects_changed_weights_and_costs() -> None:
    changed_weight = _build_case()
    original_path = changed_weight.path_set.paths[0]
    changed_weight.path_set.paths[0] = original_path.model_copy(update={"weight": 99.0})

    with pytest.raises(StaleMatrixError):
        changed_weight.matrix.verify_fingerprint(
            changed_weight.path_set,
            changed_weight.catalog,
        )

    changed_cost = _build_case()
    changed_cost.catalog.interventions[0] = _intervention(
        "i0",
        {"e0", "e1", "e2"},
        CostTier.HIGH,
    )

    with pytest.raises(StaleMatrixError):
        changed_cost.matrix.verify_fingerprint(
            changed_cost.path_set,
            changed_cost.catalog,
        )


def test_unknown_ids_raise_key_error(
    coverage_case: _CoverageCase,
) -> None:
    with pytest.raises(KeyError):
        coverage_case.matrix.covers("missing", "p0")
    with pytest.raises(KeyError):
        coverage_case.matrix.covers("i0", "missing")
    with pytest.raises(KeyError):
        coverage_case.matrix.weight_covered_by(["missing"])


def test_constructor_rejects_path_edges_outside_the_validated_graph(
    coverage_case: _CoverageCase,
) -> None:
    invalid_path = Path(
        id="invalid",
        edge_ids=["missing"],
        node_ids=["entry", "objective-0"],
        entry_id="entry",
        objective_id="objective-0",
        weight=1.0,
    )
    path_set = PathSet(paths=[invalid_path], truncated=False)

    with pytest.raises(ValueError, match=r"path set.*missing"):
        CoverageMatrix(
            path_set,
            coverage_case.catalog,
            coverage_case.graph,
        )


def test_constructor_rejects_intervention_edges_outside_the_validated_graph(
    coverage_case: _CoverageCase,
) -> None:
    catalog = InterventionCatalog(
        interventions=[_intervention("invalid", {"missing"}, CostTier.LOW)]
    )

    with pytest.raises(ValueError, match=r"intervention catalog.*missing"):
        CoverageMatrix(
            coverage_case.path_set,
            catalog,
            coverage_case.graph,
        )


def test_summary_reports_the_matrix_shape_and_density(
    coverage_case: _CoverageCase,
) -> None:
    report = summarize(coverage_case.matrix)

    assert report.intervention_count == 4
    assert report.path_count == 6
    assert report.density == pytest.approx(1 / 3)
    assert report.uncoverable_path_ids == []
    assert report.uncoverable_total_weight == 0.0
    assert report.redundant_intervention_ids == ["i3"]
    assert report.dominated_intervention_ids == ["i3"]
    assert report.full_severance_feasible is True


def test_empty_dimensions_keep_their_meaning(
    coverage_case: _CoverageCase,
) -> None:
    empty_path_set = PathSet(
        paths=[],
        truncated=False,
        graph_id="coverage-test",
    )
    no_paths = CoverageMatrix(
        empty_path_set,
        coverage_case.catalog,
        coverage_case.graph,
    )

    assert no_paths.to_dense().shape == (4, 0)
    assert no_paths.is_full_cover([]) is True
    assert summarize(no_paths).density == 0.0
    assert summarize(no_paths).full_severance_feasible is True

    empty_catalog = InterventionCatalog(interventions=[])
    no_interventions = CoverageMatrix(
        coverage_case.path_set,
        empty_catalog,
        coverage_case.graph,
    )

    assert no_interventions.to_dense().shape == (0, 6)
    assert no_interventions.uncoverable_path_ids() == no_interventions.path_ids
    assert no_interventions.is_full_cover([]) is False


def test_repr_shows_small_matrices_and_bounds_large_ones(
    coverage_case: _CoverageCase,
) -> None:
    rendered = repr(coverage_case.matrix)

    assert "i0" in rendered
    assert "p0" in rendered
    assert "[[1, 1, 1, 0, 0, 0]" in rendered

    large_path_set = PathSet(
        paths=[
            coverage_case.path_set.paths[index % 6].model_copy(update={"id": f"large-{index}"})
            for index in range(13)
        ],
        truncated=False,
    )
    large = CoverageMatrix(
        large_path_set,
        coverage_case.catalog,
        coverage_case.graph,
    )

    assert repr(large) == "CoverageMatrix(shape=(4, 13))"


def test_realistic_pipeline_builds_a_nontrivial_matrix() -> None:
    graph, _ = generate(REALISTIC)
    path_set = extract_paths(graph)
    catalog = synthesize(graph)

    matrix = CoverageMatrix(path_set, catalog, graph)
    density = summarize(matrix).density

    assert matrix.to_dense().shape == (
        len(catalog.interventions),
        len(path_set.paths),
    )
    assert 0.0 < density < 1.0
