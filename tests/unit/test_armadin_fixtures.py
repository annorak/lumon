import json
from pathlib import Path
from typing import Any

import pytest

from lumon.interventions import synthesize
from lumon.io import check_invariants, load_graph
from lumon.model import AttackGraph, CostSource, Evidence, InterventionCatalog
from lumon.paths import extract_paths

ARMADIN_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "armadin"
EXPECTED_EDGE_IDS = [
    "e_public_reach",
    "e_ssrf",
    "e_cve_execution",
    "e_credential_read",
    "e_cloud_authentication",
]
EPISODE1_EDGE_IDS = ["e_sql_injection", "e_database_command"]
EPISODE2_EDGE_IDS = ["e_authentication_bypass", "e_sql_to_host_execution"]
EPISODE3_BMS_EDGE_IDS = ["e_printnightmare", "e_credential_read", "e_bms_login"]


def _describe_catalog(catalog: InterventionCatalog) -> list[dict[str, object]]:
    return [
        {
            "id": item.id,
            "class": item.intervention_class.value,
            "target": item.target_node_id,
            "edges": sorted(item.removes_edge_ids),
            "cost": item.cost.tier.numeric_value,
        }
        for item in catalog.interventions
    ]


@pytest.fixture
def fortune600_graph() -> AttackGraph:
    return load_graph(ARMADIN_DIR / "graphs" / "episode4-fortune600.json")


def test_fortune600_graph_is_usable_and_contains_only_reviewed_transitions(
    fortune600_graph: AttackGraph,
) -> None:
    assert check_invariants(fortune600_graph).violations == []
    assert len(fortune600_graph.nodes) == 8
    assert {edge.id: edge.evidence for edge in fortune600_graph.edges} == dict.fromkeys(
        EXPECTED_EDGE_IDS, Evidence.VALIDATED
    )


def test_fortune600_extracts_exactly_the_reviewed_route(fortune600_graph: AttackGraph) -> None:
    paths = extract_paths(fortune600_graph)

    assert paths.model_dump() == {
        "graph_id": "armadin-kcc-episode4-fortune600",
        "truncated": False,
        "truncation_reason": None,
        "paths": [
            {
                "id": "p0000",
                "edge_ids": EXPECTED_EDGE_IDS,
                "node_ids": [
                    "n_internet",
                    "n_public_endpoint",
                    "n_internal_service",
                    "n_execution_identity",
                    "n_credential_material",
                    "n_cloud_compromise",
                ],
                "entry_id": "n_internet",
                "objective_id": "n_cloud_compromise",
                "weight": 10.0,
            }
        ],
    }
    assert paths.total_weight == 10.0


def test_fortune600_catalog_matches_approved_effects_and_costs(
    fortune600_graph: AttackGraph,
) -> None:
    catalog = synthesize(fortune600_graph)

    assert _describe_catalog(catalog) == [
        {
            "id": "INT-000",
            "class": "access_control_add",
            "target": "n_public_endpoint",
            "edges": ["e_public_reach"],
            "cost": 1.0,
        },
        {
            "id": "INT-001",
            "class": "credential_removal",
            "target": "n_credential_material",
            "edges": ["e_cloud_authentication", "e_credential_read"],
            "cost": 3.0,
        },
        {
            "id": "INT-002",
            "class": "vulnerability_patch",
            "target": "n_published_cve",
            "edges": ["e_cve_execution"],
            "cost": 1.0,
        },
        {
            "id": "INT-003",
            "class": "vulnerability_patch",
            "target": "n_ssrf",
            "edges": ["e_ssrf"],
            "cost": 1.0,
        },
    ]
    assert {item.cost.source for item in catalog.interventions} == {CostSource.ASSUMED_DEFAULT}


