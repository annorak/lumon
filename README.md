# Lumon

For the Fortune 600 chain reported in Armadin, Kill Chains and Coffee, episode 4, Lumon selects 1 modeled change at minimum cost to sever the 1 supplied source-validated path under the stated cost assumptions; the podcast separately reports 12 remote-code-execution findings.

[Repository](https://github.com/annorak/lumon).

Lumon helps a security team choose changes that sever supplied validated attack paths.

It does not scan a network or run attacks. It starts with paths that a red team has already
tested, puts them into a graph, and looks for changes that cut several paths at once.

## Run the demo

You need Git, Python 3.12, and [uv](https://docs.astral.sh/uv/getting-started/installation/).
If Python 3.12 is missing, run `uv python install 3.12`.
See the [Python installation instructions](https://docs.astral.sh/uv/guides/install-python/).

```sh
git clone https://github.com/annorak/lumon.git
cd lumon
uv run --frozen python demo/run_demo.py
```

The last command installs or synchronizes dependencies from `uv.lock`, computes the
answer live, prints the headline and comparison, and writes
[demo/output/result.json](demo/output/result.json). Repeated runs replace that file;
the command never reads it as a cached answer.

The command reads the reviewed Fortune 600
[graph](fixtures/armadin/graphs/episode4-fortune600.json) and
[provenance](fixtures/armadin/provenance/episode4-fortune600.json).
Supporting evidence is in the [approved excerpts](fixtures/armadin/sources/episode4-excerpts.txt).
Validation is reported by the source, not independently performed by Lumon.
Private transcripts are not needed at runtime.

Dependency downloads may need internet access. The installed demo makes no runtime
network calls and needs no API keys, Docker, database, or service account.

Costs and objective weights are assumptions, not measured customer effort or impact.
The demo minimizes cost over the supplied candidate changes while severing every
supplied validated path. It does not minimize the number of changes or compute a
Pareto frontier.

The podcast reports that the customer remediated the reported findings, but its actual
changes, cost, modeled coverage, and remaining access are unknown. A numerical savings
comparison is unavailable, and the customer's bypass queue is unavailable.

Lumon's generated queue is empty for this fixture because it supplies no observed or
inferred alternate transitions. An empty queue does not establish that no bypasses exist.

## Why this exists

Security findings are usually fixed one ticket at a time. That can hide the bigger problem.

In this synthetic illustration, two different vulnerabilities lead to the same service account:

<div align="center">
  <code>public API bug</code> &rarr; <code>service account</code> &rarr; <code>cloud account</code><br>
  <code>admin UI bug</code> &rarr; <code>service account</code> &rarr; <code>cloud account</code>
</div>

If both supplied validated paths depend on the same permission, removing it can sever both
under that modeled removal effect. Whether another entry-point bug could rebuild a route is an
unvalidated hypothesis to test. Costs and operational side effects still matter.

## How it works

<table>
  <thead>
    <tr>
      <th>Step</th>
      <th>Input</th>
      <th>Output</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1. Load and validate</td>
      <td>Nodes and attacker transitions</td>
      <td>A parsed and checked attack graph</td>
    </tr>
    <tr>
      <td>2. Find paths</td>
      <td>Transitions that were actually tested</td>
      <td>Validated paths within the configured limits</td>
    </tr>
    <tr>
      <td>3. Build interventions</td>
      <td>Possible changes such as patching a bug or reducing permissions</td>
      <td>The paths each change would break</td>
    </tr>
    <tr>
      <td>4. Solve</td>
      <td>Interventions, costs, and path weights</td>
      <td>A portfolio with coverage, cost, and an explicit optimality status</td>
    </tr>
    <tr>
      <td>5. Generate hypotheses</td>
      <td>Selected changes and supplied observed or inferred alternate transitions</td>
      <td>A ranked queue of unvalidated hypotheses to test next</td>
    </tr>
  </tbody>
</table>

The current library can extract validated paths, propose changes, build the coverage table,
and solve full-cover and budgeted problems with CP-SAT. A separate brute-force solver in
the tests checks small examples. The demo prints a console summary and writes JSON.
The shared bypass generator supports entry and vulnerability substitution only, not the
full Task 13 feature set. General-purpose reporting remains deferred.

## The graph

A graph contains nodes and directed edges. Nodes are things an attacker interacts with:

- entry points
- services and assets
- identities and credentials
- vulnerabilities and security boundaries
- objectives, such as a production account or sensitive data

Edges describe what the attacker did, for example `reaches`, `exploits`, `reads`, or
`authenticates_as`.

Every edge has an evidence level:

| Evidence | Meaning | Used for optimization |
|---|---|---|
| `validated` | The transition is reported as exercised; Lumon does not independently reproduce it | Yes |
| `observed` | Someone saw it but did not test it | No |
| `inferred` | A rule or analyst expects it to work | No |

Only paths made of validated edges enter optimization. For the demo fixtures, extracted routes
are also checked against reviewed source-supported sequences. Observed and inferred edges can
supply unvalidated hypotheses; they do not contribute to optimized path coverage or the
validated-path headline.

Here is a synthetic graph example:

```json
{
  "nodes": [
    {"id": "internet", "type": "entry_point", "label": "Public API"},
    {"id": "api", "type": "service", "label": "Checkout API"},
    {
      "id": "cloud",
      "type": "objective",
      "label": "Production cloud account",
      "weight": 10
    }
  ],
  "edges": [
    {
      "id": "reach-api",
      "source": "internet",
      "target": "api",
      "type": "reaches",
      "evidence": "validated"
    },
    {
      "id": "reach-cloud",
      "source": "api",
      "target": "cloud",
      "type": "can_access",
      "evidence": "validated"
    }
  ]
}
```

The models use Pydantic. If you mostly write Java, think of them as records with JSON parsing and
constructor validation built in. NetworkX provides the in-memory directed graph.

## Paths and interventions

A path is an ordered list of edges from an entry point to an objective. Two paths may visit the
same nodes but use different edges. That matters because a change may block one attacker
technique without blocking the other.

An intervention represents one change to the environment. It records:

- a name
- the edge IDs it removes
- an estimated cost
- the source of that estimate

One intervention may remove several edges. That is why Lumon cannot use a normal minimum-cut
algorithm where every edge has its own independent price. Full severance is a weighted set-cover
problem. Choosing the best coverage under a fixed budget is a maximum-coverage problem.
Both are NP-hard: the search can become expensive as the input grows. Exact solving is expected
to be practical for tens of validated paths and roughly 100 candidate changes, but completion
within the time limit is not guaranteed.

## Production solver

CP-SAT runs every production solve, with a default time limit of 30 seconds.
A result is labeled `EXACT` only when the solver proves it is optimal. If the time limit
expires with a feasible answer, Lumon returns it as `UNKNOWN`, meaning optimality is
unproven. If no answer was found, Lumon raises a solver error.

There is no size-based solver selection or fallback. Brute force stays under `tests/`.
The demo-first release verifies minimum-cost full cover under the existing assumed
cost tiers of 1, 3, and 9. It does not complete the original Task 10 budgeted checks.

## Full-cover verification

After installing the development dependencies, run `make check` for lint, formatting,
strict typing, and the complete test suite with the existing 90 percent coverage floor.

The focused properties check reported coverage and cost, agreement with brute force,
repeatable completed solves, uncoverable paths, dominated changes, and generated graphs
through the real pipeline. Normal runs use 200 examples for cheap properties and 50 for
oracle comparisons. Brute-force comparisons use at most 12 interventions. Equal-cost
optima need not select the same IDs across solvers.

For a deeper search:

```sh
make verify
```

This prints a fresh numeric seed and runs 1000 examples for cheap properties and 250
for oracle comparisons. The extra finite-shape checks may exhaust all possibilities
before that limit. To replay a run, replace the example seed below with its printed value:

```sh
uv run --frozen pytest tests/property --no-cov -x \
  --hypothesis-profile=demo-deep --hypothesis-seed=123456789 \
  --hypothesis-show-statistics
```

The focused command disables coverage collection because it is not the full suite.
It does not replace `make check` or lower that command's coverage requirement.
Hypothesis stores reusable examples under `.hypothesis/examples/`. Reviewed JSON
regressions live separately under `tests/property/regression/`. The initial saved
example shows how two cheap changes beat one expensive change. A separate test
checks shrinking with a deliberately broken toy. Neither reports a production bug.

Generated tests search for mistakes; they do not prove correctness for every input.
Any claim of optimality still requires an `EXACT` result from the solver.

## Limitations

The focused release uses integer cost tiers and positive integer path weights.
Broader numeric and budgeted property checks remain deferred. The budgeted solver can
raise at budget 0.3 when selected costs 0.1 and 0.2 sum to 0.30000000000000004.
The existing regression remains in the full suite. The demo does not use budgeted
solving, and this release does not fix that issue.

Intervention effects are modeled edge removals. Operational side effects are untested.
Remaining credential transitions do not prove that a complete bypass route survives.
Kubernetes permission bindings are not separately modeled in the Fortune 600 fixture.
The bypass generator uses only supplied alternatives and requires explicit applicability
decisions where relevant. Unsupported substitutions are not evidence of safety.

The PNG, GIF, playable video, final README media layout, and public CI verification
remain pending. Fresh-install benchmarking is not required for this release.
The frontier, robustness sweep, predicate normalization, LLM-assisted ingestion,
and general-purpose CLI remain deferred.

## Library usage

The demo script is available; a general-purpose CLI remains deferred.
You can also use Lumon as a Python library:

```python
from pathlib import Path

from lumon.io import assert_usable, load_graph
from lumon.paths import extract_paths, summarize

graph = load_graph(Path("attack-graph.json"))
assert_usable(graph)

paths = extract_paths(graph)
stats = summarize(paths)

print(f"found {stats.path_count} validated paths")
```

`assert_usable` checks the graph before analysis. `extract_paths` walks only validated edges.
`summarize` gives a quick count of the paths, objectives, lengths, weight, and most common edge.
