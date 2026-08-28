import networkx as nx

from lumon.model import AttackGraph


def to_networkx(graph: AttackGraph, validated_only: bool = False) -> nx.MultiDiGraph:
    """Convert a graph without running semantic validation.

    Nodes store their model under `node`. Edges store their model under `edge` and use the edge
    ID as the `MultiDiGraph` key. `validated_only` filters edges but keeps all nodes.
    """
    converted = nx.MultiDiGraph()
    for node in graph.nodes:
        converted.add_node(node.id, node=node)
    for edge in graph.validated_edges() if validated_only else graph.edges:
        converted.add_edge(edge.source, edge.target, key=edge.id, edge=edge)
    return converted
