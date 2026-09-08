"""Candidate environment changes and their cost provenance."""

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from lumon.model.graph import EntityId, reject_duplicate_ids


class InterventionClass(StrEnum):
    """Kind of environment change represented by an intervention."""

    VULNERABILITY_PATCH = "vulnerability_patch"
    ACCESS_CONTROL_ADD = "access_control_add"
    IDENTITY_PERMISSION_REDUCTION = "identity_permission_reduction"
    CREDENTIAL_REMOVAL = "credential_removal"
    NETWORK_SEGMENTATION = "network_segmentation"
    SERVICE_REMOVAL = "service_removal"
    CONTAINER_HARDENING = "container_hardening"
    EXECUTION_CONTEXT_REBIND = "execution_context_rebind"


class CostTier(StrEnum):
    """Coarse implementation-cost tier."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def numeric_value(self) -> float:
        return {
            CostTier.LOW: 1.0,
            CostTier.MEDIUM: 3.0,
            CostTier.HIGH: 9.0,
        }[self]


class CostSource(StrEnum):
    """Origin of an intervention cost."""

    ASSUMED_DEFAULT = "assumed_default"
    OPERATOR_SUPPLIED = "operator_supplied"
    CUSTOMER_SUPPLIED = "customer_supplied"

    @property
    def is_assumed(self) -> bool:
        return self is CostSource.ASSUMED_DEFAULT


class Cost(BaseModel):
    """Implementation cost with mandatory provenance and explanation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tier: CostTier
    source: CostSource
    justification: str = Field(min_length=1)

    @field_validator("justification")
    @classmethod
    def _validate_justification(cls, justification: str) -> str:
        if not justification.strip():
            raise ValueError("justification must contain non-whitespace text")
        return justification


class Intervention(BaseModel):
    """One named environment change and the validated edges it removes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    name: str
    intervention_class: InterventionClass
    removes_edge_ids: frozenset[str] = Field(min_length=1)
    cost: Cost
    target_node_id: str | None = None
    side_effects_declared: bool = False
    notes: str | None = None

    @field_serializer("removes_edge_ids", when_used="json")
    def _serialize_removes_edge_ids(self, edge_ids: frozenset[str]) -> list[str]:
        return sorted(edge_ids)


class InterventionCatalog(BaseModel):
    """Candidate changes available to the optimizer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    interventions: list[Intervention]

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> Self:
        reject_duplicate_ids(
            [intervention.id for intervention in self.interventions],
            "intervention",
        )
        return self

    def by_id(self) -> dict[str, Intervention]:
        return {intervention.id: intervention for intervention in self.interventions}

    def assumed_cost_interventions(self) -> list[Intervention]:
        return [
            intervention
            for intervention in self.interventions
            if intervention.cost.source.is_assumed
        ]

    def total_cost(self) -> float:
        return sum(intervention.cost.tier.numeric_value for intervention in self.interventions)

    def covering_edge(self, edge_id: str) -> list[Intervention]:
        return [
            intervention
            for intervention in self.interventions
            if edge_id in intervention.removes_edge_ids
        ]
