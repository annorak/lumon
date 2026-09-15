"""Bounded bypass checks. Synthetic routes are separate from the Armadin fixtures."""

import hashlib
import json
import sys
from itertools import pairwise
from pathlib import Path as FilePath

import pytest
from pydantic import ValidationError

from lumon.coverage import CoverageMatrix, StaleMatrixError
from lumon.hypotheses.generate import generate_hypotheses
from lumon.interventions import synthesize
from lumon.io import assert_usable, load_graph
from lumon.model import AttackGraph, Edge, EdgeType, Evidence, Node, NodeType, Path, PathSet
from lumon.model.hypothesis import (
    BypassHypothesis,
    HypothesisQueue,
    SubstituteApplicability,
    hypothesis_statement,
)
from lumon.paths import extract_paths

PATCH_IDS = ["INT-003", "INT-004"]
EXPLOIT_IDS = ["x_obs_a", "x_obs_b", "x_inf"]
EXPECTED_PATCH_ROUTES = [
    ["e_entry", "x_obs_a", "e_hop", "e_finish"],
    ["e_entry", "x_obs_b", "e_hop", "e_finish"],
    ["e_entry", "x_obs_a", "e_direct"],
    ["e_entry", "x_obs_b", "e_direct"],
    ["e_entry", "x_inf", "e_hop", "e_finish"],
    ["e_entry", "x_inf", "e_direct"],
]


def _build_edge(
    edge_id: str,
    source: str,
    target: str,
    edge_type: EdgeType,
    evidence: Evidence,
    enabled_by: str | None = None,
) -> Edge:
    return Edge(
        id=edge_id,
        source=source,
        target=target,
        type=edge_type,
        evidence=evidence,
        enabled_by=enabled_by,
    )


@pytest.fixture
def graph() -> AttackGraph:
    return AttackGraph(
        nodes=[
            *[
                Node(id=node_id, label=node_id, type=NodeType.ENTRY_POINT)
                for node_id in ("n_entry", "n_entry_obs", "n_entry_inf")
            ],
            *[
                Node(id=node_id, label=node_id, type=NodeType.SERVICE)
                for node_id in ("n_service", "n_other_service")
            ],
            Node(id="n_identity", label="Synthetic identity", type=NodeType.IDENTITY),
            Node(id="n_hop", label="Synthetic hop", type=NodeType.ASSET),
            Node(id="n_objective", label="Synthetic objective", type=NodeType.OBJECTIVE, weight=10),
            *[
                Node(
                    id=f"n_v{index}",
                    label=f"Synthetic vulnerability {index}",
                    type=NodeType.VULNERABILITY,
                )
                for index in range(1, 6)
            ],
        ],
        edges=[
            _build_edge("e_entry", "n_entry", "n_service", EdgeType.REACHES, Evidence.VALIDATED),
            _build_edge(
                "e_exploit_a",
                "n_service",
                "n_identity",
                EdgeType.EXPLOITS,
                Evidence.VALIDATED,
                "n_v1",
            ),
            _build_edge(
                "e_exploit_b",
                "n_service",
                "n_identity",
                EdgeType.EXPLOITS,
                Evidence.VALIDATED,
                "n_v2",
            ),
            _build_edge(
                "e_direct", "n_identity", "n_objective", EdgeType.CAN_ACCESS, Evidence.VALIDATED
            ),
            _build_edge("e_hop", "n_identity", "n_hop", EdgeType.CAN_ACCESS, Evidence.VALIDATED),
            _build_edge("e_finish", "n_hop", "n_objective", EdgeType.REACHES, Evidence.VALIDATED),
            # An off-path v3 exploit makes a v3 patch available without adding a path.
            _build_edge(
                "e_other_v3",
                "n_other_service",
                "n_identity",
                EdgeType.EXPLOITS,
                Evidence.VALIDATED,
                "n_v3",
            ),
            _build_edge("r_obs", "n_entry_obs", "n_service", EdgeType.REACHES, Evidence.OBSERVED),
            _build_edge("r_inf", "n_entry_inf", "n_service", EdgeType.REACHES, Evidence.INFERRED),
            _build_edge(
                "x_obs_a", "n_service", "n_identity", EdgeType.EXPLOITS, Evidence.OBSERVED, "n_v3"
            ),
            _build_edge(
                "x_obs_b", "n_service", "n_identity", EdgeType.EXPLOITS, Evidence.OBSERVED, "n_v4"
            ),
            _build_edge(
                "x_inf", "n_service", "n_identity", EdgeType.EXPLOITS, Evidence.INFERRED, "n_v5"
            ),
        ],
    )