def _read_and_check_provenance(fixture_name: str, graph: AttackGraph) -> dict[str, Any]:
    provenance: dict[str, Any] = json.loads(
        (ARMADIN_DIR / "provenance" / f"{fixture_name}.json").read_text(encoding="utf-8")
    )
    excerpts = (ARMADIN_DIR / "sources" / provenance["source"]["excerpts_file"]).read_text(
        encoding="utf-8"
    )

    assert provenance["graph_id"] == graph.metadata["graph_id"]
    assert graph.metadata["source_url"] == provenance["source"]["url"]
    records = provenance["evidence"]
    evidence_by_id = {record["id"]: record for record in records}
    assert len(evidence_by_id) == len(records)
    for record in records:
        assert record["location"].strip()
        assert record["quotation"].strip()
        assert record["quotation"] in excerpts

    assert {node_id for record in records for node_id in record["node_ids"]} == {
        node.id for node in graph.nodes
    }
    assert {edge_id for record in records for edge_id in record["edge_ids"]} == {
        edge.id for edge in graph.edges
    }
    for path in provenance["validated_paths"]:
        supported_edges = {
            edge_id
            for evidence_id in path["evidence_ids"]
            for edge_id in evidence_by_id[evidence_id]["edge_ids"]
        }
        assert set(path["edge_ids"]) <= supported_edges
    for record in (provenance["findings"], provenance["customer_remediation"]):
        assert set(record["evidence_ids"]) <= evidence_by_id.keys()
    return provenance


def test_fortune600_provenance_covers_graph_and_matches_approved_excerpts(
    fortune600_graph: AttackGraph,
) -> None:
    provenance = _read_and_check_provenance("episode4-fortune600", fortune600_graph)

    assert provenance["source"] == {
        "publication": "Armadin, Kill Chains and Coffee, episode 4",
        "url": "https://www.youtube.com/watch?v=RxLj-4BsYhg",
        "excerpts_file": "episode4-excerpts.txt",
    }
    assert provenance["validated_paths"] == [
        {
            "edge_ids": EXPECTED_EDGE_IDS,
            "evidence_ids": [
                "case",
                "public-entry",
                "exploitation",
                "internal-service",
                "credential-read",
                "cloud-authentication",
            ],
        }
    ]
    assert provenance["findings"] == {
        "count": 12,
        "description": "Source-reported unauthenticated RCE findings",
        "evidence_ids": ["public-entry"],
    }
    assert provenance["customer_remediation"] == {
        "reported_outcome": "The podcast reports that all 12 RCE findings were remediated.",
        "evidence_ids": ["remediation"],
        "details_status": "not_reported",
    }
    for record in (provenance["findings"], provenance["customer_remediation"]):
        assert record["evidence_ids"]


@pytest.fixture
def episode1_graph() -> AttackGraph:
    return load_graph(ARMADIN_DIR / "graphs" / "episode1-post-login.json")


def test_episode1_graph_contains_only_reviewed_post_login_transitions(
    episode1_graph: AttackGraph,
) -> None:
    assert check_invariants(episode1_graph).violations == []
    assert {node.id: node.type.value for node in episode1_graph.nodes} == {
        "n_post_login_access": "entry_point",
        "n_sql_injection": "vulnerability",
        "n_database_identity": "identity",
        "n_database_host_rce": "objective",
    }
    assert {edge.id: edge.evidence for edge in episode1_graph.edges} == dict.fromkeys(
        EPISODE1_EDGE_IDS, Evidence.VALIDATED
    )


def test_episode1_extracts_exactly_the_reviewed_post_login_route(
    episode1_graph: AttackGraph,
) -> None:
    paths = extract_paths(episode1_graph)

    assert paths.model_dump() == {
        "graph_id": "armadin-kcc-episode1-post-login",
        "truncated": False,
        "truncation_reason": None,
        "paths": [
            {
                "id": "p0000",
                "edge_ids": EPISODE1_EDGE_IDS,
                "node_ids": [
                    "n_post_login_access",
                    "n_database_identity",
                    "n_database_host_rce",
                ],
                "entry_id": "n_post_login_access",
                "objective_id": "n_database_host_rce",
                "weight": 5.0,
            }
        ],
    }
    assert paths.total_weight == 5.0


