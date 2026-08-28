import json
import re
from pathlib import Path

import pytest

from lumon.io import GraphLoadError, export_json_schema, load_graph, save_graph


def test_round_trip_preserves_the_graph(graphs_dir: Path, tmp_path: Path) -> None:
    graph = load_graph(graphs_dir / "valid_small.json")
    destination = tmp_path / "nested" / "round_trip.json"

    save_graph(graph, destination)

    assert load_graph(destination) == graph


def test_malformed_json_raises_with_the_path_in_the_message(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"nodes": [')

    with pytest.raises(GraphLoadError, match=re.escape(str(path))):
        load_graph(path)


def test_schema_invalid_graph_raises(tmp_path: Path) -> None:
    path = tmp_path / "weightless_objective.json"
    path.write_text(
        json.dumps(
            {"nodes": [{"id": "n_cloud", "type": "objective", "label": "cloud"}], "edges": []}
        )
    )

    with pytest.raises(GraphLoadError, match="weight greater than 0"):
        load_graph(path)


def test_export_json_schema_describes_the_attack_graph(tmp_path: Path) -> None:
    path = tmp_path / "schema" / "attack_graph.schema.json"

    export_json_schema(path)

    schema = json.loads(path.read_text())
    assert schema["title"] == "AttackGraph"
    assert set(schema["properties"]) == {"nodes", "edges", "metadata"}
    assert schema["description"]
    assert all(
        schema["$defs"][name].get("description")
        for name in ("Node", "Edge", "NodeType", "EdgeType", "Evidence")
    )
