import pytest

from lumon.generate.generator import generate
from lumon.generate.presets import TINY
from lumon.interventions import DEFAULT_COSTS, synthesize
from lumon.io import GraphInvariantError
from lumon.model import (
    AttackGraph,
    CostSource,
    Edge,
    EdgeType,
    Evidence,
    Intervention,
    InterventionCatalog,
    InterventionClass,
    Node,
    NodeType,
)

ENTRY = Node(id="n_entry", type=NodeType.ENTRY_POINT, label="entry")
OBJECTIVE = Node(id="n_objective", type=NodeType.OBJECTIVE, label="objective", weight=10.0)


def _edge(
    edge_id: str,
    source: str,
    target: str,
    edge_type: EdgeType,
    *,
    evidence: Evidence = Evidence.VALIDATED,
    enabled_by: str | None = None,
    crosses_boundary: str | None = None,
) -> Edge:
    attributes = {} if crosses_boundary is None else {"crosses_boundary": crosses_boundary}
    return Edge(
        id=edge_id,
        source=source,
        target=target,
        type=edge_type,
        evidence=evidence,
        enabled_by=enabled_by,
        attributes=attributes,
    )


def _graph(edges: list[Edge], extra_nodes: list[Node]) -> AttackGraph:
    return AttackGraph(nodes=[ENTRY, OBJECTIVE, *extra_nodes], edges=edges)


def _only_intervention(
    catalog: InterventionCatalog, intervention_class: InterventionClass
) -> Intervention:
    matches = [
        intervention
        for intervention in catalog.interventions
        if intervention.intervention_class is intervention_class
    ]
    assert len(matches) == 1
    return matches[0]


def test_exploits_edges_group_into_one_patch_per_vulnerability() -> None:
    vulnerability = Node(id="n_vulnerability", type=NodeType.VULNERABILITY, label="CVE-TEST")
    service = Node(id="n_service", type=NodeType.SERVICE, label="service")
    graph = _graph(
        [
            _edge(
                "e_exploit_one",
                "n_entry",
                "n_objective",
                EdgeType.EXPLOITS,
                enabled_by="n_vulnerability",
            ),
            _edge(
                "e_exploit_two",
                "n_service",
                "n_objective",
                EdgeType.EXPLOITS,
                enabled_by="n_vulnerability",
            ),
        ],
        [vulnerability, service],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.VULNERABILITY_PATCH)

    assert intervention.target_node_id == "n_vulnerability"
    assert intervention.removes_edge_ids == frozenset({"e_exploit_one", "e_exploit_two"})


def test_reaches_edges_group_into_one_access_control_change_per_target() -> None:
    service = Node(id="n_service", type=NodeType.SERVICE, label="service")
    identity = Node(id="n_identity", type=NodeType.IDENTITY, label="identity")
    graph = _graph(
        [
            _edge("e_reach_one", "n_entry", "n_service", EdgeType.REACHES),
            _edge("e_reach_two", "n_identity", "n_service", EdgeType.REACHES),
        ],
        [service, identity],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.ACCESS_CONTROL_ADD)

    assert intervention.target_node_id == "n_service"
    assert intervention.removes_edge_ids == frozenset({"e_reach_one", "e_reach_two"})


def test_explicit_boundary_crossings_group_into_one_segmentation_change() -> None:
    boundary = Node(id="n_boundary", type=NodeType.BOUNDARY, label="trust boundary")
    service = Node(id="n_service", type=NodeType.SERVICE, label="service")
    graph = _graph(
        [
            _edge(
                "e_cross_one",
                "n_entry",
                "n_service",
                EdgeType.REACHES,
                crosses_boundary="n_boundary",
            ),
            _edge(
                "e_cross_two",
                "n_service",
                "n_objective",
                EdgeType.REACHES,
                crosses_boundary="n_boundary",
            ),
        ],
        [boundary, service],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.NETWORK_SEGMENTATION)

    assert intervention.target_node_id == "n_boundary"
    assert intervention.removes_edge_ids == frozenset({"e_cross_one", "e_cross_two"})