def test_episode1_catalog_matches_approved_effects_and_costs(
    episode1_graph: AttackGraph,
) -> None:
    catalog = synthesize(episode1_graph)

    assert _describe_catalog(catalog) == [
        {
            "id": "INT-000",
            "class": "identity_permission_reduction",
            "target": "n_database_identity",
            "edges": ["e_database_command"],
            "cost": 3.0,
        },
        {
            "id": "INT-001",
            "class": "vulnerability_patch",
            "target": "n_sql_injection",
            "edges": ["e_sql_injection"],
            "cost": 1.0,
        },
    ]
    assert {item.cost.source for item in catalog.interventions} == {CostSource.ASSUMED_DEFAULT}


def test_episode1_provenance_covers_graph_and_matches_approved_excerpts(
    episode1_graph: AttackGraph,
) -> None:
    provenance = _read_and_check_provenance("episode1-post-login", episode1_graph)

    assert provenance["source"] == {
        "publication": "Armadin, Kill Chains and Coffee, episode 1",
        "url": "https://www.youtube.com/watch?v=6H07KzPNT2w",
        "excerpts_file": "episode1-excerpts.txt",
    }
    assert provenance["validated_paths"] == [
        {
            "edge_ids": EPISODE1_EDGE_IDS,
            "evidence_ids": [
                "starting-access",
                "sql-injection",
                "database-access",
                "host-execution",
            ],
        }
    ]
    assert provenance["findings"] == {
        "count": None,
        "description": "No total finding count reported in the supplied source",
        "evidence_ids": [],
    }
    assert provenance["customer_remediation"] == {
        "reported_outcome": None,
        "evidence_ids": [],
        "details_status": "not_reported",
    }


@pytest.fixture
def episode2_graph() -> AttackGraph:
    return load_graph(ARMADIN_DIR / "graphs" / "episode2-auction.json")


def test_episode2_graph_preserves_the_reviewed_abbreviation(episode2_graph: AttackGraph) -> None:
    assert check_invariants(episode2_graph).violations == []
    assert {node.id: node.type.value for node in episode2_graph.nodes} == {
        "n_internet": "entry_point",
        "n_authentication_bug": "vulnerability",
        "n_bid_websocket": "service",
        "n_sql_injection": "vulnerability",
        "n_server_rce": "objective",
    }
    assert {edge.id: edge.evidence for edge in episode2_graph.edges} == dict.fromkeys(
        EPISODE2_EDGE_IDS, Evidence.VALIDATED
    )
    assert episode2_graph.edge_by_id("e_sql_to_host_execution").attributes["operation"] == (
        "Create a privileged account through SQL injection, log in, "
        "upload a Joomla plugin, and execute PHP shell_exec"
    )


def test_episode2_extracts_exactly_the_reviewed_route(episode2_graph: AttackGraph) -> None:
    paths = extract_paths(episode2_graph)

    assert paths.model_dump() == {
        "graph_id": "armadin-kcc-episode2-auction",
        "truncated": False,
        "truncation_reason": None,
        "paths": [
            {
                "id": "p0000",
                "edge_ids": EPISODE2_EDGE_IDS,
                "node_ids": ["n_internet", "n_bid_websocket", "n_server_rce"],
                "entry_id": "n_internet",
                "objective_id": "n_server_rce",
                "weight": 5.0,
            }
        ],
    }
    assert paths.total_weight == 5.0


def test_episode2_catalog_contains_only_the_approved_patches(
    episode2_graph: AttackGraph,
) -> None:
    catalog = synthesize(episode2_graph)

    assert _describe_catalog(catalog) == [
        {
            "id": "INT-000",
            "class": "vulnerability_patch",
            "target": "n_authentication_bug",
            "edges": ["e_authentication_bypass"],
            "cost": 1.0,
        },
        {
            "id": "INT-001",
            "class": "vulnerability_patch",
            "target": "n_sql_injection",
            "edges": ["e_sql_to_host_execution"],
            "cost": 1.0,
        },
    ]
    assert {item.cost.source for item in catalog.interventions} == {CostSource.ASSUMED_DEFAULT}