def _build_unblocked_records(
    selected_ids: list[str], substitute_ids: list[str]
) -> list[SubstituteApplicability]:
    return [
        SubstituteApplicability(
            intervention_id=selected_id,
            substitute_edge_id=substitute_id,
            is_blocked=False,
            justification=(
                f"Synthetic test assumption: {selected_id} leaves {substitute_id} unchanged."
            ),
        )
        for selected_id in selected_ids
        for substitute_id in substitute_ids
    ]


def _generate_queue(
    graph: AttackGraph,
    selected_ids: list[str],
    records: list[SubstituteApplicability],
    *,
    max_hypotheses: int = 20,
) -> HypothesisQueue:
    paths = extract_paths(graph)
    catalog = synthesize(graph)
    matrix = CoverageMatrix(paths, catalog, graph)
    return generate_hypotheses(
        graph, paths, catalog, matrix, selected_ids, records, max_hypotheses=max_hypotheses
    )


def _replace_edge(graph: AttackGraph, edge_id: str, **updates: object) -> AttackGraph:
    return AttackGraph(
        nodes=graph.nodes,
        edges=[
            Edge.model_validate({**edge.model_dump(), **updates}) if edge.id == edge_id else edge
            for edge in graph.edges
        ],
    )


def _set_objective_weight(graph: AttackGraph, weight: float) -> AttackGraph:
    return AttackGraph(
        nodes=[
            Node.model_validate({**node.model_dump(), "weight": weight})
            if node.type is NodeType.OBJECTIVE
            else node
            for node in graph.nodes
        ],
        edges=graph.edges,
    )


def test_synthetic_inputs_match_the_reviewed_paths_and_interventions(graph: AttackGraph) -> None:
    assert_usable(graph)
    paths = extract_paths(graph)
    assert not paths.truncated
    assert [path.edge_ids for path in paths.paths] == [
        ["e_entry", "e_exploit_a", "e_direct"],
        ["e_entry", "e_exploit_b", "e_direct"],
        ["e_entry", "e_exploit_a", "e_hop", "e_finish"],
        ["e_entry", "e_exploit_b", "e_hop", "e_finish"],
    ]
    assert [(item.id, item.target_node_id) for item in synthesize(graph).interventions] == [
        ("INT-000", "n_objective"),
        ("INT-001", "n_service"),
        ("INT-002", "n_identity"),
        ("INT-003", "n_v1"),
        ("INT-004", "n_v2"),
        ("INT-005", "n_v3"),
    ]


