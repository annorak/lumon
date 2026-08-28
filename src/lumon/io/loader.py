import json
from pathlib import Path

from pydantic import ValidationError

from lumon.model import AttackGraph


class GraphLoadError(Exception):
    """Graph JSON could not be loaded."""


def load_graph(path: Path) -> AttackGraph:
    """Load graph JSON and validate its schema.

    This does not check semantic invariants. Call `assert_usable` before analysis.
    """
    try:
        return AttackGraph.model_validate_json(path.read_text())
    except ValidationError as error:
        raise GraphLoadError(f"{path} is not a valid attack graph: {error}") from error


def save_graph(graph: AttackGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.model_dump_json(indent=2) + "\n")


def export_json_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(AttackGraph.model_json_schema(), indent=2) + "\n")