def test_episode2_provenance_covers_graph_and_matches_approved_excerpts(
    episode2_graph: AttackGraph,
) -> None:
    provenance = _read_and_check_provenance("episode2-auction", episode2_graph)

    assert provenance["source"] == {
        "publication": "Armadin, Kill Chains and Coffee, episode 2",
        "url": "https://www.youtube.com/watch?v=KPLQmX_dqNM",
        "excerpts_file": "episode2-excerpts.txt",
    }
    assert provenance["validated_paths"] == [
        {
            "edge_ids": EPISODE2_EDGE_IDS,
            "evidence_ids": [
                "source-disclosure",
                "authentication-bypass",
                "account-creation",
                "plugin-execution",
            ],
        }
    ]
    assert provenance["findings"] == {
        "count": None,
        "description": "No total finding count reported in the supplied source",
        "evidence_ids": [],
    }
    assert provenance["customer_remediation"] == {
        "reported_outcome": None,
        "evidence_ids": [],
        "details_status": "not_reported",
    }


@pytest.fixture
def episode3_bms_graph() -> AttackGraph:
    return load_graph(ARMADIN_DIR / "graphs" / "episode3-building-management.json")


def test_episode3_bms_graph_preserves_the_reviewed_scope(episode3_bms_graph: AttackGraph) -> None:
    assert check_invariants(episode3_bms_graph).violations == []
    assert {node.id: node.type.value for node in episode3_bms_graph.nodes} == {
        "n_corporate_foothold": "entry_point",
        "n_printnightmare": "vulnerability",
        "n_windows_server": "asset",
        "n_bms_operator_credential": "credential",
        "n_bms_console_access": "objective",
    }
    assert {edge.id: edge.evidence for edge in episode3_bms_graph.edges} == dict.fromkeys(
        EPISODE3_BMS_EDGE_IDS, Evidence.VALIDATED
    )
    assert episode3_bms_graph.edge_by_id("e_printnightmare").attributes["operation"] == (
        "Exploit PrintNightmare to load a DLL as SYSTEM and create local administrator access"
    )
    assert episode3_bms_graph.edge_by_id("e_credential_read").attributes["operation"] == (
        "Read plaintext operator credentials from the server's local Desigo BMS database"
    )


def test_episode3_bms_extracts_exactly_the_reviewed_route(episode3_bms_graph: AttackGraph) -> None:
    paths = extract_paths(episode3_bms_graph)

    assert paths.model_dump() == {
        "graph_id": "armadin-kcc-episode3-building-management",
        "truncated": False,
        "truncation_reason": None,
        "paths": [
            {
                "id": "p0000",
                "edge_ids": EPISODE3_BMS_EDGE_IDS,
                "node_ids": [
                    "n_corporate_foothold",
                    "n_windows_server",
                    "n_bms_operator_credential",
                    "n_bms_console_access",
                ],
                "entry_id": "n_corporate_foothold",
                "objective_id": "n_bms_console_access",
                "weight": 5.0,
            }
        ],
    }
    assert paths.total_weight == 5.0


def test_episode3_bms_catalog_matches_approved_effects_and_costs(
    episode3_bms_graph: AttackGraph,
) -> None:
    catalog = synthesize(episode3_bms_graph)

    assert _describe_catalog(catalog) == [
        {
            "id": "INT-000",
            "class": "credential_removal",
            "target": "n_bms_operator_credential",
            "edges": ["e_bms_login", "e_credential_read"],
            "cost": 3.0,
        },
        {
            "id": "INT-001",
            "class": "vulnerability_patch",
            "target": "n_printnightmare",
            "edges": ["e_printnightmare"],
            "cost": 1.0,
        },
    ]
    assert {item.cost.source for item in catalog.interventions} == {CostSource.ASSUMED_DEFAULT}