def test_vulnerability_substitution_ranks_and_deduplicates_real_candidates(
    graph: AttackGraph,
) -> None:
    records = _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS)
    queue = _generate_queue(graph, PATCH_IDS, records)

    assert [item.candidate_edge_ids for item in queue.hypotheses] == EXPECTED_PATCH_ROUTES
    assert [item.original_path.id for item in queue.hypotheses] == [
        "p0002",
        "p0002",
        "p0000",
        "p0000",
        "p0002",
        "p0000",
    ]
    assert [item.ranking_score for item in queue.hypotheses] == pytest.approx(
        [7.5, 7.5, 20 / 3, 20 / 3, 7.5, 20 / 3], abs=1e-12, rel=0
    )
    assert [item.substitute_edge.evidence for item in queue.hypotheses] == [
        Evidence.OBSERVED,
        Evidence.OBSERVED,
        Evidence.OBSERVED,
        Evidence.OBSERVED,
        Evidence.INFERRED,
        Evidence.INFERRED,
    ]
    for item, route in zip(queue.hypotheses, EXPECTED_PATCH_ROUTES, strict=True):
        identity = ("vulnerability_substitution", "n_objective", route)
        encoded = json.dumps(identity, separators=(",", ":")).encode("utf-8")
        assert item.id == f"HYP-{hashlib.sha256(encoded).hexdigest()}"
        assert item.rule == "vulnerability_substitution"
        assert item.replaced_edge_id == "e_exploit_a"
        assert item.substitute_edge == graph.edge_by_id(item.substitute_edge.id)
        assert item.assumptions[1:-1] == [
            f"{record.intervention_id} is modeled not to block "
            f"{item.substitute_edge.id}: {record.justification}"
            for record in records
            if record.substitute_edge_id == item.substitute_edge.id
        ]
        for phrase in ("Hypothesis", "unvalidated", "Recommend validation", "side effects"):
            assert phrase in hypothesis_statement(item)
    assert HypothesisQueue.model_validate_json(queue.model_dump_json()) == queue


def test_entry_substitution_and_explicit_portfolio_binding(graph: AttackGraph) -> None:
    entry = _generate_queue(
        graph, ["INT-001"], _build_unblocked_records(["INT-001"], ["r_obs", "r_inf"])
    )
    patch = _generate_queue(graph, PATCH_IDS, _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS))

    assert [item.candidate_edge_ids for item in entry.hypotheses] == [
        [replacement, exploit, *suffix]
        for replacement in ("r_obs", "r_inf")
        for suffix in (["e_hop", "e_finish"], ["e_direct"])
        for exploit in ("e_exploit_a", "e_exploit_b")
    ]
    assert all(
        item.rule == "entry_substitution" and item.replaced_edge_id == "e_entry"
        for item in entry.hypotheses
    )
    assert entry.matrix_fingerprint == patch.matrix_fingerprint
    assert entry.selected_intervention_ids == ["INT-001"]
    assert patch.selected_intervention_ids == PATCH_IDS


@pytest.mark.parametrize(
    ("selected_ids", "substitute_ids"),
    [(PATCH_IDS, EXPLOIT_IDS), (["INT-001"], ["r_obs", "r_inf"])],
)
def test_repeats_and_input_reordering_preserve_the_complete_queue(
    graph: AttackGraph, selected_ids: list[str], substitute_ids: list[str]
) -> None:
    records = _build_unblocked_records(selected_ids, substitute_ids)
    expected = _generate_queue(graph, selected_ids, records)
    reordered = AttackGraph(nodes=graph.nodes[::-1], edges=graph.edges[::-1])

    for _ in range(3):
        assert _generate_queue(graph, selected_ids, records) == expected
    assert _generate_queue(reordered, selected_ids[::-1], records[::-1]).model_dump_json() == (
        expected.model_dump_json()
    )


def test_evidence_changes_regenerate_the_queue_without_a_matrix_change(graph: AttackGraph) -> None:
    records = _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS)
    before = _generate_queue(graph, PATCH_IDS, records)
    changed = _replace_edge(graph, "x_obs_b", evidence=Evidence.INFERRED)
    after = _generate_queue(changed, PATCH_IDS, records)

    assert after != before
    assert after.matrix_fingerprint == before.matrix_fingerprint
    assert [item.substitute_edge.id for item in after.hypotheses] == [
        "x_obs_a",
        "x_obs_a",
        "x_inf",
        "x_obs_b",
        "x_inf",
        "x_obs_b",
    ]
    assert all(
        item.substitute_edge.evidence is Evidence.INFERRED
        for item in after.hypotheses
        if item.substitute_edge.id == "x_obs_b"
    )


