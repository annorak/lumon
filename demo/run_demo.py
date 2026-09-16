"""Run the reviewed Fortune 600 example without network access or private inputs."""

import json
import sys
from pathlib import Path as FilePath
from tempfile import NamedTemporaryFile
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl

from lumon.coverage import CoverageMatrix, StaleMatrixError
from lumon.hypotheses.generate import generate_hypotheses
from lumon.interventions import synthesize
from lumon.io import GraphInvariantError, GraphLoadError, assert_usable, load_graph
from lumon.model import AttackGraph, EdgeType, Intervention, PathSet
from lumon.model.hypothesis import HypothesisQueue
from lumon.paths import extract_paths
from lumon.solve import (
    InfeasibleError,
    OptimalityGuarantee,
    Solution,
    SolverError,
    solve_min_cost_cover,
)

REPOSITORY_URL = "https://github.com/annorak/lumon"
FIXTURE_NAME = "episode4-fortune600"
MAX_PATHS = 5000
MAX_DEPTH = 12
MAX_HYPOTHESES = 20

_NonblankText = Annotated[str, Field(pattern=r"\S")]


class _Source(BaseModel):
    publication: _NonblankText
    url: HttpUrl
    excerpts_file: _NonblankText


class _ReviewedPath(BaseModel):
    edge_ids: list[_NonblankText] = Field(min_length=1)
    evidence_ids: list[_NonblankText] = Field(min_length=1)


class _Findings(BaseModel):
    count: int = Field(ge=0)
    description: _NonblankText
    evidence_ids: list[_NonblankText] = Field(min_length=1)


class _CustomerRemediation(BaseModel):
    reported_outcome: _NonblankText
    evidence_ids: list[_NonblankText] = Field(min_length=1)
    details_status: Literal["not_reported"]


class _Provenance(BaseModel):
    """Consumed fields only; full quotations remain in the linked provenance file."""

    graph_id: Literal["armadin-kcc-episode4-fortune600"]
    source: _Source
    validated_paths: list[_ReviewedPath] = Field(min_length=1)
    findings: _Findings
    customer_remediation: _CustomerRemediation
    assumptions: list[_NonblankText]
    omissions: list[_NonblankText]


class _RankedIntervention(BaseModel):
    rank: int
    intervention: Intervention
    cost_units: float
    covered_path_ids: list[str]
    covered_weight: float


class DemoResult(BaseModel):
    """Shared values for console output, JSON, and later release media."""

    repository_url: str
    graph: AttackGraph
    provenance_file: str
    provenance: _Provenance
    paths: PathSet
    matrix_fingerprint: str
    extraction_limits: dict[str, int]
    solution: Solution
    ranked_interventions: list[_RankedIntervention]
    removed_transition_ids: list[str]
    remaining_transition_ids: list[str]
    remaining_credential_read_ids: list[str]
    remaining_credential_authentication_ids: list[str]
    permission_bindings: Literal["not_separately_modeled"]
    customer: dict[str, None]
    bypass_queue: HypothesisQueue

    @property
    def counts(self) -> dict[str, int]:
        return {
            "N_validated_paths": len(self.paths.paths),
            "M_selected_changes": len(self.solution.selected_intervention_ids),
            "K_source_reported_findings": self.provenance.findings.count,
        }

    @property
    def headline(self) -> str:
        counts = self.counts
        change_word = "change" if counts["M_selected_changes"] == 1 else "changes"
        path_word = "path" if counts["N_validated_paths"] == 1 else "paths"
        return (
            f"For the Fortune 600 chain reported in {self.provenance.source.publication}, "
            f"Lumon selects {counts['M_selected_changes']} modeled {change_word} at minimum cost "
            f"to sever the {counts['N_validated_paths']} supplied source-validated {path_word} "
            "under the stated cost assumptions; the podcast separately reports "
            f"{counts['K_source_reported_findings']} remote-code-execution findings."
        )


