from collections import Counter
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from lumon.model.enums import EdgeType, Evidence, NodeType


def _check_id(value: str) -> str:
    if not value or any(character.isspace() for character in value):
        raise ValueError("must be non-empty and contain no whitespace")
    return value


EntityId = Annotated[str, AfterValidator(_check_id)]


def reject_duplicate_ids(ids: list[str], kind: str) -> None:
    duplicates = sorted(id_ for id_, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise ValueError(f"duplicate {kind} ids: {', '.join(duplicates)}")


class Node(BaseModel):
    """Object an attacker interacts with."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    type: NodeType
    label: str
    attributes: dict[str, str] = Field(default_factory=dict)
    weight: float | None = None

    @model_validator(mode="after")
    def _validate_weight(self) -> Self:
        if self.type is NodeType.OBJECTIVE:
            if self.weight is None or self.weight <= 0:
                raise ValueError(f"objective node {self.id!r} needs a weight greater than 0")
        elif self.weight is not None:
            raise ValueError(f"node {self.id!r} is a {self.type}, so it may not carry a weight")
        return self


class Edge(BaseModel):
    """Directed attacker transition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId
    source: str
    target: str
    type: EdgeType
    evidence: Evidence
    # Node ID of the vulnerability or credential that enables this transition.
    enabled_by: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_no_self_loop(self) -> Self:
        if self.source == self.target:
            raise ValueError(f"edge {self.id!r} is a self-loop on node {self.source!r}")
        return self


class AttackGraph(BaseModel):
    """Nodes and attacker transitions before semantic validation.

    Missing node references are allowed so partial graph input can be represented. Call
    `check_invariants` before analysis.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes: list[Node]
    edges: list[Edge]
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> Self:
        reject_duplicate_ids([node.id for node in self.nodes], "node")
        reject_duplicate_ids([edge.id for edge in self.edges], "edge")
        return self

    def node_by_id(self, node_id: str) -> Node:
        for node in self.nodes:
            if node.id == node_id:
                return node
        raise KeyError(f"no node with id {node_id!r}")

    def edge_by_id(self, edge_id: str) -> Edge:
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
        return [edge for edge in self.edges if edge.evidence is Evidence.VALIDATED]
