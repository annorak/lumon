"""Synthetic inputs for full-cover checks. No production interface is changed."""

from dataclasses import dataclass

from hypothesis import strategies as st

from lumon.coverage import CoverageMatrix
from lumon.generate import GeneratorParams
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


@dataclass(frozen=True)
class CoverageCase:
    rows: list[list[bool]]
    costs: list[CostTier]
    weights: list[int]


def build_matrix(case: CoverageCase) -> CoverageMatrix:
    objectives = [
        Node(
            id=f"objective-{index:03d}",
            type=NodeType.OBJECTIVE,
            label=f"objective {index}",
            weight=float(weight),
        )
        for index, weight in enumerate(case.weights)
    ]
    edges = [
        Edge(
            id=f"e{index:03d}",
            source="entry",
            target=objective.id,
            type=EdgeType.REACHES,
            evidence=Evidence.VALIDATED,
        )
        for index, objective in enumerate(objectives)
    ]
    graph = AttackGraph(
        nodes=[
            Node(id="entry", type=NodeType.ENTRY_POINT, label="entry"),
            Node(id="off-path-service", type=NodeType.SERVICE, label="off-path service"),
            *objectives,
        ],
        edges=[
            *edges,
            Edge(
                id="off-path-edge",
                source="entry",
                target="off-path-service",
                type=EdgeType.REACHES,
                evidence=Evidence.VALIDATED,
            ),
        ],
    )
    path_set = PathSet(
        paths=[
            Path(
                id=f"p{index:03d}",
                edge_ids=[edge.id],
                node_ids=[edge.source, edge.target],
                entry_id=edge.source,
                objective_id=edge.target,
                weight=float(case.weights[index]),
            )
            for index, edge in enumerate(edges)
        ],
        truncated=False,
    )
    catalog = InterventionCatalog(
        interventions=[
            Intervention(
                id=f"i{index:03d}",
                name=f"test change {index}",
                intervention_class=InterventionClass.ACCESS_CONTROL_ADD,
                # A change may remove an edge outside the supplied path set.
                removes_edge_ids=frozenset(
                    edge.id for edge, covered in zip(edges, row, strict=True) if covered
                )
                or frozenset({"off-path-edge"}),
                cost=Cost(
                    tier=tier,
                    source=CostSource.ASSUMED_DEFAULT,
                    justification="Synthetic test cost",
                ),
            )
            for index, (row, tier) in enumerate(zip(case.rows, case.costs, strict=True))
        ]
    )
    matrix = CoverageMatrix(path_set, catalog, graph)
    matrix.verify_fingerprint(path_set, catalog)
    return matrix


@st.composite
def matrix_cases(
    draw: st.DrawFn,
    max_interventions: int = 12,
    *,
    min_interventions: int = 0,
    min_paths: int = 0,
    max_paths: int = 8,
    is_feasible: bool = False,
) -> CoverageCase:
    minimum_rows = max(min_interventions, int(is_feasible and min_paths > 0))
    row_count = draw(st.integers(minimum_rows, max_interventions))
    maximum_columns = 0 if is_feasible and row_count == 0 else max_paths
    column_count = draw(st.integers(min_paths, maximum_columns))
    rows = draw(
        st.lists(
            st.lists(st.booleans(), min_size=column_count, max_size=column_count),
            min_size=row_count,
            max_size=row_count,
        )
    )
    costs = draw(st.lists(st.sampled_from(list(CostTier)), min_size=row_count, max_size=row_count))
    weights = draw(st.lists(st.integers(1, 10), min_size=column_count, max_size=column_count))

    shapes = ["arbitrary", "all_ones"]
    if column_count and not is_feasible:
        shapes.append("zero_column")
    if row_count and (not is_feasible or row_count > 1):
        shapes.append("redundant")
    if row_count > 1:
        shapes.append("ties")
    shape = draw(st.sampled_from(shapes))

    match shape:
        case "all_ones":
            rows = [[True] * column_count for _ in rows]
        case "zero_column":
            column = draw(st.integers(0, column_count - 1))
            for row in rows:
                row[column] = False
        case "redundant" | "ties":
            rows[-1] = [False] * column_count

    # Reserve the last row when it must remain redundant or duplicate the first.
    repair_rows = row_count - int(shape in {"redundant", "ties"})
    if is_feasible:
        for column in range(column_count):
            if not any(row[column] for row in rows):
                rows[draw(st.integers(0, repair_rows - 1))][column] = True
    if shape == "ties":
        rows[-1] = rows[0].copy()
        costs[-1] = costs[0]

    return CoverageCase(rows=rows, costs=costs, weights=weights)


@st.composite
def generated_params(draw: st.DrawFn) -> GeneratorParams:
    depth = draw(st.integers(1, 3))
    minimum_weight = draw(st.integers(1, 10))
    return GeneratorParams(
        seed=draw(st.integers(0, 2**32 - 1)),
        n_entry_points=draw(st.integers(1, 3)),
        n_objectives=draw(st.integers(1, 3)),
        depth=depth,
        branching=draw(st.integers(1, 3)),
        n_planted_chokepoints=draw(st.integers(0, depth)),
        observed_edge_ratio=draw(st.sampled_from([0.0, 0.25, 1.0])),
        inferred_edge_ratio=draw(st.sampled_from([0.0, 0.25, 1.0])),
        objective_weight_range=(minimum_weight, draw(st.integers(minimum_weight, 10))),
    )
