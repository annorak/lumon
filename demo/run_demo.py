"""Run the source-backed and constructed examples without network access or private inputs."""

import json
import sys
from pathlib import Path as FilePath
from tempfile import NamedTemporaryFile
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl

from lumon.coverage import CoverageMatrix, StaleMatrixError
from lumon.generate import REALISTIC, GeneratorParams, generate
from lumon.hypotheses.generate import generate_hypotheses
from lumon.interventions import synthesize
from lumon.io import GraphInvariantError, GraphLoadError, assert_usable, load_graph
from lumon.model import AttackGraph, EdgeType, Intervention, InterventionCatalog, PathSet
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


class ConstructedResult(BaseModel):
    """A generated example, never source evidence or an exercised attack."""

    evidence_basis: Literal["constructed"]
    preset: Literal["REALISTIC"]
    generator_params: GeneratorParams
    graph_id: str
    validated_path_count: int
    candidate_count: int
    extraction_limits: dict[str, int]
    solution: Solution
    ranked_interventions: list[_RankedIntervention]
    bypass_queue: HypothesisQueue

    @property
    def headline(self) -> str:
        changes = len(self.solution.selected_intervention_ids)
        change_word = "change" if changes == 1 else "changes"
        unit_word = "unit" if self.solution.total_cost == 1 else "units"
        return (
            f"Constructed {self.preset} graph: {self.validated_path_count} paths marked validated, "
            f"{changes} {change_word}, cost {self.solution.total_cost:g} assumed implementation "
            f"{unit_word}. Lumon proves this is the minimum cost to sever all "
            f"{self.validated_path_count} paths using the {self.candidate_count} "
            "modeled candidates."
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
    solution = _solve_full_cover(matrix)
    ranked = _rank_interventions(catalog, matrix, solution)
    removed_ids = {edge_id for row in ranked for edge_id in row.intervention.removes_edge_ids}
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


def compute_constructed_result() -> ConstructedResult:
    graph, truth = generate(REALISTIC)
    assert_usable(graph)
    paths = extract_paths(graph, max_paths=MAX_PATHS, max_depth=MAX_DEPTH)
    if paths.truncated:
        raise ValueError(f"incomplete constructed path extraction: {paths.truncation_reason}")
    if sorted(path.node_ids for path in paths.paths) != truth.path_node_sequences:
        raise ValueError(
            "constructed paths do not match generator ground truth; check both extraction limits"
        )

    catalog = synthesize(graph)
    matrix = CoverageMatrix(paths, catalog, graph)
    matrix.verify_fingerprint(paths, catalog)
    solution = _solve_full_cover(matrix)
    queue = generate_hypotheses(
        graph,
        paths,
        catalog,
        matrix,
        solution.selected_intervention_ids,
        [],  # This preset supplies no alternatives matching the supported substitution rules.
        max_hypotheses=MAX_HYPOTHESES,
    )
    return ConstructedResult(
        evidence_basis="constructed",
        preset="REALISTIC",
        generator_params=REALISTIC,
        graph_id=graph.metadata["graph_id"],
        validated_path_count=len(paths.paths),
        candidate_count=len(catalog.interventions),
        extraction_limits={"max_paths": MAX_PATHS, "max_depth": MAX_DEPTH},
        solution=solution,
        ranked_interventions=_rank_interventions(catalog, matrix, solution),
        bypass_queue=queue,
    )


def _solve_full_cover(matrix: CoverageMatrix) -> Solution:
    solution = solve_min_cost_cover(matrix)
    if solution.guarantee is not OptimalityGuarantee.EXACT:
        raise ValueError(f"the demo requires a proven EXACT optimum: {solution.notes}")
    if not solution.is_full_cover or not matrix.is_full_cover(solution.selected_intervention_ids):
        raise ValueError("the selected changes do not sever every supplied validated path")
    return solution


def _rank_interventions(
    catalog: InterventionCatalog, matrix: CoverageMatrix, solution: Solution
) -> list[_RankedIntervention]:
    interventions = catalog.by_id()
    selected = [interventions[item_id] for item_id in solution.selected_intervention_ids]
    selected.sort(
        key=lambda item: (
            item.cost.tier.numeric_value,
            -matrix.weight_covered_by([item.id]),
            item.id,
        )
    )
    return [
        _RankedIntervention(
            rank=index,
            intervention=item,
            cost_units=item.cost.tier.numeric_value,
            covered_path_ids=matrix.paths_covered_by(item.id),
            covered_weight=matrix.weight_covered_by([item.id]),
        )
        for index, item in enumerate(selected, start=1)
    ]


def render_text(result: DemoResult | ConstructedResult) -> str:
    solution = result.solution
    metrics = [
        ("Metric", "Lumon"),
        ("Selected changes", str(len(solution.selected_intervention_ids))),
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
    source = (
        f"Source: {result.provenance.source.url}"
        if isinstance(result, DemoResult)
        else f"Input: {result.preset}, seed {result.generator_params.seed}. "
        "All evidence labels and objective weights are synthetic, not exercised attacks."
    )
    repository_url = result.repository_url if isinstance(result, DemoResult) else REPOSITORY_URL
    lines = [
        result.headline,
        f"Repository: {repository_url}",
        source,
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
        covered_paths = (
            ", ".join(row.covered_path_ids)
            if isinstance(result, DemoResult)
            else str(len(row.covered_path_ids))
        )
        lines.extend(
            [
                f"{row.rank}. {row.intervention.id}: {row.intervention.name}",
                f"   Cost: {row.cost_units:g} assumed implementation units; "
                f"supplied validated paths severed: {covered_paths}",
            ]
        )
    return "\n".join(lines)


def serialize_result(result: DemoResult, constructed: ConstructedResult) -> str:
    """Keep case provenance separate and run timing out of the repeatable artifact."""
    payload = result.model_dump(mode="json")
    payload["counts"] = result.counts
    payload["headline"] = result.headline
    constructed_payload = constructed.model_dump(mode="json")
    constructed_payload["headline"] = constructed.headline
    for case in (payload, constructed_payload):
        del case["solution"]["wall_time_seconds"]
    payload["constructed_case"] = constructed_payload
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
    stage = "Fortune 600 case"
    try:
        result = compute_result(root)
        stage = "constructed REALISTIC case"
        constructed = compute_constructed_result()
        stage = "result output"
        contents = serialize_result(result, constructed)
        display = render_text(result) + "\n\n" + render_text(constructed)
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
        print(f"Demo failed: {stage}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
