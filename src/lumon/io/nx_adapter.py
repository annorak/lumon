"""The NetworkX view of an attack graph, for the graph algorithms later stages need."""

import networkx as nx

from lumon.model import AttackGraph


def to_networkx(graph: AttackGraph, validated_only: bool = False) -> nx.MultiDiGraph:
    """A `MultiDiGraph` of this attack graph.

    Each node carries the full `Node` under its ``node`` attribute, and each edge the full
    `Edge` under its ``edge`` attribute, keyed by edge id so a lookup names exactly one edge.

    `MultiDiGraph` rather than `DiGraph` because one pair of nodes can be joined by several
    distinct transitions — an identity that both `REACHES` and `CAN_ACCESS` a cloud account
    is two edges, with different interventions available against each. Collapsing them would
    throw one away, and the solver would then be choosing from a catalog missing a fix.

    `validated_only=True` keeps every node but only `Evidence.VALIDATED` edges. That is the
    view every claim Lumon makes is computed over.

    This is a plain conversion and does **not** check invariants. Given a graph with a
    dangling edge, NetworkX will invent the missing endpoint as a node with no attributes.
    Call `assert_usable` where the graph enters the pipeline, not here, so that a caller can
    still convert a graph it already knows is broken in order to look at it.
    """
    converted = nx.MultiDiGraph()
    for node in graph.nodes:
        converted.add_node(node.id, node=node)
    for edge in graph.validated_edges() if validated_only else graph.edges:
        converted.add_edge(edge.source, edge.target, key=edge.id, edge=edge)
    return converted
