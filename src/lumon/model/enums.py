from enum import StrEnum


class NodeType(StrEnum):
    """Type of object represented by a graph node."""

    ASSET = "asset"
    SERVICE = "service"
    IDENTITY = "identity"
    CREDENTIAL = "credential"
    BOUNDARY = "boundary"
    VULNERABILITY = "vulnerability"
    OBJECTIVE = "objective"
    ENTRY_POINT = "entry_point"


class EdgeType(StrEnum):
    """Attacker action represented by a directed edge."""

    REACHES = "reaches"
    EXPLOITS = "exploits"
    EXECUTES_AS = "executes_as"
    READS = "reads"
    AUTHENTICATES_AS = "authenticates_as"
    CAN_ACCESS = "can_access"
    ESCAPES = "escapes"


class Evidence(StrEnum):
    """How an attacker transition was established.

    Analysis uses validated edges. Observed and inferred edges are reserved for bypass
    hypotheses that still need testing.
    """

    VALIDATED = "validated"
    OBSERVED = "observed"
    INFERRED = "inferred"
