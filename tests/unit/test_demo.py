"""Regression checks for the live, public-input Fortune 600 demonstration."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from demo import run_demo as demo

from lumon.coverage import CoverageMatrix, StaleMatrixError
from lumon.interventions import synthesize
from lumon.model import Intervention, InterventionCatalog
from lumon.solve import InfeasibleError, OptimalityGuarantee, Solution, SolverError

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_HEADLINE = (
    "For the Fortune 600 chain reported in Armadin, Kill Chains and Coffee, episode 4, "
    "Lumon selects 1 modeled change at minimum cost to sever the 1 supplied "
    "source-validated path under the stated cost assumptions; the podcast separately "
    "reports 12 remote-code-execution findings."
)
EXPECTED_FINGERPRINT = "8779e43738511e00ba17a9bf13c0c8875951babd0b3af126d05682efc8b7f855"


@pytest.fixture
def result() -> demo.DemoResult:
    return demo.compute_result(ROOT)


@pytest.fixture
def demo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "demo/run_demo.py"
    script.parent.mkdir()
    shutil.copyfile(ROOT / "demo/run_demo.py", script)
    shutil.copytree(ROOT / "fixtures/armadin", tmp_path / "fixtures/armadin")
    monkeypatch.setattr(demo, "__file__", str(script))
    return tmp_path


def _run_command(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "demo/run_demo.py")],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
    )


def _assert_failed_main(root: Path, capsys: pytest.CaptureFixture[str], explanation: str) -> None:
    output = root / "demo/output/result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    previous = '{"previous": true}\n'
    output.write_text(previous, encoding="utf-8")

    assert demo.main() == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Demo failed:" in captured.err
    assert explanation in captured.err
    assert output.read_text(encoding="utf-8") == previous
    assert list(output.parent.iterdir()) == [output]


def test_live_result_matches_the_reviewed_full_cover(result: demo.DemoResult) -> None:
    assert result.counts == {
        "N_validated_paths": 1,
        "M_selected_changes": 1,
        "K_source_reported_findings": 12,
    }
    assert result.headline == EXPECTED_HEADLINE
    assert result.graph.metadata["graph_id"] == "armadin-kcc-episode4-fortune600"
    assert result.matrix_fingerprint == EXPECTED_FINGERPRINT
    assert result.extraction_limits == {"max_paths": 5000, "max_depth": 12}
    assert not result.paths.truncated
    assert result.solution.guarantee is OptimalityGuarantee.EXACT
    assert result.solution.selected_intervention_ids == ["INT-003"]
    assert result.solution.total_cost == 1
    assert result.solution.covered_path_ids == ["p0000"]
    assert result.solution.uncovered_path_ids == []
    assert result.solution.covered_weight == 10
    assert result.solution.is_full_cover
    assert result.removed_transition_ids == ["e_ssrf"]
    assert result.ranked_interventions[0].rank == 1
    assert result.ranked_interventions[0].intervention.cost.source.value == "assumed_default"
    assert result.ranked_interventions[0].cost_units == 1
    assert result.ranked_interventions[0].covered_path_ids == ["p0000"]
    assert result.ranked_interventions[0].covered_weight == 10


def test_readme_and_saved_result_match_the_live_result(result: demo.DemoResult) -> None:
    saved = (ROOT / "demo/output/result.json").read_text(encoding="utf-8")
    assert saved == demo.serialize_result(result)
    assert json.loads(saved)["headline"] == EXPECTED_HEADLINE

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.split("\n\n", 2)[:2] == ["# Lumon", EXPECTED_HEADLINE]
    assert f"[Repository]({result.repository_url})" in readme
    assert "\nuv run --frozen python demo/run_demo.py\n" in readme


def test_unknown_customer_results_are_not_an_empty_lumon_queue(result: demo.DemoResult) -> None:
    assert result.customer == {
        "selected_intervention_ids": None,
        "change_count": None,
        "total_cost": None,
        "removed_transition_ids": None,
        "covered_path_ids": None,
        "covered_path_count": None,
        "uncovered_path_ids": None,
        "uncovered_path_count": None,
        "covered_weight": None,
        "is_full_cover": None,
        "remaining_transition_ids": None,
        "remaining_credential_read_ids": None,
        "remaining_credential_authentication_ids": None,
        "permission_bindings": None,
        "bypass_queue": None,
    }
    assert result.provenance.customer_remediation.details_status == "not_reported"
    assert result.bypass_queue.hypotheses == []
    assert not result.bypass_queue.truncated
    assert result.bypass_queue.max_hypotheses == 20
    assert result.bypass_queue.selected_intervention_ids == ["INT-003"]
    assert result.bypass_queue.matrix_fingerprint == EXPECTED_FINGERPRINT


def test_console_shows_a_compact_lumon_table(result: demo.DemoResult) -> None:
    assert demo.render_text(result) == (
        EXPECTED_HEADLINE
        + "\nRepository: https://github.com/annorak/lumon"
        + f"\nSource: {result.provenance.source.url}\n\n"
        + """+------------------------------------+-------+
