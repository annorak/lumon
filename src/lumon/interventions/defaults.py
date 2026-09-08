"""Assumed default implementation costs."""

from lumon.model import Cost, CostSource, CostTier, InterventionClass

# These defaults are assumptions, not measurements.
DEFAULT_COSTS: dict[InterventionClass, Cost] = {
    InterventionClass.VULNERABILITY_PATCH: Cost(
        tier=CostTier.LOW,
        source=CostSource.ASSUMED_DEFAULT,
        justification="usually a version bump and a deploy",
    ),
    InterventionClass.ACCESS_CONTROL_ADD: Cost(
        tier=CostTier.LOW,
        source=CostSource.ASSUMED_DEFAULT,
        justification="usually config, but can break callers",
    ),
    InterventionClass.CREDENTIAL_REMOVAL: Cost(
        tier=CostTier.MEDIUM,
        source=CostSource.ASSUMED_DEFAULT,
        justification="requires finding and updating consumers",
    ),
    InterventionClass.IDENTITY_PERMISSION_REDUCTION: Cost(
        tier=CostTier.MEDIUM,
        source=CostSource.ASSUMED_DEFAULT,
        justification="risk of breaking a workload",
    ),
    InterventionClass.CONTAINER_HARDENING: Cost(
        tier=CostTier.MEDIUM,
        source=CostSource.ASSUMED_DEFAULT,
        justification="redeploy plus possible workload changes",
    ),
    InterventionClass.EXECUTION_CONTEXT_REBIND: Cost(
        tier=CostTier.MEDIUM,
        source=CostSource.ASSUMED_DEFAULT,
        justification=(
            "changing which principal a workload runs as requires a redeploy and risks "
            "breaking the workload's legitimate access."
        ),
    ),
    InterventionClass.SERVICE_REMOVAL: Cost(
        tier=CostTier.HIGH,
        source=CostSource.ASSUMED_DEFAULT,
        justification="something depends on it",
    ),
    InterventionClass.NETWORK_SEGMENTATION: Cost(
        tier=CostTier.HIGH,
        source=CostSource.ASSUMED_DEFAULT,
        justification="architecture change, likely an outage window",
    ),
}