def test_removing_a_substitute_removes_exactly_its_candidates(graph: AttackGraph) -> None:
    changed = AttackGraph(
        nodes=graph.nodes, edges=[edge for edge in graph.edges if edge.id != "x_obs_a"]
    )
    queue = _generate_queue(
        changed, PATCH_IDS, _build_unblocked_records(PATCH_IDS, ["x_obs_b", "x_inf"])
    )

    assert [item.candidate_edge_ids for item in queue.hypotheses] == [
        route for route in EXPECTED_PATCH_ROUTES if "x_obs_a" not in route
    ]


def test_another_selected_fix_can_cut_all_or_only_some_retained_suffixes(
    graph: AttackGraph,
) -> None:
    records = _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS)
    # The retained suffix is already cut, so substitute applicability is unnecessary.
    assert _generate_queue(graph, [*PATCH_IDS, "INT-002"], records).hypotheses == []
    selected = [*PATCH_IDS, "INT-000"]
    partial = _generate_queue(graph, selected, _build_unblocked_records(selected, EXPLOIT_IDS))
    assert [item.candidate_edge_ids for item in partial.hypotheses] == [
        route for route in EXPECTED_PATCH_ROUTES if len(route) == 3
    ]


def test_a_selected_fix_can_block_the_substitute_through_reviewed_applicability(
    graph: AttackGraph,
) -> None:
    selected = [*PATCH_IDS, "INT-005"]
    records = [
        SubstituteApplicability.model_validate(
            {
                **record.model_dump(),
                "is_blocked": record.intervention_id == "INT-005"
                and record.substitute_edge_id == "x_obs_a",
                "justification": (
                    "Synthetic test: the v3 patch blocks x_obs_a only."
                    if record.intervention_id == "INT-005"
                    else record.justification
                ),
            }
        )
        for record in _build_unblocked_records(selected, EXPLOIT_IDS)
    ]
    queue = _generate_queue(graph, selected, records)

    assert synthesize(graph).by_id()["INT-005"].removes_edge_ids == {"e_other_v3"}
    assert [item.candidate_edge_ids for item in queue.hypotheses] == [
        route for route in EXPECTED_PATCH_ROUTES if "x_obs_a" not in route
    ]


def test_missing_applicability_is_an_error_not_an_unaffected_substitute(graph: AttackGraph) -> None:
    records = _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS)
    with pytest.raises(ValueError, match="review applicability of INT-003 to substitute 'x_obs_a'"):
        _generate_queue(graph, PATCH_IDS, records[1:])


@pytest.mark.parametrize(
    ("intervention_id", "substitute_id", "expected"),
    [
        ("missing", "x_obs_a", "unknown intervention"),
        ("INT-003", "missing", "observed or inferred"),
        ("INT-003", "e_exploit_a", "observed or inferred"),
    ],
)
def test_applicability_references_are_checked(
    graph: AttackGraph, intervention_id: str, substitute_id: str, expected: str
) -> None:
    with pytest.raises(ValueError, match=expected):
        _generate_queue(
            graph, PATCH_IDS, _build_unblocked_records([intervention_id], [substitute_id])
        )


def test_duplicate_applicability_and_unknown_selected_ids_are_rejected(graph: AttackGraph) -> None:
    records = _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS)
    with pytest.raises(ValueError, match="duplicate applicability"):
        _generate_queue(graph, PATCH_IDS, [*records, records[0]])
    with pytest.raises(ValueError, match="unknown selected intervention IDs: missing"):
        _generate_queue(graph, ["missing"], [])


@pytest.mark.parametrize(("limit", "is_truncated"), [(3, True), (6, False)])
def test_output_limit_applies_after_deduplication(
    graph: AttackGraph, limit: int, is_truncated: bool
) -> None:
    queue = _generate_queue(
        graph, PATCH_IDS, _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS), max_hypotheses=limit
    )
    assert [item.candidate_edge_ids for item in queue.hypotheses] == EXPECTED_PATCH_ROUTES[:limit]
    assert queue.max_hypotheses == limit
    assert queue.truncated is is_truncated


