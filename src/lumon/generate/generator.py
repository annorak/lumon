"""Building an attack graph whose answers are known before anything is asked of it.

The graph is a layered DAG. Layer 0 holds the entry points, layers 1 through `depth` hold
intermediate nodes, and the last layer holds the objectives. Every node in a layer is joined
to every node in the next by one validated edge, and a validated edge never runs anywhere
else — not backwards, not across a gap, not within a layer.

Two things fall straight out of that restriction, and both are the point of the module:

- **The path set is a product, not a search.** A validated path is one node from each layer
  in order, and every such combination is a path, so the complete set is
  `itertools.product(*layers)`. The generator never traverses the graph to find its paths,
  which is what keeps `GroundTruth` independent of the code it is used to test.
- **A layer of width one is a chokepoint.** Narrowing a layer to a single node leaves every
  path no choice but to pass through it.

Decoy `OBSERVED` and `INFERRED` edges are added on top, always pointing from an earlier layer
to a strictly later one. Such an edge can never invent a validated path — it is not validated
— and the route it names is one the validated backbone already provides, since consecutive
layers are fully joined and reachability therefore runs forward through every layer. Decoys
are free to skip past a chokepoint, and that is deliberate: an unexercised route around the
fix is exactly the raw material task 13 turns into bypass hypotheses to go and test.
"""

import hashlib
import itertools
import random

from lumon.generate.params import GeneratorParams
from lumon.generate.truth import GroundTruth
from lumon.model import AttackGraph, Edge, EdgeType, Evidence, Node, NodeType


def generate(params: GeneratorParams) -> tuple[AttackGraph, GroundTruth]:
    """A synthetic attack graph and the answers that come with it.

    Every random choice runs through one `random.Random`, drawn from in a fixed order:
    chokepoint placement, then objective weights, then decoy edges. Reordering those three
    calls would change what every existing seed produces, so do not.
    """
    rng = random.Random(params.seed)
    chokepoint_layers = sorted(rng.sample(range(1, params.depth + 1), params.n_planted_chokepoints))
    objective_weights = _draw_objective_weights(params, rng)

    layers = _build_layers(params, chokepoint_layers, objective_weights)
    backbone = _build_backbone(layers)
    graph = AttackGraph(
        nodes=[node for layer in layers for node in layer],
        edges=[*backbone, *_build_decoys(layers, backbone, params, rng)],
        metadata=_build_metadata(params),
    )
    return graph, _build_truth(layers, chokepoint_layers, objective_weights)


def _draw_objective_weights(params: GeneratorParams, rng: random.Random) -> dict[str, float]:
    """What each objective is worth. Drawn before the nodes exist so that the ground truth
    and the objective nodes read the same numbers out of one place."""
    low, high = params.objective_weight_range
    return {
        f"n_obj_{index:02d}": float(rng.randint(low, high)) for index in range(params.n_objectives)
    }


def _build_layers(
    params: GeneratorParams,
    chokepoint_layers: list[int],
    objective_weights: dict[str, float],
) -> list[list[Node]]:
    """The nodes, grouped into the layers that give the graph its shape."""
    entries = [
        Node(id=f"n_entry_{index:02d}", type=NodeType.ENTRY_POINT, label=f"entry point {index}")
        for index in range(params.n_entry_points)
    ]
    intermediates = [
        _build_intermediate_layer(position, position in chokepoint_layers, params.branching)
        for position in range(1, params.depth + 1)
    ]
    objectives = [
        Node(id=node_id, type=NodeType.OBJECTIVE, label=f"objective {index}", weight=weight)
        for index, (node_id, weight) in enumerate(objective_weights.items())
    ]
    return [entries, *intermediates, objectives]


