# Lumon

**Attack-path intervention optimizer with bypass hypothesis generation.**

Lumon takes a set of **validated attack paths** — routes an attacker actually proved they
could take through an environment — and computes the minimum-cost set of environment changes
that severs them. It presents the answer as a Pareto frontier of implementation cost against
weighted validated paths severed, so a security leader picks their own point on the curve
instead of being handed one number. It then emits a ranked queue of **bypass hypotheses**:
structurally similar routes that would likely survive each proposed fix and therefore need
testing next.

---

## The governing principle

> **Everything Lumon claims must be checkable by someone who does not trust us.**

Four rules follow from that, and they are enforced by tests rather than by good intentions:

1. **Only `validated` edges influence the answer.** Edges marked `observed` or `inferred` feed
   the hypothesis generator and nothing else.
2. **Every cost carries its provenance.** A cost is labeled `assumed_default`,
   `operator_supplied`, or `customer_supplied` everywhere it appears, forever. An assumption is
   never laundered into a measurement.
3. **Inferences are phrased as hypotheses, never as findings.** A bypass hypothesis is a test
   queue item. Lumon never says a bypass path exists.
4. **No language model is anywhere in the decision path.** See
   [Where AI is and is not allowed](#where-ai-is-and-is-not-allowed).

---

## The problem

A red team engagement produces hundreds of findings and a few dozen validated attack paths. The
customer gets a prioritized list and fixes it top-down. That workflow has a specific failure
mode: **customers fix instances, not archetypes.**

The motivating example, from a publicly published engagement: a company received 12
unauthenticated remote-code-execution findings and remediated all 12 within low double-digit
hours. Genuinely fast, genuinely well done. But all 12 sat at the *entry* of the same kill
chain. The over-permissioned Kubernetes principal and the readable credential material at the
*end* of the chain were untouched, because no individual finding pointed at them. The next
entry-point bug that ships reconstitutes the whole path to cloud compromise.

No human looking at 12 separate tickets sees the shared chokepoint. The graph sees it. Lumon is
the thing that looks at the graph.

---

## The pipeline

```
  ingest surfaces
          |
   [01] Ingest & Normalize          typed graph, every edge tagged
          |                          validated / observed / inferred
   [02] Path Extraction             keep validated only, enumerate entry -> objective
          |
   [03] Intervention Synthesis      each candidate change -> the edge set it removes
          |
  ======= PIVOT =======             above: handling evidence
          |                         below: making a claim
   [04] Coverage Matrix             M[i][p] = 1 if intervention i severs path p
          |
   [05] Frontier Solve              ILP at each budget level -> non-dominated portfolios
          |
   [06] Robustness Sweep            resample assumed costs -> band + invariant core
          |
   [07] Bypass Hypotheses           substitution search -> ranked test queue
          |
   [08] Render                      one chart, one table, one queue
```

Everything above the pivot can be wrong in ways a reviewer can see and correct. Everything below
it is arithmetic on a single matrix.

---

## The optimization

Given a graph `G = (V, E)`, entry nodes `S`, weighted objectives `T` with weights `w_t`,
validated path set `P`, and an intervention catalog `I` where intervention `i` removes edge set
`R_i` at cost `c_i`:

**Full severance** — minimize cost subject to every validated path being cut:

```
minimize    sum_i c_i * x_i
subject to  sum over {i : R_i intersects p} of x_i  >=  1     for every p in P
            x_i in {0,1}
```

**Budgeted severance** — maximize severed weight under a budget `B`:

```
maximize    sum_p w_p * z_p
subject to  sum_i c_i * x_i <= B
            z_p <= sum over {i : R_i intersects p} of x_i      for every p in P
            x_i, z_p in {0,1}
```

### Complexity, both halves

This is **not** minimum s-t cut. Min-cut is polynomial, and it would be the right model if each
edge were independently removable at its own price. It is not that problem, because a single
intervention removes an arbitrary *set* of edges.

- Formulation 1 is **weighted set cover** over the path set. NP-hard. Greedy gives `1 + ln |P|`.
- Formulation 2 is **budgeted maximum coverage**. NP-hard. Greedy gives `1 - 1/e`.

**And it does not bind at the real instance size.** Validation is expensive, so only proven
paths get reported: `|P|` lands in the tens and `|I|` around 100. Exact ILP returns in
milliseconds there. Lumon runs the exact solver by default, falls back to greedy only above a
configurable threshold, and always reports which mode produced a result.

Both halves matter. Stating only the hardness overstates the difficulty; stating only the
practical speed hides where the boundary sits.

---

## Why a frontier, not a single answer

Lumon does not report one optimum. It sweeps the budget from zero upward, solves the budgeted
ILP at each level, and keeps the non-dominated portfolios. Each point on the resulting curve is
a *portfolio* — a set of interventions optimal at that budget — not a single fix.

The curve's **knee** is the deliverable: *three interventions get you 81% of weighted validated
paths, the next seven get you the remaining 19%.*

The two halves of that curve are labeled in the vocabulary a security team already uses. At or
below the knee is the **tourniquet**: cheap, fast, containment, compensating controls. Past it
is the **hardening plan**: architectural, durable, expensive. Same computation either way — the
split just names the choice the reader is actually making.

A **robustness sweep** then resamples the assumed cost tiers across their plausible range and
reports the band around the curve plus the **cost-invariant core**: the interventions that stay
in the optimal portfolio no matter how implementation difficulty is weighted. That is the
strongest honest claim available. Not "this is the cheapest fix," but "this intervention is
optimal across every weighting we tested."

---

## Where AI is and is not allowed

**Allowed, upstream, behind a human review gate:**

- Extracting typed edges from narrative text such as transcripts and reports
- Proposing candidate interventions, to widen the set the solver chooses from
- Predicate normalization on messy source text

**Allowed, downstream of a decision already made:**

- Writing up an explanation of a result the solver already produced

**Forbidden, always:**

- Choosing which interventions go in the solution
- Ranking or scoring by cost
- Asserting that a bypass path exists

---

## Honest limitations

These are structural. They are stated in the output, not just here.

1. **A cut over validated paths is not a cut over all paths.** Validation is a sample of
   reachability, not a census. Every claim Lumon emits is scoped to *validated reachability*.
   Any string in the codebase that drops that qualifier is a bug.
2. **Cost weighting is partly assumption.** Mitigated by provenance labels and the robustness
   sweep. Not solved. A ranked table must not imply otherwise.
3. **Bypass hypotheses are unvalidated by construction.** They are a test queue, not findings.
   Never phrased as paths that exist.
4. **Intervention side effects are out of model.** Lumon does not know that downscoping a
   principal breaks a vendor integration. The `side_effects_declared` field holds
   customer-supplied constraints; the model cannot discover them.
5. **Hypothesis ranking quality cannot be honestly self-evaluated.** Recall against synthetic
   graphs with seeded bypasses shows the ranking logic works on graphs we built, and nothing
   more. Only a real attacker validating the queue can say more than that.

---

## Status

**Pre-scaffold.** This repository currently contains documentation only — no package, no
`pyproject.toml`, no `Makefile`. The build proceeds as 19 sequenced tasks; task 01 lays down the
tooling described below. Until then, the commands in the next section describe the intended
interface rather than something you can run today.

---

## Install

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/annorak/lumon.git
cd lumon
make install
```

## Running the checks

```bash
make check        # lint + typecheck + test — the gate everything else trusts
```

Individually:

| Command | What it does |
|---|---|
| `make lint` | `ruff` lint and format check, line length 100 |
| `make format` | `ruff` format, in place |
| `make typecheck` | `mypy` in strict mode |
| `make test` | `pytest` with coverage reported to the terminal |
| `make clean` | remove build, cache, and coverage artifacts |

The verification harness is the part that makes the rest credible: property-based tests generate
random attack graphs and intervention catalogs, run the solver, then assert that the returned
set actually disconnects every entry from every objective, and that on instances small enough to
brute-force no cheaper valid set exists. If those tests fail, nothing downstream should be
trusted.

---

## Tech stack

Fixed. Substitutions are a discussion, not a default.

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Package manager | `uv` |
| Graph | `networkx` |
| Exact solver | `ortools` CP-SAT |
| Fallback solver | greedy, pure Python, with the approximation bound reported |
| Schema | `pydantic` v2 |
| Arrays | `numpy` |
| Templating | `jinja2` |
| CLI | `typer` |
| Tests | `pytest`, `pytest-cov`, `hypothesis` |
| Lint / format | `ruff` |
| Types | `mypy` (strict) |

---

## Repo layout

```
lumon/
  src/lumon/
    model/          domain types: nodes, edges, graph, paths, interventions
    io/             load, save, validate, networkx adapter
    generate/       synthetic attack graph generator
    paths/          path extraction
    interventions/  synthesis + cost model
    coverage/       the coverage matrix
    solve/          brute force, greedy, ILP
    analysis/       frontier sweep, robustness sweep
    hypotheses/     bypass hypothesis generation
    normalize/      predicate normalization + archetype collapse
    report/         jinja templates + renderer
    cli/            typer app
  tests/
    unit/
    property/
    fixtures/
  fixtures/
    armadin/        hand-encoded public kill chains
  docs/
  CHANGELOG.md
  pyproject.toml
```

---

## Data model

**Node types:** `Asset`, `Service`, `Identity`, `Credential`, `Boundary`, `Vulnerability`,
`Objective` (weighted), `EntryPoint`.

**Edge types**, all attacker transitions: `REACHES`, `EXPLOITS`, `EXECUTES_AS`, `READS`,
`AUTHENTICATES_AS`, `CAN_ACCESS`, `ESCAPES`.

Every edge carries an `evidence` field — `validated`, `observed`, or `inferred`. That separation
is load-bearing. It is the reason the optimizer's output stays provable while the hypothesis
output stays honestly labeled.

An **intervention** is not a node. It is a named change that removes a set of edges, with a cost
tier and a provenance label on that tier:

```yaml
- id: INT-014
  name: "Downscope service account sa-workflow-07"
  class: identity_permission_reduction
  removes_edges: [E-221, E-222, E-238, E-401]
  cost:
    tier: medium            # low | medium | high
    source: assumed_default # assumed_default | operator_supplied | customer_supplied
    justification: "Default for identity permission changes on a shared workload."
  side_effects_declared: false
```

Because one intervention removes many edges, this is set cover rather than min-cut. That single
structural fact is what the complexity section above is about.

---

## Not in scope

Considered and cut. The reasons matter more than the list.

- **No attacker, no swarm, no exploit execution.** A faked attacker is worse than no attacker.
- **No continuous regression loop.** The value there is targeted re-attack, which needs a swarm.
- **No detection efficacy scoring, kill chain reproduction, or model routing.**
- **No coverage or information-gain planner.** It needs ground truth about an environment's true
  attack graph to measure against, and we do not have it.
- **No dashboard, auth, multi-tenancy, or UI beyond a static report.** None of it changes whether
  the core result is correct.

The unifying rule: every component is either provably correct or clearly labeled as a hypothesis.
Anything that requires trusting a simulation we authored does not ship.

---

## Contributing

Read `CHANGELOG.md` for what has landed and in what order. Every change ends with a plain-English
changelog entry written for a junior engineer who has not read the design doc.

Design and planning material lives outside version control by intent and is not distributed with
this repository.