def test_validated_alternatives_require_path_analysis_not_hypotheses(graph: AttackGraph) -> None:
    original_paths = extract_paths(graph)
    promoted = _replace_edge(graph, "x_obs_a", evidence=Evidence.VALIDATED)
    catalog = synthesize(promoted)
    matrix = CoverageMatrix(original_paths, catalog, promoted)
    records = _build_unblocked_records(PATCH_IDS, ["x_obs_b", "x_inf"])

    with pytest.raises(ValueError, match="validated substitute 'x_obs_a' exposes a route absent"):
        generate_hypotheses(
            promoted, original_paths, catalog, matrix, PATCH_IDS, records, max_hypotheses=20
        )
    assert len(extract_paths(promoted).paths) == 6
    queue = _generate_queue(promoted, PATCH_IDS, records)
    assert queue.hypotheses
    assert all(item.substitute_edge.evidence is not Evidence.VALIDATED for item in queue.hypotheses)


@pytest.mark.parametrize(
    "updates",
    [
        {"enabled_by": None},
        {"enabled_by": "n_identity"},
        {"source": "n_other_service"},
        {"target": "n_hop"},
    ],
)
def test_unsupported_exploit_substitutions_are_excluded(
    graph: AttackGraph, updates: dict[str, object]
) -> None:
    changed = _replace_edge(graph, "x_obs_a", **updates)
    queue = _generate_queue(changed, PATCH_IDS, _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS))
    assert [item.candidate_edge_ids for item in queue.hypotheses] == [
        route for route in EXPECTED_PATCH_ROUTES if "x_obs_a" not in route
    ]


@pytest.mark.parametrize(
    "updates", [{"source": "n_identity"}, {"source": "n_entry"}, {"target": "n_hop"}]
)
def test_unsupported_entry_substitutions_are_excluded(
    graph: AttackGraph, updates: dict[str, object]
) -> None:
    queue = _generate_queue(
        _replace_edge(graph, "r_obs", **updates),
        ["INT-001"],
        _build_unblocked_records(["INT-001"], ["r_obs", "r_inf"]),
    )
    assert [item.substitute_edge.id for item in queue.hypotheses] == ["r_inf"] * 4


def test_an_entry_substitution_cannot_repeat_a_node(graph: AttackGraph) -> None:
    changed = AttackGraph(
        nodes=graph.nodes,
        edges=[
            *graph.edges,
            _build_edge(
                "e_entry_obs_hop",
                "n_identity",
                "n_entry_obs",
                EdgeType.CAN_ACCESS,
                Evidence.VALIDATED,
            ),
            _build_edge(
                "e_entry_obs_finish",
                "n_entry_obs",
                "n_objective",
                EdgeType.REACHES,
                Evidence.VALIDATED,
            ),
        ],
    )
    queue = _generate_queue(
        changed, ["INT-001"], _build_unblocked_records(["INT-001"], ["r_obs", "r_inf"])
    )

    assert len(queue.hypotheses) == 10
    assert any(
        item.substitute_edge.id == "r_inf" and "e_entry_obs_hop" in item.candidate_edge_ids
        for item in queue.hypotheses
    )
    for item in queue.hypotheses:
        route = [changed.edge_by_id(edge_id) for edge_id in item.candidate_edge_ids]
        nodes = [route[0].source, *[edge.target for edge in route]]
        assert len(set(nodes)) == len(nodes)
        assert all(left.target == right.source for left, right in pairwise(route))


def test_empty_selection_no_substitutes_and_no_supplied_paths(graph: AttackGraph) -> None:
    assert _generate_queue(graph, [], []).hypotheses == []
    validated_only = AttackGraph(nodes=graph.nodes, edges=graph.validated_edges())
    assert _generate_queue(validated_only, PATCH_IDS, []).hypotheses == []
    paths = PathSet(paths=[], truncated=False)
    catalog = synthesize(graph)
    queue = generate_hypotheses(
        graph,
        paths,
        catalog,
        CoverageMatrix(paths, catalog, graph),
        PATCH_IDS,
        [],
        max_hypotheses=20,
    )
    assert queue.hypotheses == []
    assert not queue.truncated


