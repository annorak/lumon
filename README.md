# Lumon

Lumon helps a security team decide which fixes will break the most attack paths.

It does not scan a network or run attacks. It starts with paths that a red team has already
tested, puts them into a graph, and looks for changes that cut several paths at once.

## Why this exists

Security findings are usually fixed one ticket at a time. That can hide the bigger problem.

Say two different vulnerabilities lead to the same service account:

<div align="center">
  <code>public API bug</code> &rarr; <code>service account</code> &rarr; <code>cloud account</code><br>
  <code>admin UI bug</code> &rarr; <code>service account</code> &rarr; <code>cloud account</code>
</div>

Patching both entry points closes the paths we know about today. Reducing the service account's
permissions closes both paths and also makes the next entry-point bug less useful. Lumon is meant
to find changes like that.

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
      <td>4. Solve, planned</td>
      <td>Interventions, costs, and path weights</td>
      <td>Production CP-SAT results planned in Task 09</td>
    </tr>
    <tr>
      <td>5. Review, planned</td>
      <td>The solver results and untested graph edges</td>
      <td>A report with recommended changes and routes to test next</td>
    </tr>
  </tbody>
</table>

The current library can extract paths, propose changes, build the coverage table, and
represent solver results. Task 08 provides a brute-force answer key in shared test code.
Task 09 adds CP-SAT as the only production solver.

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
| `validated` | Someone performed and reproduced the transition | Yes |
| `observed` | Someone saw it but did not test it | No |
| `inferred` | A rule or analyst expects it to work | No |

Only validated edges become attack paths. Observed and inferred edges are kept because they may
be useful routes to test later, but they cannot change the recommended fixes.

Here is a small graph:

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

## Production solver plan

Task 09 will use CP-SAT for every production solve, with a default time limit of 30 seconds.
A result is labeled `EXACT` only when the solver proves it is optimal. If the time limit
expires with a feasible answer, Lumon returns it as `UNKNOWN`, meaning optimality is
unproven. If no answer was found, Lumon raises a solver error.

There will be one production solver, with no size-based selection or alternate solver
mode. Brute force lives under `tests/` to check CP-SAT on small examples. Task 10 will
generate many such examples and check coverage, costs, budgets, and optimality.
The production CP-SAT implementation is planned for Task 09.

## Install

Lumon requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/annorak/lumon.git
cd lumon
make install
```

There is no command-line interface yet. The current code is used as a Python library:

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
