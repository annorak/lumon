"""Generate layered attack graphs with known paths and chokepoints."""

import hashlib
import itertools
import random

from lumon.generate.params import GeneratorParams
from lumon.generate.truth import GroundTruth
from lumon.model import AttackGraph, Edge, EdgeType, Evidence, Node, NodeType


def generate(params: GeneratorParams) -> tuple[AttackGraph, GroundTruth]:
    """Build a synthetic graph and its expected results."""
    rng = random.Random(params.seed)
    # Keep this draw order stable so existing seeds continue to produce the same graph.
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
    low, high = params.objective_weight_range
    return {
        f"n_obj_{index:02d}": float(rng.randint(low, high)) for index in range(params.n_objectives)
    }


def _build_layers(
    params: GeneratorParams,
    chokepoint_layers: list[int],
    objective_weights: dict[str, float],
) -> list[list[Node]]:
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
    # Ground truth assumes every adjacent pair of layers is fully connected.
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
    return GroundTruth(
        path_node_sequences=sorted(
            [node.id for node in combination] for combination in itertools.product(*layers)
        ),
        planted_chokepoint_ids=[layers[position][0].id for position in chokepoint_layers],
        # Every planted chokepoint lies on every path, so any one covers the full set.
        minimum_chokepoint_cover_size=1 if chokepoint_layers else 0,
        objective_weights=objective_weights,
    )


def _build_metadata(params: GeneratorParams) -> dict[str, str]:
    serialized = params.model_dump_json()
    digest = hashlib.sha256(serialized.encode()).hexdigest()[:8]
    return {"graph_id": f"synthetic-{digest}", "generator_params": serialized}