def test_fortune600_has_no_supplied_substitutes() -> None:
    graph = load_graph(
        FilePath(__file__).resolve().parents[2] / "fixtures/armadin/graphs/episode4-fortune600.json"
    )
    queue = _generate_queue(graph, ["INT-003"], [])
    assert queue.selected_intervention_ids == ["INT-003"]
    assert queue.hypotheses == []
    assert not queue.truncated


def test_stale_matrix_is_rejected(graph: AttackGraph) -> None:
    paths = extract_paths(graph)
    catalog = synthesize(graph)
    matrix = CoverageMatrix(paths, catalog, graph)
    changed_paths = PathSet(paths=paths.paths[:-1], truncated=False)
    with pytest.raises(StaleMatrixError, match="coverage matrix no longer matches"):
        generate_hypotheses(graph, changed_paths, catalog, matrix, PATCH_IDS, [], max_hypotheses=20)


@pytest.mark.parametrize("edge_id", ["e_exploit_a", "e_other_v3"])
def test_current_graph_must_still_validate_path_and_removal_edges(
    graph: AttackGraph, edge_id: str
) -> None:
    paths = extract_paths(graph)
    catalog = synthesize(graph)
    matrix = CoverageMatrix(paths, catalog, graph)
    changed = _replace_edge(graph, edge_id, evidence=Evidence.OBSERVED)
    with pytest.raises(ValueError, match="non-validated or missing edges: " + edge_id):
        generate_hypotheses(changed, paths, catalog, matrix, PATCH_IDS, [], max_hypotheses=20)


def test_supplied_path_must_match_graph_continuity_and_weight(graph: AttackGraph) -> None:
    paths = extract_paths(graph)
    catalog = synthesize(graph)
    for updates in (
        {"node_ids": ["n_entry", "n_identity", "n_service", "n_objective"]},
        {"weight": 5},
    ):
        changed = Path.model_validate({**paths.paths[0].model_dump(), **updates})
        supplied = PathSet(paths=[changed, *paths.paths[1:]], truncated=False)
        matrix = CoverageMatrix(supplied, catalog, graph)
        with pytest.raises(ValueError, match="does not match a simple validated"):
            generate_hypotheses(graph, supplied, catalog, matrix, PATCH_IDS, [], max_hypotheses=20)


@pytest.fixture
def single_edge_graph(graph: AttackGraph) -> AttackGraph:
    return AttackGraph(
        nodes=[
            node
            for node in graph.nodes
            if node.id in {"n_entry", "n_objective", "n_v1", "n_v3", "n_v4"}
        ],
        edges=[
            _build_edge(
                "original", "n_entry", "n_objective", EdgeType.EXPLOITS, Evidence.VALIDATED, "n_v1"
            ),
            _build_edge(
                "z_alternate",
                "n_entry",
                "n_objective",
                EdgeType.EXPLOITS,
                Evidence.OBSERVED,
                "n_v3",
            ),
            _build_edge(
                "a_alternate",
                "n_entry",
                "n_objective",
                EdgeType.EXPLOITS,
                Evidence.OBSERVED,
                "n_v4",
            ),
        ],
    )


@pytest.mark.parametrize("weight", [10.0, sys.float_info.max])
def test_one_edge_candidates_have_zero_scores_and_stable_ties(
    single_edge_graph: AttackGraph, weight: float
) -> None:
    graph = _set_objective_weight(single_edge_graph, weight)
    records = _build_unblocked_records(["INT-000"], ["a_alternate", "z_alternate"])
    first = _generate_queue(graph, ["INT-000"], records)
    reversed_graph = AttackGraph(nodes=graph.nodes, edges=graph.edges[::-1])
    assert _generate_queue(reversed_graph, ["INT-000"], records) == first
    assert [item.substitute_edge.id for item in first.hypotheses] == ["a_alternate", "z_alternate"]
    assert [item.retained_fraction for item in first.hypotheses] == [0.0, 0.0]
    assert [item.ranking_score for item in first.hypotheses] == [0.0, 0.0]