def test_reaching_a_boundary_does_not_mean_crossing_it() -> None:
    boundary = Node(id="n_boundary", type=NodeType.BOUNDARY, label="OT boundary")
    graph = _graph(
        [_edge("e_reach_boundary", "n_entry", "n_boundary", EdgeType.REACHES)],
        [boundary],
    )

    catalog = synthesize(graph)

    assert all(
        intervention.intervention_class is not InterventionClass.NETWORK_SEGMENTATION
        for intervention in catalog.interventions
    )


def test_wrong_type_crossing_does_not_generate_segmentation() -> None:
    service = Node(id="n_service", type=NodeType.SERVICE, label="service")
    graph = _graph(
        [
            _edge(
                "e_reach",
                "n_entry",
                "n_objective",
                EdgeType.REACHES,
                crosses_boundary="n_service",
            )
        ],
        [service],
    )

    catalog = synthesize(graph)

    assert all(
        intervention.intervention_class is not InterventionClass.NETWORK_SEGMENTATION
        for intervention in catalog.interventions
    )


def test_can_access_edges_group_into_one_permission_reduction_per_identity() -> None:
    identity = Node(id="n_identity", type=NodeType.IDENTITY, label="identity")
    service = Node(id="n_service", type=NodeType.SERVICE, label="service")
    graph = _graph(
        [
            _edge("e_access_one", "n_identity", "n_service", EdgeType.CAN_ACCESS),
            _edge("e_access_two", "n_identity", "n_objective", EdgeType.CAN_ACCESS),
        ],
        [identity, service],
    )

    intervention = _only_intervention(
        synthesize(graph), InterventionClass.IDENTITY_PERMISSION_REDUCTION
    )

    assert intervention.target_node_id == "n_identity"
    assert intervention.removes_edge_ids == frozenset({"e_access_one", "e_access_two"})


def test_reads_edge_synthesizes_credential_removal() -> None:
    credential = Node(id="n_credential", type=NodeType.CREDENTIAL, label="cleartext credential")
    graph = _graph(
        [_edge("e_read", "n_entry", "n_credential", EdgeType.READS)],
        [credential],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.CREDENTIAL_REMOVAL)

    assert intervention.target_node_id == "n_credential"
    assert intervention.removes_edge_ids == frozenset({"e_read"})


def test_authenticates_as_edge_synthesizes_credential_removal() -> None:
    credential = Node(id="n_credential", type=NodeType.CREDENTIAL, label="cleartext credential")
    graph = _graph(
        [
            _edge(
                "e_authenticate",
                "n_credential",
                "n_objective",
                EdgeType.AUTHENTICATES_AS,
            )
        ],
        [credential],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.CREDENTIAL_REMOVAL)

    assert intervention.target_node_id == "n_credential"
    assert intervention.removes_edge_ids == frozenset({"e_authenticate"})


def test_credential_rules_deduplicate_and_remove_both_halves() -> None:
    credential = Node(id="n_credential", type=NodeType.CREDENTIAL, label="cleartext credential")
    graph = _graph(
        [
            _edge("e_read", "n_entry", "n_credential", EdgeType.READS),
            _edge(
                "e_authenticate",
                "n_credential",
                "n_objective",
                EdgeType.AUTHENTICATES_AS,
            ),
        ],
        [credential],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.CREDENTIAL_REMOVAL)

    assert intervention.removes_edge_ids == frozenset({"e_read", "e_authenticate"})


def test_escapes_edges_group_into_one_hardening_change_per_source() -> None:
    workload = Node(id="n_workload", type=NodeType.ASSET, label="workload")
    service = Node(id="n_service", type=NodeType.SERVICE, label="service")
    graph = _graph(
        [
            _edge("e_escape_one", "n_workload", "n_service", EdgeType.ESCAPES),
            _edge("e_escape_two", "n_workload", "n_objective", EdgeType.ESCAPES),
        ],
        [workload, service],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.CONTAINER_HARDENING)

    assert intervention.target_node_id == "n_workload"
    assert intervention.removes_edge_ids == frozenset({"e_escape_one", "e_escape_two"})