def compute_result(root: FilePath) -> DemoResult:
    graph_file = root / "fixtures/armadin/graphs" / f"{FIXTURE_NAME}.json"
    provenance_file = FilePath("fixtures/armadin/provenance") / f"{FIXTURE_NAME}.json"
    graph = load_graph(graph_file)
    assert_usable(graph)
    provenance = _Provenance.model_validate_json(
        (root / provenance_file).read_text(encoding="utf-8"), strict=True
    )
    if graph.metadata.get("graph_id") != provenance.graph_id:
        raise ValueError(
            "the demo graph and provenance must identify the reviewed Fortune 600 case"
        )
    if graph.metadata.get("source_url") != str(provenance.source.url):
        raise ValueError("the demo graph and provenance must identify the same source URL")

    paths = extract_paths(graph, max_paths=MAX_PATHS, max_depth=MAX_DEPTH)
    if paths.truncated:
        raise ValueError(f"incomplete path extraction: {paths.truncation_reason}")
    reviewed_routes = sorted(tuple(path.edge_ids) for path in provenance.validated_paths)
    if sorted(tuple(path.edge_ids) for path in paths.paths) != reviewed_routes:
        raise ValueError(
            "extracted paths do not match the reviewed source-supported routes; "
            "check the evidence and both extraction limits"
        )

    catalog = synthesize(graph)
    matrix = CoverageMatrix(paths, catalog, graph)
    matrix.verify_fingerprint(paths, catalog)
    solution = solve_min_cost_cover(matrix)
    if solution.guarantee is not OptimalityGuarantee.EXACT:
        raise ValueError(f"the demo requires a proven EXACT optimum: {solution.notes}")
    if not solution.is_full_cover or not matrix.is_full_cover(solution.selected_intervention_ids):
        raise ValueError("the selected changes do not sever every supplied validated path")

    interventions = catalog.by_id()
    selected = [interventions[item_id] for item_id in solution.selected_intervention_ids]
    selected.sort(
        key=lambda item: (
            item.cost.tier.numeric_value,
            -matrix.weight_covered_by([item.id]),
            item.id,
        )
    )
    ranked = [
        _RankedIntervention(
            rank=index,
            intervention=item,
            cost_units=item.cost.tier.numeric_value,
            covered_path_ids=matrix.paths_covered_by(item.id),
            covered_weight=matrix.weight_covered_by([item.id]),
        )
        for index, item in enumerate(selected, start=1)
    ]
    removed_ids = {edge_id for item in selected for edge_id in item.removes_edge_ids}
    remaining_edges = [edge for edge in graph.edges if edge.id not in removed_ids]
    queue = generate_hypotheses(
        graph,
        paths,
        catalog,
        matrix,
        solution.selected_intervention_ids,
        [],  # The reviewed fixture supplies no alternate transitions or applicability decisions.
        max_hypotheses=MAX_HYPOTHESES,
    )
    return DemoResult(
        repository_url=REPOSITORY_URL,
        graph=graph,
        provenance_file=provenance_file.as_posix(),
        provenance=provenance,
        paths=paths,
        matrix_fingerprint=matrix.fingerprint,
        extraction_limits={"max_paths": MAX_PATHS, "max_depth": MAX_DEPTH},
        solution=solution,
        ranked_interventions=ranked,
        removed_transition_ids=sorted(removed_ids),
        remaining_transition_ids=sorted(edge.id for edge in remaining_edges),
        remaining_credential_read_ids=sorted(
            edge.id for edge in remaining_edges if edge.type is EdgeType.READS
        ),
        remaining_credential_authentication_ids=sorted(
            edge.id for edge in remaining_edges if edge.type is EdgeType.AUTHENTICATES_AS
        ),
        permission_bindings="not_separately_modeled",
        customer=dict.fromkeys(
            [
                "selected_intervention_ids",
                "change_count",
                "total_cost",
                "removed_transition_ids",
                "covered_path_ids",
                "covered_path_count",
                "uncovered_path_ids",
                "uncovered_path_count",
                "covered_weight",
                "is_full_cover",
                "remaining_transition_ids",
                "remaining_credential_read_ids",
                "remaining_credential_authentication_ids",
                "permission_bindings",
                "bypass_queue",
            ]
        ),
        bypass_queue=queue,
    )


def render_text(result: DemoResult) -> str:
    solution = result.solution
    metrics = [
        ("Metric", "Lumon"),
        ("Selected changes", str(result.counts["M_selected_changes"])),
        ("Cost, assumed implementation units", f"{solution.total_cost:g}"),
        ("Supplied validated paths severed", str(len(solution.covered_path_ids))),
        ("Severed path weight, assumed", f"{solution.covered_weight:g}"),
        ("Uncovered supplied validated paths", str(len(solution.uncovered_path_ids))),
        ("Optimality", solution.guarantee.value.upper()),
    ]
    metric_width = max(len(metric) for metric, _ in metrics)
    value_width = max(len(value) for _, value in metrics)
    border = f"+-{'-' * metric_width}-+-{'-' * value_width}-+"
    table = [f"| {metric:<{metric_width}} | {value:>{value_width}} |" for metric, value in metrics]
    lines = [
        result.headline,
        f"Repository: {result.repository_url}",
        f"Source: {result.provenance.source.url}",
        "",
        border,
        table[0],
        border,
        *table[1:],
        border,
        "",
        "Selected changes, display order: cost ascending, individual weight descending, then ID.",
    ]
    for row in result.ranked_interventions:
        lines.extend(
            [
                f"{row.rank}. {row.intervention.id}: {row.intervention.name}",
                f"   Cost: {row.cost_units:g} assumed implementation units; "
                f"supplied validated paths severed: {', '.join(row.covered_path_ids)}",
            ]
        )
    return "\n".join(lines)


def serialize_result(result: DemoResult) -> str:
    """Keep run timing out of the shared, repeatable result artifact."""
    payload = result.model_dump(mode="json", exclude={"solution": {"wall_time_seconds"}})
    payload["counts"] = result.counts
    payload["headline"] = result.headline
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _write_result(output: FilePath, contents: str) -> None:
    """Replace the prior result only after a complete write in the same directory."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=output.parent, prefix=".result-", delete=False
    ) as temporary:
        try:
            temporary.write(contents)
            temporary.close()
            FilePath(temporary.name).replace(output)
        finally:
            FilePath(temporary.name).unlink(missing_ok=True)


def main() -> int:
    root = FilePath(__file__).resolve().parents[1]
    try:
        result = compute_result(root)
        contents = serialize_result(result)
        display = render_text(result)
        _write_result(root / "demo/output/result.json", contents)
        print(display)
        print("Result written to demo/output/result.json")
    except (
        OSError,
        ValueError,
        GraphLoadError,
        GraphInvariantError,
        StaleMatrixError,
        InfeasibleError,
        SolverError,
    ) as error:
        print(f"Demo failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