def test_episode3_bms_provenance_preserves_the_route_and_separate_dead_end(
    episode3_bms_graph: AttackGraph,
) -> None:
    provenance = _read_and_check_provenance("episode3-building-management", episode3_bms_graph)

    assert provenance["source"] == {
        "publication": "Armadin, Kill Chains and Coffee, episode 3, building-management chain",
        "url": "https://www.youtube.com/watch?v=EIXWUWXRlXs",
        "excerpts_file": "episode3-building-management-excerpts.txt",
    }
    assert provenance["validated_paths"] == [
        {
            "edge_ids": EPISODE3_BMS_EDGE_IDS,
            "evidence_ids": [
                "assumed-breach",
                "contractor-foothold",
                "host-exploitation",
                "printnightmare-cve",
                "system-execution",
                "local-credentials",
                "desigo-database",
                "bms-login",
            ],
        }
    ]
    dead_end = next(
        record for record in provenance["evidence"] if record["id"] == "service-account-dead-end"
    )
    assert dead_end["node_ids"] == []
    assert dead_end["edge_ids"] == []
    assert provenance["findings"] == {
        "count": None,
        "description": "No total finding count reported for the building-management chain",
        "evidence_ids": [],
    }
    assert provenance["customer_remediation"] == {
        "reported_outcome": None,
        "evidence_ids": [],
        "details_status": "not_reported",
    }


@pytest.fixture
def episode5_graph() -> AttackGraph:
    return load_graph(ARMADIN_DIR / "graphs" / "episode5-post-registration.json")


def test_episode5_graph_contains_only_the_reviewed_partial_route(
    episode5_graph: AttackGraph,
) -> None:
    assert check_invariants(episode5_graph).violations == []
    assert {node.id: node.type.value for node in episode5_graph.nodes} == {
        "n_authenticated_app_access": "entry_point",
        "n_sql_injection": "vulnerability",
        "n_sql_query_execution": "objective",
    }
    assert {edge.id: edge.evidence for edge in episode5_graph.edges} == {
        "e_sql_injection": Evidence.VALIDATED
    }


def test_episode5_extracts_one_post_registration_sql_route(episode5_graph: AttackGraph) -> None:
    paths = extract_paths(episode5_graph)

    assert paths.model_dump() == {
        "graph_id": "armadin-kcc-episode5-post-registration",
        "truncated": False,
        "truncation_reason": None,
        "paths": [
            {
                "id": "p0000",
                "edge_ids": ["e_sql_injection"],
                "node_ids": ["n_authenticated_app_access", "n_sql_query_execution"],
                "entry_id": "n_authenticated_app_access",
                "objective_id": "n_sql_query_execution",
                "weight": 5.0,
            }
        ],
    }
    assert paths.total_weight == 5.0


def test_episode5_catalog_contains_only_the_represented_sql_patch(
    episode5_graph: AttackGraph,
) -> None:
    catalog = synthesize(episode5_graph)

    assert _describe_catalog(catalog) == [
        {
            "id": "INT-000",
            "class": "vulnerability_patch",
            "target": "n_sql_injection",
            "edges": ["e_sql_injection"],
            "cost": 1.0,
        }
    ]
    assert {item.cost.source for item in catalog.interventions} == {CostSource.ASSUMED_DEFAULT}


def test_episode5_provenance_separates_the_partial_route_from_case_results(
    episode5_graph: AttackGraph,
) -> None:
    provenance = _read_and_check_provenance("episode5-post-registration", episode5_graph)

    assert provenance["source"] == {
        "publication": "Armadin, Kill Chains and Coffee, episode 5",
        "url": "https://www.youtube.com/watch?v=LXzHIG4CqnA",
        "excerpts_file": "episode5-excerpts.txt",
    }
    assert provenance["validated_paths"] == [
        {
            "edge_ids": ["e_sql_injection"],
            "evidence_ids": ["starting-access", "sql-injection", "sql-execution"],
        }
    ]
    evidence_by_id = {record["id"]: record for record in provenance["evidence"]}
    for evidence_id in (
        "reported-counts",
        "linked-data",
        "workforce-data",
        "caller-data",
        "sim-prerequisites",
        "reported-impact",
    ):
        assert evidence_by_id[evidence_id]["node_ids"] == []
        assert evidence_by_id[evidence_id]["edge_ids"] == []
    assert provenance["findings"] == {
        "count": 3,
        "description": (
            "Source-reported SQL injections across the case, "
            "not modeled paths or total engagement findings"
        ),
        "evidence_ids": ["reported-counts"],
    }
    assert provenance["customer_remediation"] == {
        "reported_outcome": None,
        "evidence_ids": [],
        "details_status": "not_reported",
    }
