"""Nodes, edges, and the attack graph they form.

Pure data. Every model here is frozen and forbids unknown fields: frozen so an analysis
stage cannot mutate the graph it was handed, and `extra="forbid"` so a typo in an input
file is a loud error instead of a silently dropped key. The only methods are lookups —
everything that computes lives in the pipeline packages.
"""

from collections import Counter
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from lumon.model.enums import EdgeType, Evidence, NodeType


def _check_id(value: str) -> str:
    if not value or any(character.isspace() for character in value):
        raise ValueError("must be non-empty and contain no whitespace")
    return value


EntityId = Annotated[str, AfterValidator(_check_id)]
"""An id used to reference a node or an edge. Ids appear in paths, coverage matrices, and
reports, so whitespace in one turns every downstream join into a guessing game."""


def _reject_duplicate_ids(ids: list[str], kind: str) -> None:
    duplicates = sorted(id_ for id_, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {kind} ids: {', '.join(duplicates)}")


class Node(BaseModel):
    """One thing an attacker interacts with: an asset, service, identity, credential,
    boundary, vulnerability, entry point, or objective."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    type: NodeType
    label: str
    attributes: dict[str, str] = Field(default_factory=dict)
    # Only objectives carry a weight: how much the business loses if this one falls. It is
    # what makes "severed 81% of weighted validated paths" mean anything.
    weight: float | None = None

    @model_validator(mode="after")
    def _check_weight_matches_type(self) -> Self:
        if self.type is NodeType.OBJECTIVE:
            if self.weight is None or self.weight <= 0:
                raise ValueError(f"objective node {self.id!r} needs a weight greater than 0")
        elif self.weight is not None:
            raise ValueError(f"node {self.id!r} is a {self.type}, so it may not carry a weight")
        return self


class Edge(BaseModel):
    """One transition an attacker makes, from `source` to `target`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    source: str
    target: str
    type: EdgeType
    evidence: Evidence
    # Node id of the vulnerability or credential that makes this transition possible.
    enabled_by: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_not_self_loop(self) -> Self:
        if self.source == self.target:
            raise ValueError(f"edge {self.id!r} is a self-loop on node {self.source!r}")
        return self


class AttackGraph(BaseModel):
    """A set of nodes and the attacker transitions between them.

    Whether an edge's endpoints actually exist is deliberately *not* checked here. Ingest
    builds partial graphs as evidence arrives, so a graph that references a node it does
    not yet contain must be constructible. `lumon.io.invariants` is where a graph is judged
    usable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes: list[Node]
    edges: list[Edge]
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_ids_unique(self) -> Self:
        _reject_duplicate_ids([node.id for node in self.nodes], "node")
        _reject_duplicate_ids([edge.id for edge in self.edges], "edge")
        return self

    def node_by_id(self, node_id: str) -> Node:
        """The node with this id. Raises `KeyError` if the graph has no such node."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(f"no node with id {node_id!r}")

    def edge_by_id(self, edge_id: str) -> Edge:
        """The edge with this id. Raises `KeyError` if the graph has no such edge."""
        for edge in self.edges:
            if edge.id == edge_id:
                return edge
        raise KeyError(f"no edge with id {edge_id!r}")

    def nodes_of_type(self, node_type: NodeType) -> list[Node]:
        return [node for node in self.nodes if node.type is node_type]

    def edges_of_type(self, edge_type: EdgeType) -> list[Edge]:
        return [edge for edge in self.edges if edge.type is edge_type]

    def entry_points(self) -> list[Node]:
        return self.nodes_of_type(NodeType.ENTRY_POINT)

    def objectives(self) -> list[Node]:
        return self.nodes_of_type(NodeType.OBJECTIVE)

    def validated_edges(self) -> list[Edge]:
        """The edges an attacker proved. These are the only ones any result may rest on —
        see `Evidence` for what the other two levels are allowed to influence."""
        return [edge for edge in self.edges if edge.evidence is Evidence.VALIDATED]