| Metric                             | Lumon |
+------------------------------------+-------+
| Selected changes                   |     1 |
| Cost, assumed implementation units |     1 |
| Supplied validated paths severed   |     1 |
| Severed path weight, assumed       |    10 |
| Uncovered supplied validated paths |     0 |
| Optimality                         | EXACT |
+------------------------------------+-------+

Selected changes, display order: cost ascending, individual weight descending, then ID.
1. INT-003: Patch vulnerability n_ssrf
   Cost: 1 assumed implementation units; supplied validated paths severed: p0000"""
    )


def test_repeated_commands_write_identical_results_from_public_inputs(demo_root: Path) -> None:
    assert not (demo_root / ".private").exists()
    first = _run_command(demo_root)
    assert first.returncode == 0, first.stderr
    output = demo_root / "demo/output/result.json"
    first_bytes = output.read_bytes()
    second = _run_command(demo_root)
    assert second.returncode == 0, second.stderr

    assert first.stderr == second.stderr == ""
    assert first.stdout == second.stdout
    assert output.read_bytes() == first_bytes
    payload = json.loads(first_bytes)
    assert payload["headline"] == EXPECTED_HEADLINE
    assert first.stdout.splitlines()[0] == payload["headline"]
    assert "Result written to demo/output/result.json" in first.stdout
    assert payload["counts"] == {
        "N_validated_paths": 1,
        "M_selected_changes": 1,
        "K_source_reported_findings": 12,
    }
    assert payload["solution"]["selected_intervention_ids"] == ["INT-003"]
    assert payload["solution"]["guarantee"] == "exact"
    assert payload["matrix_fingerprint"] == EXPECTED_FINGERPRINT
    assert b"wall_time_seconds" not in first_bytes
    assert str(ROOT).encode() not in first_bytes
    assert str(demo_root).encode() not in first_bytes


def test_credential_claims_follow_the_computed_removal_effects(
    result: demo.DemoResult, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert result.remaining_transition_ids == [
        "e_cloud_authentication",
        "e_credential_read",
        "e_cve_execution",
        "e_public_reach",
    ]
    assert result.remaining_credential_read_ids == ["e_credential_read"]
    assert result.remaining_credential_authentication_ids == ["e_cloud_authentication"]
    assert result.permission_bindings == "not_separately_modeled"
    catalog = synthesize(result.graph)
    # Test-only prices make credential removal the real optimum, not a guessed customer fix.
    synthetic_catalog = InterventionCatalog(
        interventions=[
            Intervention.model_validate(
                {
                    **item.model_dump(),
                    "cost": {
                        **item.cost.model_dump(),
                        "tier": "low" if item.id == "INT-001" else "high",
                        "justification": "Synthetic test: credential-removal cost is low.",
                    },
                }
            )
            for item in catalog.interventions
        ]
    )
    monkeypatch.setattr(demo, "synthesize", lambda graph: synthetic_catalog)
    changed = demo.compute_result(ROOT)

    assert changed.solution.guarantee is OptimalityGuarantee.EXACT
    assert changed.solution.selected_intervention_ids == ["INT-001"]
    assert changed.solution.is_full_cover
    assert changed.removed_transition_ids == ["e_cloud_authentication", "e_credential_read"]
    assert changed.remaining_credential_read_ids == []
    assert changed.remaining_credential_authentication_ids == []
    assert changed.graph == result.graph
    assert changed.customer == result.customer


def test_invalid_input_exits_nonzero_without_an_output(demo_root: Path) -> None:
    graph_file = demo_root / "fixtures/armadin/graphs/episode4-fortune600.json"
    graph_file.write_text("{", encoding="utf-8")
    run = _run_command(demo_root)

    assert run.returncode == 1
    assert run.stdout == ""
    assert "Demo failed:" in run.stderr
    assert "episode4-fortune600.json" in run.stderr
    assert not (demo_root / "demo/output/result.json").exists()


@pytest.mark.parametrize(
    ("limit", "value", "explanation"),
    [("MAX_PATHS", 0, "incomplete path extraction"), ("MAX_DEPTH", 4, "both extraction limits")],
)
def test_incomplete_extraction_retains_the_previous_result(
    demo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    limit: str,
    value: int,
    explanation: str,
) -> None:
    monkeypatch.setattr(demo, limit, value)
    _assert_failed_main(demo_root, capsys, explanation)


@pytest.mark.parametrize(
    ("target", "error"),
    [
        ("demo.run_demo.solve_min_cost_cover", InfeasibleError(["p0000"])),
        ("demo.run_demo.solve_min_cost_cover", SolverError("controlled solver failure")),
        ("demo.run_demo.CoverageMatrix.verify_fingerprint", StaleMatrixError("stale input")),
        ("demo.run_demo.generate_hypotheses", ValueError("review substitute applicability")),
    ],
)
def test_dependency_failures_retain_the_previous_result(
    demo_root: Path, capsys: pytest.CaptureFixture[str], target: str, error: Exception
) -> None:
    with patch(target, side_effect=error):
        _assert_failed_main(demo_root, capsys, str(error))


@pytest.mark.parametrize(
    ("selected_ids", "guarantee", "is_full_cover", "explanation"),
    [
        (["INT-003"], OptimalityGuarantee.UNKNOWN, True, "proven EXACT optimum"),
        ([], OptimalityGuarantee.EXACT, False, "do not sever every supplied validated path"),
        ([], OptimalityGuarantee.EXACT, True, "do not sever every supplied validated path"),
    ],
)
def test_unproven_or_incomplete_solutions_are_rejected(
    demo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    selected_ids: list[str],
    guarantee: OptimalityGuarantee,
    is_full_cover: bool,
    explanation: str,
) -> None:
    def supply_controlled_solution(matrix: CoverageMatrix) -> Solution:
        solution = Solution.from_matrix(
            matrix, selected_ids, solver_name="cp_sat", guarantee=guarantee, wall_time_seconds=0
        )
        # Exercise the independent matrix check even if the solver reports a wrong coverage flag.
        return solution.model_copy(update={"is_full_cover": is_full_cover})

    monkeypatch.setattr(demo, "solve_min_cost_cover", supply_controlled_solution)
    _assert_failed_main(demo_root, capsys, explanation)


def test_failed_output_replacement_cleans_up_and_preserves_previous_result(
    demo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with patch.object(Path, "replace", side_effect=OSError("controlled output failure")):
        _assert_failed_main(demo_root, capsys, "controlled output failure")


def test_main_writes_the_shared_result(demo_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert demo.main() == 0
    captured = capsys.readouterr()
    payload = json.loads((demo_root / "demo/output/result.json").read_text(encoding="utf-8"))
    assert captured.err == ""
    assert captured.out.splitlines()[0] == payload["headline"] == EXPECTED_HEADLINE
    assert payload["solution"]["selected_intervention_ids"] == ["INT-003"]
    assert payload["matrix_fingerprint"] == EXPECTED_FINGERPRINT
    assert "wall_time_seconds" not in payload["solution"]


@pytest.mark.parametrize("blank", ["", " \t\n"])
@pytest.mark.parametrize(
    "field_path",
    [
        ("source", "publication"),
        ("source", "excerpts_file"),
        ("validated_paths", 0, "edge_ids", 0),
        ("validated_paths", 0, "evidence_ids", 0),
        ("findings", "description"),
        ("findings", "evidence_ids", 0),
        ("customer_remediation", "reported_outcome"),
        ("customer_remediation", "evidence_ids", 0),
        ("assumptions", 0),
        ("omissions", 0),
    ],
)
def test_blank_provenance_text_is_rejected_before_writing(
    demo_root: Path,
    capsys: pytest.CaptureFixture[str],
    field_path: tuple[str | int, ...],
    blank: str,
) -> None:
    provenance_file = demo_root / "fixtures/armadin/provenance/episode4-fortune600.json"
    fields = json.loads(provenance_file.read_text(encoding="utf-8"))
    section = fields
    for key in field_path[:-1]:
        section = section[key]
    section[field_path[-1]] = blank
    provenance_file.write_text(json.dumps(fields), encoding="utf-8")

    _assert_failed_main(demo_root, capsys, ".".join(str(key) for key in field_path))


@pytest.mark.parametrize(
    ("key", "explanation"),
    [("graph_id", "reviewed Fortune 600 case"), ("source_url", "same source URL")],
)
def test_mismatched_graph_provenance_is_rejected(
    demo_root: Path, capsys: pytest.CaptureFixture[str], key: str, explanation: str
) -> None:
    graph_file = demo_root / "fixtures/armadin/graphs/episode4-fortune600.json"
    fields = json.loads(graph_file.read_text(encoding="utf-8"))
    fields["metadata"][key] = "wrong-source"
    graph_file.write_text(json.dumps(fields), encoding="utf-8")

    _assert_failed_main(demo_root, capsys, explanation)
