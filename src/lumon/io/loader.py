"""Reading and writing attack graphs as JSON files.

JSON is the interchange format on purpose. An input graph has to be reviewable by someone
who does not trust us, which means it has to be readable in a text editor and meaningful in
a diff. A binary or database-backed format would make the input as unauditable as the answer.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from lumon.model import AttackGraph


class GraphLoadError(Exception):
    """A file could not be read as an `AttackGraph`."""


def load_graph(path: Path) -> AttackGraph:
    """The attack graph in this JSON file.

    Raises `GraphLoadError` if the file is not valid JSON or does not match the schema. A
    graph that loads cleanly is still only well-formed, not necessarily usable —
    `lumon.io.invariants` is what decides that.
    """
    try:
        return AttackGraph.model_validate_json(path.read_text())
    except ValidationError as error:
        raise GraphLoadError(f"{path} is not a valid attack graph: {error}") from error


def save_graph(graph: AttackGraph, path: Path) -> None:
    """Write the graph as indented JSON, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.model_dump_json(indent=2) + "\n")


def export_json_schema(path: Path) -> None:
    """Write the JSON Schema for `AttackGraph`, so a tool outside this repo can produce input
    Lumon will accept without having to read our Pydantic models."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(AttackGraph.model_json_schema(), indent=2) + "\n")
