import json
from pathlib import Path

import pytest

from lumon.interventions import CostOverrideError, apply_overrides, load_overrides
from lumon.model import (
    Cost,
    CostSource,
    CostTier,
    Intervention,
    InterventionCatalog,
    InterventionClass,
)


def _build_catalog() -> InterventionCatalog:
    return InterventionCatalog(
        interventions=[
            Intervention(
                id="INT-000",
                name="Patch vulnerability",
                intervention_class=InterventionClass.VULNERABILITY_PATCH,
                removes_edge_ids=frozenset({"e_exploit"}),
                cost=Cost(
                    tier=CostTier.LOW,
                    source=CostSource.ASSUMED_DEFAULT,
                    justification="default patch cost",
                ),
            ),
            Intervention(
                id="INT-001",
                name="Downscope identity",
                intervention_class=InterventionClass.IDENTITY_PERMISSION_REDUCTION,
                removes_edge_ids=frozenset({"e_access"}),
                cost=Cost(
                    tier=CostTier.MEDIUM,
                    source=CostSource.ASSUMED_DEFAULT,
                    justification="default identity cost",
                ),
            ),
        ]
    )


@pytest.mark.parametrize(
    ("suffix", "body"),
    [
        pytest.param(
            ".json",
            json.dumps(
                {
                    "overrides": [
                        {
                            "intervention_id": "INT-000",
                            "tier": "high",
                            "source": "customer_supplied",
                            "justification": "customer change estimate",
                        }
                    ]
                }
            ),
            id="json",
        ),
        pytest.param(
            ".yaml",
            """
overrides:
  - intervention_id: INT-000
    tier: high
    source: customer_supplied
    justification: customer change estimate
""",
            id="yaml",
        ),
        pytest.param(
            ".yml",
            """
overrides:
  - intervention_id: INT-000
    tier: high
    source: customer_supplied
    justification: customer change estimate
""",
            id="yml",
        ),
    ],
)
def test_load_overrides_accepts_json_and_yaml(tmp_path: Path, suffix: str, body: str) -> None:
    path = tmp_path / f"costs{suffix}"
    path.write_text(body)

    overrides = load_overrides(path)

    assert overrides == {
        "INT-000": Cost(
            tier=CostTier.HIGH,
            source=CostSource.CUSTOMER_SUPPLIED,
            justification="customer change estimate",
        )
    }


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_load_overrides_rejects_duplicate_ids(tmp_path: Path, suffix: str) -> None:
    records = [
        {
            "intervention_id": "INT-000",
            "tier": "low",
            "source": "operator_supplied",
            "justification": "first estimate",
        },
        {
            "intervention_id": "INT-000",
            "tier": "high",
            "source": "customer_supplied",
            "justification": "second estimate",
        },
    ]
    path = tmp_path / f"costs{suffix}"
    if suffix == ".json":
        path.write_text(json.dumps({"overrides": records}))
    else:
        path.write_text(
            """
overrides:
  - intervention_id: INT-000
    tier: low
    source: operator_supplied
    justification: first estimate
  - intervention_id: INT-000
    tier: high
    source: customer_supplied
    justification: second estimate
"""
        )

    with pytest.raises(CostOverrideError, match="duplicate override intervention ids: INT-000"):
        load_overrides(path)


@pytest.mark.parametrize(
    ("suffix", "body"),
    [
        pytest.param(
            ".json",
            '{"overrides":[{"intervention_id":"INT-000","tier":"low",'
            '"tier":"high","source":"operator_supplied","justification":"estimate"}]}',
            id="json",
        ),
        pytest.param(
            ".yaml",
            """
overrides:
  - intervention_id: INT-000
    tier: low
    tier: high
    source: operator_supplied
    justification: estimate
""",
            id="yaml",
        ),
    ],
)
def test_load_overrides_rejects_duplicate_mapping_keys(
    tmp_path: Path, suffix: str, body: str
) -> None:
    path = tmp_path / f"costs{suffix}"
    path.write_text(body)

    with pytest.raises(CostOverrideError, match="duplicate mapping key: 'tier'"):
        load_overrides(path)


def test_load_overrides_rejects_assumed_costs(tmp_path: Path) -> None:
    path = tmp_path / "costs.json"
    path.write_text(
        json.dumps(
            {
                "overrides": [
                    {
                        "intervention_id": "INT-000",
                        "tier": "low",
                        "source": "assumed_default",
                        "justification": "not a human estimate",
                    }
                ]
            }
        )
    )

    with pytest.raises(CostOverrideError, match="must use operator_supplied or customer_supplied"):
        load_overrides(path)


def test_load_overrides_rejects_extra_fields(tmp_path: Path) -> None:
    path = tmp_path / "costs.yaml"
    path.write_text(
        """
overrides:
  - intervention_id: INT-000
    tier: high
    source: customer_supplied
    justification: customer change estimate
    confidence: certain
"""
    )

    with pytest.raises(CostOverrideError, match="Extra inputs"):
        load_overrides(path)


def test_load_overrides_rejects_an_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "costs.toml"
    path.write_text("overrides = []")

    with pytest.raises(CostOverrideError, match=r"\.json, \.yaml, or \.yml"):
        load_overrides(path)


def test_apply_overrides_changes_cost_and_preserves_other_interventions() -> None:
    catalog = _build_catalog()
    replacement = Cost(
        tier=CostTier.HIGH,
        source=CostSource.CUSTOMER_SUPPLIED,
        justification="customer change estimate",
    )

    updated = apply_overrides(catalog, {"INT-000": replacement})

    assert updated.by_id()["INT-000"].cost == replacement
    assert updated.by_id()["INT-001"] is catalog.by_id()["INT-001"]
    assert catalog.by_id()["INT-000"].cost.source is CostSource.ASSUMED_DEFAULT


def test_apply_overrides_rejects_an_assumed_default() -> None:
    assumed = Cost(
        tier=CostTier.HIGH,
        source=CostSource.ASSUMED_DEFAULT,
        justification="still an assumption",
    )

    with pytest.raises(CostOverrideError, match="must use operator_supplied or customer_supplied"):
        apply_overrides(_build_catalog(), {"INT-000": assumed})


def test_apply_overrides_rejects_unknown_intervention_ids() -> None:
    supplied = Cost(
        tier=CostTier.HIGH,
        source=CostSource.OPERATOR_SUPPLIED,
        justification="operator estimate",
    )

    with pytest.raises(CostOverrideError, match="unknown intervention ids: INT-999"):
        apply_overrides(_build_catalog(), {"INT-999": supplied})
