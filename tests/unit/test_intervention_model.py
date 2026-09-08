import json

import pytest
from pydantic import ValidationError

from lumon.interventions import DEFAULT_COSTS
from lumon.model import (
    Cost,
    CostSource,
    CostTier,
    Intervention,
    InterventionCatalog,
    InterventionClass,
)


def _cost(
    tier: CostTier = CostTier.LOW,
    source: CostSource = CostSource.ASSUMED_DEFAULT,
    justification: str = "test cost",
) -> Cost:
    return Cost(tier=tier, source=source, justification=justification)


def _intervention(
    intervention_id: str = "INT-000",
    intervention_class: InterventionClass = InterventionClass.VULNERABILITY_PATCH,
    removes_edge_ids: frozenset[str] = frozenset({"e_one"}),
    cost: Cost | None = None,
) -> Intervention:
    return Intervention(
        id=intervention_id,
        name=f"intervention {intervention_id}",
        intervention_class=intervention_class,
        removes_edge_ids=removes_edge_ids,
        cost=cost or _cost(),
        target_node_id="n_target",
    )


def test_cost_requires_a_justification() -> None:
    with pytest.raises(ValidationError, match="justification"):
        Cost.model_validate(
            {
                "tier": CostTier.LOW,
                "source": CostSource.ASSUMED_DEFAULT,
            }
        )


@pytest.mark.parametrize("justification", ["", "   "])
def test_cost_rejects_an_empty_justification(justification: str) -> None:
    with pytest.raises(ValidationError, match="justification"):
        _cost(justification=justification)


def test_intervention_rejects_an_empty_removal_set() -> None:
    with pytest.raises(ValidationError, match="removes_edge_ids"):
        _intervention(removes_edge_ids=frozenset())


def test_catalog_rejects_duplicate_intervention_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate intervention ids: INT-000"):
        InterventionCatalog(
            interventions=[
                _intervention("INT-000"),
                _intervention("INT-000", removes_edge_ids=frozenset({"e_two"})),
            ]
        )


def test_assumed_cost_interventions_returns_only_assumed_costs() -> None:
    assumed = _intervention("INT-000")
    supplied = _intervention(
        "INT-001",
        cost=_cost(
            source=CostSource.CUSTOMER_SUPPLIED,
            justification="customer supplied this tier",
        ),
    )
    catalog = InterventionCatalog(interventions=[assumed, supplied])

    assert catalog.assumed_cost_interventions() == [assumed]


@pytest.mark.parametrize(
    ("tier", "numeric_value"),
    [
        pytest.param(CostTier.LOW, 1.0, id="low"),
        pytest.param(CostTier.MEDIUM, 3.0, id="medium"),
        pytest.param(CostTier.HIGH, 9.0, id="high"),
    ],
)
def test_cost_tier_numeric_values(tier: CostTier, numeric_value: float) -> None:
    assert tier.numeric_value == numeric_value


def test_only_assumed_default_is_marked_assumed() -> None:
    assert CostSource.ASSUMED_DEFAULT.is_assumed is True
    assert CostSource.OPERATOR_SUPPLIED.is_assumed is False
    assert CostSource.CUSTOMER_SUPPLIED.is_assumed is False


def test_catalog_queries_use_ids_and_removal_sets() -> None:
    first = _intervention("INT-000", removes_edge_ids=frozenset({"e_one", "e_shared"}))
    second = _intervention(
        "INT-001",
        removes_edge_ids=frozenset({"e_shared"}),
        cost=_cost(tier=CostTier.HIGH),
    )
    catalog = InterventionCatalog(interventions=[first, second])

    assert catalog.by_id() == {"INT-000": first, "INT-001": second}
    assert catalog.covering_edge("e_shared") == [first, second]
    assert catalog.covering_edge("e_absent") == []
    assert catalog.total_cost() == 10.0


def test_removal_ids_serialize_in_stable_order() -> None:
    intervention = _intervention(removes_edge_ids=frozenset({"e_zulu", "e_alpha"}))

    serialized = json.loads(intervention.model_dump_json())

    assert serialized["removes_edge_ids"] == ["e_alpha", "e_zulu"]


def test_default_cost_table_covers_every_class() -> None:
    assert set(DEFAULT_COSTS) == set(InterventionClass)
    assert all(cost.source is CostSource.ASSUMED_DEFAULT for cost in DEFAULT_COSTS.values())
    assert all(cost.justification.strip() for cost in DEFAULT_COSTS.values())


def test_default_cost_tiers_match_the_documented_assumptions() -> None:
    assert {item: cost.tier for item, cost in DEFAULT_COSTS.items()} == {
        InterventionClass.VULNERABILITY_PATCH: CostTier.LOW,
        InterventionClass.ACCESS_CONTROL_ADD: CostTier.LOW,
        InterventionClass.CREDENTIAL_REMOVAL: CostTier.MEDIUM,
        InterventionClass.IDENTITY_PERMISSION_REDUCTION: CostTier.MEDIUM,
        InterventionClass.CONTAINER_HARDENING: CostTier.MEDIUM,
        InterventionClass.EXECUTION_CONTEXT_REBIND: CostTier.MEDIUM,
        InterventionClass.SERVICE_REMOVAL: CostTier.HIGH,
        InterventionClass.NETWORK_SEGMENTATION: CostTier.HIGH,
    }


def test_execution_context_default_records_why_it_is_assumed() -> None:
    assert DEFAULT_COSTS[InterventionClass.EXECUTION_CONTEXT_REBIND].justification == (
        "changing which principal a workload runs as requires a redeploy and risks "
        "breaking the workload's legitimate access."
    )