def _build_intermediate_layer(position: int, is_chokepoint: bool, branching: int) -> list[Node]:
    """One intermediate layer: `branching` alternate routes, or a single node if this layer is
    the one every path is being forced through."""
    if is_chokepoint:
        return [
            Node(
                id=f"n_choke_l{position}",
                type=NodeType.SERVICE,
                label=f"planted chokepoint at layer {position}",
            )
        ]
    return [
        Node(
            id=f"n_l{position}_{index:02d}",
            type=NodeType.SERVICE,
            label=f"layer {position} alternative {index}",
        )
        for index in range(branching)
    ]


def _build_backbone(layers: list[list[Node]]) -> list[Edge]:
    """One validated edge from every node in a layer to every node in the next.

    Joining consecutive layers completely is what makes the path set a plain product of the
    layer widths. Leave any of these edges out and the ground truth stops being constructible
    without going and looking at the graph.
    """
    joined = [
        (source, target)
        for earlier, later in itertools.pairwise(layers)
        for source, target in itertools.product(earlier, later)
    ]
    return [
        Edge(
            id=f"e_{index:04d}",
            source=source.id,
            target=target.id,
            type=EdgeType.REACHES,
            evidence=Evidence.VALIDATED,
        )
        for index, (source, target) in enumerate(joined)
    ]


def _build_decoys(
    layers: list[list[Node]],
    backbone: list[Edge],
    params: GeneratorParams,
    rng: random.Random,
) -> list[Edge]:
    """The non-validated edges, counted as a fraction of the validated backbone.

    There is always room to place them. Slots run over every forward node pair crossed with
    every edge type, so there are at least `7 * validated - validated` of them, while the two
    ratios cap at 1.0 each and can therefore ask for at most `2 * validated`.
    """
    validated_count = len(backbone)
    n_observed = round(params.observed_edge_ratio * validated_count)
    n_inferred = round(params.inferred_edge_ratio * validated_count)
    drawn = rng.sample(_forward_slots(layers, backbone), n_observed + n_inferred)
    evidence_per_slot = [Evidence.OBSERVED] * n_observed + [Evidence.INFERRED] * n_inferred

    return [
        Edge(
            id=f"e_{validated_count + index:04d}",
            source=source,
            target=target,
            type=edge_type,
            evidence=evidence,
        )
        for index, ((source, target, edge_type), evidence) in enumerate(
            zip(drawn, evidence_per_slot, strict=True)
        )
    ]


def _forward_slots(
    layers: list[list[Node]], backbone: list[Edge]
) -> list[tuple[str, str, EdgeType]]:
    """Every place a decoy edge could go: a node pair running strictly forward through the
    layers, paired with an edge type, minus the ones the backbone already occupies."""
    occupied = {(edge.source, edge.target, edge.type) for edge in backbone}
    forward_pairs = [
        (source, target)
        for position, earlier in enumerate(layers)
        for later in layers[position + 1 :]
        for source, target in itertools.product(earlier, later)
    ]
    return [
        (source.id, target.id, edge_type)
        for source, target in forward_pairs
        for edge_type in EdgeType
        if (source.id, target.id, edge_type) not in occupied
    ]


def _build_truth(
    layers: list[list[Node]],
    chokepoint_layers: list[int],
    objective_weights: dict[str, float],
) -> GroundTruth:
    """The answers, read off the layout rather than computed from the finished graph."""
    return GroundTruth(
        path_node_sequences=sorted(
            [node.id for node in combination] for combination in itertools.product(*layers)
        ),
        planted_chokepoint_ids=[layers[position][0].id for position in chokepoint_layers],
        # Every planted chokepoint sits on every path, so one of them covers all of them.
        minimum_chokepoint_cover_size=min(len(chokepoint_layers), 1),
        objective_weights=objective_weights,
    )


def _build_metadata(params: GeneratorParams) -> dict[str, str]:
    """Enough to regenerate this exact graph from the file it was saved to. `graph_id` is
    keyed to the parameters rather than the seed alone, so two graphs sharing a seed but
    differing in shape do not claim to be the same graph."""
    serialized = params.model_dump_json()
    digest = hashlib.sha256(serialized.encode()).hexdigest()[:8]
    return {"graph_id": f"synthetic-{digest}", "generator_params": serialized}