def test_executes_as_edges_group_into_one_rebind_per_workload() -> None:
    workload = Node(id="n_workload", type=NodeType.ASSET, label="workload")
    identities = [
        Node(id="n_identity_one", type=NodeType.IDENTITY, label="first identity"),
        Node(id="n_identity_two", type=NodeType.IDENTITY, label="second identity"),
    ]
    graph = _graph(
        [
            _edge("e_execute_one", "n_workload", "n_identity_one", EdgeType.EXECUTES_AS),
            _edge("e_execute_two", "n_workload", "n_identity_two", EdgeType.EXECUTES_AS),
        ],
        [workload, *identities],
    )

    intervention = _only_intervention(synthesize(graph), InterventionClass.EXECUTION_CONTEXT_REBIND)

    assert intervention.target_node_id == "n_workload"
    assert intervention.removes_edge_ids == frozenset({"e_execute_one", "e_execute_two"})


def test_non_validated_edges_never_influence_the_catalog() -> None:
    graph = _graph(
        [
            _edge("e_validated", "n_entry", "n_objective", EdgeType.REACHES),
            _edge(
                "e_observed",
                "n_entry",
                "n_objective",
                EdgeType.REACHES,
                evidence=Evidence.OBSERVED,
            ),
            _edge(
                "e_inferred",
                "n_entry",
                "n_objective",
                EdgeType.REACHES,
                evidence=Evidence.INFERRED,
            ),
        ],
        [],
    )

    removed = {
        edge_id
        for intervention in synthesize(graph).interventions
        for edge_id in intervention.removes_edge_ids
    }

    assert removed == {"e_validated"}


def test_synthesis_fails_when_validated_exploit_has_no_enabler() -> None:
    graph = _graph([_edge("e_exploit", "n_entry", "n_objective", EdgeType.EXPLOITS)], [])

    with pytest.raises(GraphInvariantError, match="EXPLOITS_WITHOUT_ENABLED_BY"):
        synthesize(graph)


def test_synthesis_fails_when_exploit_enabler_is_not_a_vulnerability() -> None:
    credential = Node(id="n_credential", type=NodeType.CREDENTIAL, label="credential")
    graph = _graph(
        [
            _edge(
                "e_exploit",
                "n_entry",
                "n_objective",
                EdgeType.EXPLOITS,
                enabled_by="n_credential",
            )
        ],
        [credential],
    )

    with pytest.raises(GraphInvariantError, match="EXPLOITS_ENABLED_BY_NON_VULNERABILITY"):
        synthesize(graph)


def test_synthesis_is_deterministic_and_ids_start_at_zero() -> None:
    service = Node(id="n_service", type=NodeType.SERVICE, label="service")
    edges = [
        _edge("e_to_objective", "n_entry", "n_objective", EdgeType.REACHES),
        _edge("e_to_service", "n_entry", "n_service", EdgeType.REACHES),
    ]

    first = synthesize(_graph(edges, [service]))
    second = synthesize(_graph(list(reversed(edges)), [service]))

    assert first.model_dump_json() == second.model_dump_json()
    assert [item.id for item in first.interventions] == [
        f"INT-{index:03d}" for index in range(len(first.interventions))
    ]
    assert first.interventions[0].id == "INT-000"


def test_every_synthesized_cost_comes_from_the_default_table() -> None:
    graph, _ = generate(TINY)

    catalog = synthesize(graph)

    assert catalog.interventions
    for intervention in catalog.interventions:
        assert intervention.cost == DEFAULT_COSTS[intervention.intervention_class]
        assert intervention.cost.source is CostSource.ASSUMED_DEFAULT
        assert intervention.cost.justification.strip()


def test_every_validated_generated_edge_has_a_candidate_change() -> None:
    graph, _ = generate(TINY)

    catalog = synthesize(graph)
    removed = {
        edge_id
        for intervention in catalog.interventions
        for edge_id in intervention.removes_edge_ids
    }

    assert {edge.id for edge in graph.validated_edges()} <= removed
