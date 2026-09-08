"""Load and apply human-supplied intervention cost overrides."""

import json
from collections.abc import Hashable
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from yaml.nodes import MappingNode

from lumon.model import Cost, CostSource, CostTier, InterventionCatalog
from lumon.model.graph import EntityId, reject_duplicate_ids


class CostOverrideError(ValueError):
    """A cost override file or requested override is invalid."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key: object = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, Hashable):
            raise CostOverrideError(f"unhashable mapping key: {key!r}")
        if key in mapping:
            raise CostOverrideError(f"duplicate mapping key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class _OverrideEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    intervention_id: EntityId
    tier: CostTier
    source: CostSource
    justification: str = Field(min_length=1)


class _OverrideDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    overrides: list[_OverrideEntry]

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> Self:
        reject_duplicate_ids(
            [override.intervention_id for override in self.overrides],
            "override intervention",
        )
        return self


def load_overrides(path: Path) -> dict[str, Cost]:
    """Load a strict YAML or JSON cost-override document."""
    suffix = path.suffix.lower()
    if suffix not in {".json", ".yaml", ".yml"}:
        raise CostOverrideError(f"{path} must use a .json, .yaml, or .yml extension")

    try:
        document = _OverrideDocument.model_validate(_read_document(path, suffix))
        overrides = {
            entry.intervention_id: Cost(
                tier=entry.tier,
                source=entry.source,
                justification=entry.justification,
            )
            for entry in document.overrides
        }
    except (OSError, json.JSONDecodeError, yaml.YAMLError, ValidationError) as error:
        raise CostOverrideError(f"{path} is not a valid cost override file: {error}") from error

    _reject_assumed(overrides)
    return overrides


def _read_document(path: Path, suffix: str) -> object:
    text = path.read_text()
    if suffix == ".json":
        return json.loads(text, object_pairs_hook=_construct_unique_json_mapping)
    return yaml.load(text, Loader=_UniqueKeyLoader)


def _construct_unique_json_mapping(pairs: list[tuple[str, object]]) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for key, value in pairs:
        if key in mapping:
            raise CostOverrideError(f"duplicate mapping key: {key!r}")
        mapping[key] = value
    return mapping


def apply_overrides(
    catalog: InterventionCatalog, overrides: dict[str, Cost]
) -> InterventionCatalog:
    """Return a catalog with the requested human-supplied costs."""
    _reject_assumed(overrides)
    unknown_ids = sorted(set(overrides) - set(catalog.by_id()))
    if unknown_ids:
        raise CostOverrideError(
            f"cost overrides name unknown intervention ids: {', '.join(unknown_ids)}"
        )
    return InterventionCatalog(
        interventions=[
            intervention.model_copy(update={"cost": overrides[intervention.id]})
            if intervention.id in overrides
            else intervention
            for intervention in catalog.interventions
        ]
    )


def _reject_assumed(overrides: dict[str, Cost]) -> None:
    assumed_ids = sorted(
        intervention_id for intervention_id, cost in overrides.items() if cost.source.is_assumed
    )
    if assumed_ids:
        raise CostOverrideError(
            "cost overrides must use operator_supplied or customer_supplied; "
            f"assumed_default was supplied for: {', '.join(assumed_ids)}"
        )
