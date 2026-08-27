"""The closed vocabularies the rest of Lumon speaks.

These are `StrEnum`s on purpose. A serialized graph records `"evidence": "validated"`
rather than an opaque integer, so an input file stays readable, diffable, and reviewable
by someone who does not trust us — which is the whole point of the project.
"""

from enum import StrEnum


class NodeType(StrEnum):
    """What a node in the attack graph is."""

    ASSET = "asset"
    SERVICE = "service"
    IDENTITY = "identity"
    CREDENTIAL = "credential"
    BOUNDARY = "boundary"
    VULNERABILITY = "vulnerability"
    OBJECTIVE = "objective"
    ENTRY_POINT = "entry_point"


class EdgeType(StrEnum):
    """The kind of transition an attacker makes when traversing an edge."""

    REACHES = "reaches"
    EXPLOITS = "exploits"
    EXECUTES_AS = "executes_as"
    READS = "reads"
    AUTHENTICATES_AS = "authenticates_as"
    CAN_ACCESS = "can_access"
    ESCAPES = "escapes"


class Evidence(StrEnum):
    """How well an edge is backed by evidence, and what that permits it to influence.

    There are three levels because "we proved this" and "we think this is there" are
    different claims, and Lumon's core guarantee is that the second can never quietly
    become the first. The tag is the mechanism that enforces that separation, and it is
    checked by every stage downstream of ingest.

    ``VALIDATED``
        The attacker actually performed this transition and it was reproduced. This is the
        **only** value the solver may consider. Path extraction, the coverage matrix, the
        cost frontier, and every severance claim are computed over validated edges alone.
        Because validation is a sample of reachability and not a census, results built from
        these edges are still scoped to *validated reachability* — never to "all paths."

    ``OBSERVED``
        Seen during reconnaissance but never exercised: a port that answered, a role that
        exists, a mount that is present. It may feed bypass-hypothesis generation, which
        produces a queue of routes to go test. It may never enter the solver and may never
        appear in a claim about what has been severed.

    ``INFERRED``
        Asserted by a rule rather than seen — "this role grants that permission, so this
        transition should work." Same permission as ``OBSERVED``: hypotheses only, never
        the solver, and never phrased as a finding.

    Anything computed from ``OBSERVED`` or ``INFERRED`` edges is a hypothesis awaiting
    validation. If you are about to write code that lets either one change an answer,
    stop and ask.
    """

    VALIDATED = "validated"
    OBSERVED = "observed"
    INFERRED = "inferred"