def test_infinite_weights_are_rejected_before_ranking(single_edge_graph: AttackGraph) -> None:
    graph = _set_objective_weight(single_edge_graph, float("inf"))
    records = _build_unblocked_records(["INT-000"], ["a_alternate", "z_alternate"])
    for current in (graph, AttackGraph(nodes=graph.nodes, edges=graph.edges[::-1])):
        assert extract_paths(current).paths[0].weight == float("inf")
        with pytest.raises(
            ValueError, match="path 'p0000' needs a finite weight for bypass ranking"
        ):
            _generate_queue(current, ["INT-000"], records)


def test_same_vulnerability_is_not_a_substitution(single_edge_graph: AttackGraph) -> None:
    changed = _replace_edge(single_edge_graph, "a_alternate", enabled_by="n_v1")
    queue = _generate_queue(
        changed, ["INT-000"], _build_unblocked_records(["INT-000"], ["a_alternate", "z_alternate"])
    )
    assert [item.substitute_edge.id for item in queue.hypotheses] == ["z_alternate"]


def test_objective_weight_affects_ranking_score(graph: AttackGraph) -> None:
    records = _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS)
    original = _generate_queue(graph, PATCH_IDS, records)
    weighted = _generate_queue(_set_objective_weight(graph, 20), PATCH_IDS, records)
    assert [item.ranking_score for item in weighted.hypotheses] == [
        2 * item.ranking_score for item in original.hypotheses
    ]


@pytest.fixture
def hypothesis(graph: AttackGraph) -> BypassHypothesis:
    return _generate_queue(
        graph, PATCH_IDS, _build_unblocked_records(PATCH_IDS, EXPLOIT_IDS)
    ).hypotheses[0]


def test_hypothesis_model_rejects_validated_substitute_evidence(
    hypothesis: BypassHypothesis,
) -> None:
    fields = hypothesis.model_dump(mode="json")
    fields["substitute_edge"]["evidence"] = "validated"
    with pytest.raises(ValidationError, match="validated-path analysis"):
        BypassHypothesis.model_validate_json(json.dumps(fields))


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"assumptions": []}, "at least 1 item"),
        ({"assumptions": [""]}, "non-whitespace"),
        ({"assumptions": [" \n\t"]}, "non-whitespace"),
        ({"replaced_edge_id": "missing"}, "exactly once"),
        ({"rule": "credential_substitution"}, "Input should be"),
    ],
)
def test_hypothesis_model_requires_real_assumptions_and_a_supported_substitution(
    hypothesis: BypassHypothesis, updates: dict[str, object], expected: str
) -> None:
    with pytest.raises(ValidationError, match=expected):
        BypassHypothesis.model_validate({**hypothesis.model_dump(), **updates})


def test_hypothesis_model_rejects_a_repeated_replaced_edge(hypothesis: BypassHypothesis) -> None:
    fields = hypothesis.model_dump()
    fields["original_path"]["edge_ids"] = ["e_entry", "e_exploit_a", "e_exploit_a", "e_finish"]
    with pytest.raises(ValidationError, match="exactly once"):
        BypassHypothesis.model_validate(fields)


@pytest.mark.parametrize("justification", ["", " ", "\n\t"])
def test_applicability_requires_a_nonblank_justification(justification: str) -> None:
    with pytest.raises(ValidationError, match="justification"):
        SubstituteApplicability(
            intervention_id="INT-003",
            substitute_edge_id="x_obs_a",
            is_blocked=False,
            justification=justification,
        )


@pytest.mark.parametrize("limit", [0, -1])
def test_nonpositive_queue_limits_are_rejected(graph: AttackGraph, limit: int) -> None:
    with pytest.raises(ValueError, match="max_hypotheses"):
        _generate_queue(graph, [], [], max_hypotheses=limit)
    with pytest.raises(ValidationError, match="max_hypotheses"):
        HypothesisQueue(
            matrix_fingerprint="test",
            selected_intervention_ids=[],
            hypotheses=[],
            max_hypotheses=limit,
            truncated=False,
        )
