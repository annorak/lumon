# Changelog

---

## Repository initialization — README and .gitignore

**What changed in plain English**

This is the first thing in the repo. Before this commit the directory held nothing but a folder
of planning documents, and there was no way for someone landing on the GitHub page to tell what
this project is.

There are now three files. `README.md` explains what Lumon does — it takes attack paths that
someone actually proved were exploitable, and works out the cheapest set of changes to the
environment that breaks all of them. The README also spells out the four rules the whole project
lives by, because those rules constrain the code you are about to write, not just the marketing.
The short version: only evidence marked `validated` is allowed to affect the answer; every cost
number says out loud whether a human gave it to us or we made it up; anything we guessed at is
called a hypothesis and never a finding; and no language model is allowed to pick, rank, or score
anything.

`.gitignore` covers the usual Python, `uv`, coverage, and editor noise, and one project-specific
thing: the planning material. The design doc, the implementation plans, and the agent preamble used to
sit in a folder called `files/`. That folder is now `.private/` and is ignored. It stays on the
author's machine and is not distributed with the repo. If you cloned this and are wondering where
the design doc went, that is where — ask for it directly.

`CHANGELOG.md` is this file, started here to record future changes.

No code exists yet. The repo does not install, lint, type check, or test, because there is no
package and no `pyproject.toml`. The repository scaffold will add all of that. The install and `make check`
instructions in the README describe the planned interface, and the README says so
plainly in its Status section rather than implying you can run them today.

**New things you can now do**

- Understand what the project is, and what it deliberately refuses to do, from the repo alone
- Clone the repo without dragging the private planning material along with it
- Append a change entry to a changelog that already exists

**Files added or changed**

- `README.md` — what Lumon is, the optimization it solves, the honest limitations, the tech stack
- `.gitignore` — Python, `uv`, coverage, and editor artifacts, plus `.private/`
- `CHANGELOG.md` — this file
- `files/` renamed to `.private/` — the planning material, now untracked

**Not done yet**

- Everything. There is no Python package, no dependencies declared, no `Makefile`, and no CI.
  The scaffold will provide those pieces and add its own entry below this one.
- The README links no design doc, because the design doc is intentionally not in the repo.

---

## Repo scaffold and tooling

**What changed in plain English**

There is now a real Python project here. Before this, the repo was three documents. Now it
installs, lints, type checks, runs tests, and reports coverage, and it does all of that in one
command.

To get started, you need Python 3.12 and [`uv`](https://docs.astral.sh/uv/) on your machine.
Then `make install`, and you are done — `uv` creates the virtual environment, reads
`pyproject.toml`, installs everything including Lumon itself in editable mode, and writes
`uv.lock` so that your machine and CI resolve to byte-identical versions. You do not activate
anything; every `make` target runs through `uv run`, which finds the environment for you.

`make check` is the one command that matters. It runs three things in order and stops at the
first failure: `ruff` for lint and format, `mypy` in strict mode, and `pytest` with coverage.
Later changes will run `make check` and trust the result, so the
settings are deliberately unforgiving. `mypy` is strict, which means every function you write
needs type annotations including the return type, and that applies to test functions too — a
test that says `def test_thing():` will fail type checking until you write
`def test_thing() -> None:`. That catches real bugs and it is much cheaper to accept now than to
retrofit later.

The package skeleton exists as thirteen empty importable packages — `model`, `io`, `paths`,
`solve`, and so on — one per stage of the pipeline. They contain nothing but an `__init__.py`.
That is on purpose: the directory layout is fixed by the project context, and having it in place
means new code has a defined home.

One number to know about: the coverage gate is set to `--cov-fail-under=0`, not 90. There are
two lines of real code in the whole repo right now, so a 90% gate would fail the build for no
useful reason. A comment in `pyproject.toml` records the plan to raise it to 90 when the
domain model arrives. It should not come back down after that.

**New things you can now do**

- `make install` — create the environment and install everything from a clean checkout
- `make check` — lint, type check, and test in one command; this is the gate
- `make lint`, `make typecheck`, `make test` — run any one of the three on its own
- `make format` — reformat and auto-fix in place
- `make clean` — remove build, cache, and coverage artifacts
- `import lumon` and every `lumon.<subpackage>`, all importable, all empty
- Push or open a pull request and have GitHub Actions run `make check` on Python 3.12

**Files added or changed**

- `pyproject.toml` — dependencies, and all config for ruff, mypy, pytest, and coverage
- `Makefile` — the seven targets above
- `.github/workflows/ci.yml` — runs `make check` on push to `master` and on every pull request
- `.python-version` — pins the project to 3.12 so `uv` picks the right interpreter
- `src/lumon/__init__.py` — exposes `__version__ = "0.1.0"`
- `src/lumon/{model,io,generate,paths,interventions,coverage,solve,analysis,hypotheses,normalize,report,cli}/__init__.py` — the empty pipeline packages
- `tests/unit/test_smoke.py` — imports the package, asserts the version string
- `uv.lock` — committed on purpose
- `README.md` — Status section updated from "pre-scaffold" to what actually exists now
- `docs/`, `fixtures/armadin/`, `tests/fixtures/` — created with `.gitkeep`, since git does not
  track empty directories

**Not done yet**

- No product logic of any kind. No graph, no paths, no interventions, no solver. The domain
  model is next.
- Coverage gate is at 0 and will rise to 90 with the domain model.
- CI has never actually run — the workflow file is valid YAML and the same `make check` passes
  locally on macOS, but the first push is the first time it executes on Linux.
- `docs/` and `fixtures/armadin/` are empty placeholders. Source-backed fixture work will fill them.

---

## Core domain model

**What changed in plain English**

The repo now has a vocabulary. Later code manipulates the three types added
here: a `Node` (a thing an attacker interacts with — an asset, a service, an identity, a
credential, a boundary, a vulnerability, an entry point, or an objective), an `Edge` (one
transition the attacker makes from one node to another), and an `AttackGraph` (a bag of nodes
and edges plus a little metadata). They are Pydantic models, so they validate themselves and
they load and save as JSON without anyone writing a parser.

The part worth actually reading is the **evidence tag**. Every edge carries one of three
values, and which one it carries decides what that edge is allowed to influence.

`VALIDATED` means the attacker performed this transition and it was reproduced. This is the
only value the solver is ever allowed to look at. Path enumeration, the coverage matrix, the
cost frontier, the "you severed 81% of weighted paths" number — all of it is computed over
validated edges and nothing else. `OBSERVED` means someone saw it during reconnaissance but
never actually did it: a port answered, a role exists, a secret is mounted. `INFERRED` means
a rule asserted it — "this role has that permission, so this should work" — and nobody looked.

Why three levels instead of a boolean? Because the two weaker ones are not garbage, they are
just a different kind of claim. They are the raw material for bypass hypotheses later on: the
routes an attacker would probably try next after you apply a fix, which is a queue of things
to go test. What they must never do is quietly become part of an answer. If an `OBSERVED` edge
could sneak into the solver, Lumon would be telling a customer "this path is now severed"
based on something nobody ever proved was there in the first place, and the entire pitch —
that everything we claim can be checked by someone who does not trust us — collapses. So the
tag is not documentation. It is a filter that every stage downstream is required to apply, and
`validated_edges()` on the graph is the accessor that does it. There is a long docstring on
`Evidence` in `src/lumon/model/enums.py` stating exactly what each level may and may not touch;
read that one before writing anything that consumes edges.

Two smaller decisions. First, the models are **frozen**: once you build a node you cannot
reassign its fields. That kills a whole family of bugs where some analysis stage quietly edits
the graph it was handed and the stage after it computes something different. Second, unknown
fields are **rejected** rather than ignored, so a typo like `"evidance": "validated"` in an
input file fails loudly instead of silently defaulting.

One thing this change deliberately does *not* do: it does not check that an edge's `source` and
`target` actually exist in the node list. A graph full of dangling edges constructs happily.
That is on purpose — ingest assembles a graph as evidence arrives and needs to hold partial
state — and there is a test asserting it stays that way. Graph validation will decide whether a graph is
usable.

**New things you can now do**

- Build a typed attack graph in Python, or load one from JSON, with validation for free
- Serialize a graph to JSON and read it back and get an equal object
- Ask a graph for its entry points, its objectives, its nodes or edges of a given type, or a
  node or edge by id
- Ask a graph for only its validated edges, which is the filter every later stage depends on

**Files added or changed**

- `src/lumon/model/enums.py` — `NodeType`, `EdgeType`, `Evidence`, with the evidence rules
  written out in the docstring
- `src/lumon/model/graph.py` — `Node`, `Edge`, `AttackGraph`, their validation, and the lookups
- `src/lumon/model/__init__.py` — re-exports the six public names; import from here, not from
  the submodules
- `tests/unit/test_model_graph.py` — 18 tests over a six-node kill chain shaped like the one in
  the design doc
- `pyproject.toml` — coverage gate raised from 0 to 90 now that there is real code to cover

**Not done yet**

- Nothing loads a graph from a file yet, nothing checks that a graph makes sense, and nothing
  converts it to NetworkX. Graph loading and validation will add those pieces.
- `Path`, `PathSet`, and the intervention types are not here. Path extraction and intervention synthesis will add them to this
  same `model/` package.

---

## Graph I/O and invariants

**What changed in plain English**

The domain model gave us types you could build in Python. This change lets a graph come from a file, and
answers the question you have to answer before any analysis touches it: *is this graph
actually usable?*

Three things landed. `load_graph` and `save_graph` read and write an attack graph as indented
JSON. `export_json_schema` writes out the JSON Schema for `AttackGraph`, so somebody building
a tool outside this repo can generate input Lumon will accept without reading our Pydantic
models. And `to_networkx` converts a graph into the NetworkX structure the path enumerator and
everything after it will run on.

The part worth reading is the invariant checker, and specifically the fact that it **returns a
report rather than throwing**. That looks like the wrong choice until you look at what failure
actually looks like here. Say an edge's target is `n_clod` and the author meant `n_cloud`.
Nothing crashes. The file is valid JSON, it is valid against the schema, every field is the
right type, and it loads fine. What happens is that the path from the internet-facing service
to the cloud account quietly stops existing, the solver severs the paths it was handed, and the
final report tells a customer they have fewer attack paths than they really do. Under-reporting
risk is the single worst thing this system can do — worse than crashing, because a crash gets
noticed. So `check_invariants` collects *every* problem in one pass and hands the whole list
back, and the caller decides what to do with it and can show that list to whoever supplied the
graph. `assert_usable` is there for callers that do want to stop dead; it raises with all the
errors formatted.

There are ten checks. Six are errors, meaning analysis over this graph would be wrong: the
three flavours of dangling reference (source, target, `enabled_by`), and the three ways a graph
can have nothing to analyse (no entry points, no objectives, no validated edges). Four are
warnings, meaning it will analyse fine but probably is not what the author meant: a node no
edge mentions, an objective nothing validated reaches, an entry point nothing validated leaves,
and an `enabled_by` pointing at something that is not a vulnerability or a credential. Warnings
never block. `is_usable` is true as long as there are no errors.

`to_networkx` builds a `MultiDiGraph`, not a `DiGraph`, and that is deliberate. One pair of
nodes can be joined by more than one transition — a service account can both `reaches` and
`can_access` a cloud account — and those are two different edges with two different fixes
available against them. A `DiGraph` would keep one and silently drop the other, and the solver
would end up choosing from a catalog that is missing an option. `valid_small.json` has exactly
that shape, and there is a test asserting both edges survive.

**New things you can now do**

- Load an attack graph from a JSON file, and save one back out, with the round trip proven equal
- Export the JSON Schema so an external tool can produce input we will accept
- Ask a graph what is wrong with it and get a structured list back, with a severity and the id of
  the offending node or edge on each item
- Assert a graph is usable and get a single exception listing every error, if you want the strict
  behaviour
- Convert a graph to NetworkX, optionally filtered to validated edges only

**Files added or changed**

- `src/lumon/io/loader.py` — `load_graph`, `save_graph`, `export_json_schema`, `GraphLoadError`
- `src/lumon/io/invariants.py` — the ten checks, `Severity`, `Violation`, `InvariantReport`,
  `check_invariants`, `assert_usable`, `GraphInvariantError`
- `src/lumon/io/nx_adapter.py` — `to_networkx`
- `src/lumon/io/__init__.py` — re-exports the eleven public names; import from here
- `tests/conftest.py` — the `graphs_dir` fixture pointing at the hand-written graphs
- `tests/fixtures/graphs/valid_small.json` — eight nodes, two validated paths, zero violations
- `tests/fixtures/graphs/dangling_edge.json` — the `n_clod` typo, as a file you can look at
- `tests/fixtures/graphs/no_objective.json` — well-formed, but nothing worth reaching
- `tests/unit/test_io_loader.py`, `tests/unit/test_invariants.py`, `tests/unit/test_nx_adapter.py`
  — 26 tests, one per violation code
- `pyproject.toml` — the mypy override for `networkx`, which ships no type information

**Not done yet**

- Nothing enumerates paths through the graph. `to_networkx` is ready for path extraction, but no code
  walks entry to objective yet.
- Nothing calls `assert_usable` anywhere, because there is no pipeline and no CLI yet. The CLI will
  wire it in at the boundary where a graph is loaded.
- No generator, so every graph in the repo is hand-written. Synthetic graph generation is still to come.

---

## Synthetic attack graph generator

**What changed in plain English**

Every graph in the repo up to now was hand-written, and there were three of them. That does not
carry us far. Generated solver checks need hundreds of randomly shaped graphs to check
the answers, and nobody is hand-writing hundreds of graphs. So this change adds a generator: give it
a seed and a shape, and it hands back an attack graph.

The interesting part is the second thing it hands back. Alongside the graph comes a `GroundTruth`
object saying what the answers are — every attack path in the graph, which nodes every path is
forced through, and what each objective is worth. And the generator knows all of that **because it
built the graph that way**, not because it went and looked afterwards.

That distinction is the whole point of this change, so it is worth being clear about. Suppose we had
written the generator the lazy way: scatter some nodes and edges around, then run our own path
enumerator over the result and write down whatever it said. The tests would look identical, and
they would be worthless — if our path enumerator had a bug that missed a path, it would miss that
path when generating the expected answer too, and the test would happily pass. The tests would be
marking their own homework. So the expected answer has to come from somewhere the code under test
cannot reach.

The way out is to build the graph in a shape where the answer is forced. Every generated graph is
a stack of layers: entry points on the bottom, then some middle layers, then the objectives on
top. Every node in a layer connects to every node in the next one, and a validated edge never goes
anywhere else — not sideways, not backwards, not skipping a layer. Once that is true, an attack
path is just "pick one node from each layer," and the complete list of paths is every combination.
No searching involved. A chokepoint is even simpler: squeeze one middle layer down to a single
node, and every path has no choice but to go through it. That is what `n_planted_chokepoints` does.

The generator also sprinkles in some `observed` and `inferred` edges — routes that were seen but
never actually exercised. These are decoys. They exist so that later stages have something to trip
over, and to supply raw material for bypass hypotheses. They are placed carefully: a
decoy always runs forward through the layers, to somewhere the validated edges could already get
to anyway. That guarantees it adds no new reachability of its own, which is why we can promise
that filtering the graph down to validated edges leaves you with exactly the paths in the ground
truth and nothing else.

**New things you can now do**

- Generate a reproducible attack graph of a chosen size and shape from a seed
- Get the correct answers for that graph handed to you alongside it
- Pick one of six ready-made shapes by name instead of choosing parameters yourself
- Regenerate any saved graph exactly, since the parameters that made it are recorded inside it

**Files added or changed**

- `src/lumon/generate/params.py` — `GeneratorParams`, the knobs and their validation
- `src/lumon/generate/truth.py` — `GroundTruth`, the answers that ship with the graph
- `src/lumon/generate/generator.py` — `generate(params)`, the layered construction
- `src/lumon/generate/presets.py` — `TINY`, `SMALL`, `MEDIUM`, `REALISTIC`, `WIDE`, `DEEP`, and
  the `PRESETS` dict that holds all six
- `src/lumon/generate/__init__.py` — re-exports the public names; import from here
- `tests/unit/test_generator.py` — 54 tests, including the one that re-derives the path set with
  NetworkX and checks it against what the generator claimed

**Not done yet**

- Nothing consumes these graphs yet. Path extraction is next, and its key test is that the
  paths it finds match `GroundTruth.path_node_sequences` exactly, for every preset.
- The generator makes no vulnerability or credential nodes and sets no `enabled_by` on anything,
  so the synthesis rules keyed to those will not fire on a generated graph. They get
  tested against hand-built graphs instead.
- No graphs are checked into the repo from this. Everything is generated on demand in tests, since
  a seed and a parameter set reproduce a graph exactly.

## Path extraction

**What changed in plain English**

Up to now we had graphs and nothing that read them. This change adds the step that turns a graph
into the thing the rest of the system actually works on: the list of attack paths. A path is one
route from an entry point to an objective — "the internet-facing service, then the service
account, then the credential sitting on disk, then the cloud account." Everything after this
point counts paths, weights paths, or tries to break paths, so this is where that list gets made.

The rule that matters most here is that **only validated edges are allowed to produce a path**.
Every edge in a graph carries a tag saying how well it is backed by evidence: `validated` means
somebody actually performed that transition and it was reproduced, `observed` means it was seen
during recon but never exercised, and `inferred` means a rule asserted it. Extraction throws
away the second two entirely before it starts walking. That is not a tidiness thing. Lumon's one
promise is that a person who does not trust us can check every claim it makes, and the moment an
unproven edge can put a path into the answer, the whole output becomes "here is a fix for a route
we think might be there." The observed and inferred edges are not deleted, they are just held
back as raw material for bypass hypotheses, which are explicitly a queue
of things to go and test rather than findings.

The second thing worth understanding is why the caps are loud. Enumeration is capped at 5,000
paths by default, because a badly shaped graph can produce astronomically many. If we hit that
cap and quietly handed back the first 5,000 of 8,000 paths, the report would go on to say "these
three fixes sever everything" while 3,000 paths nobody looked at sat there untouched. So when the
cap bites, the returned `PathSet` sets `truncated=True` and carries a `truncation_reason` naming
the cap and the entry-objective pair it was working on at the time. A caller can always tell, and
`PathSet` refuses to be built with `truncated=True` and no reason.

There is one subtlety in what counts as a distinct path. Two nodes can be joined by more than one
validated edge — an identity that both `reaches` and `can_access` a cloud account is two separate
attacker techniques that happen to start and end in the same place. Those are two paths, not one,
because an intervention might remove one and leave the other standing. So the search runs over
edge sequences rather than node sequences, and two paths in the output can have identical node
lists and different edge lists.

`summarize()` is a small extra: it gives you a one-line read on a path set — how many paths, how
many entries and objectives they touch, how long they are, and which single edge shows up on the
most paths. That last number is a preview of the chokepoint structure the solver will find
properly later. It is a sanity check for a human, not an input to anything, and nothing is ranked
or chosen from it.

**New things you can now do**

- Turn an attack graph into the complete set of validated entry-to-objective paths
- Tell, from the result alone, whether the enumeration finished or gave up partway
- Group paths by the objective they reach, total their weight, or get their weights keyed by id
- Get a quick sanity summary of a path set, including the busiest edge in it

**Files added or changed**

- `src/lumon/model/path.py` — `Path` and `PathSet`, the models everything downstream counts
- `src/lumon/paths/extract.py` — `extract_paths(graph, max_paths, max_depth)`, the enumeration
- `src/lumon/paths/stats.py` — `PathStats` and `summarize(path_set)`, the sanity read
- `src/lumon/paths/__init__.py` — re-exports the public names; import from here
- `src/lumon/model/__init__.py` — now also exports `Path` and `PathSet`
- `src/lumon/model/graph.py` — `_reject_duplicate_ids` renamed to `reject_duplicate_ids` so
  `PathSet` can reuse it instead of copying the same four lines
- `tests/unit/test_model_path.py` — the models on their own
- `tests/unit/test_path_extraction.py` — extraction, including the run against every generator
  preset's ground truth
- `tests/unit/test_path_stats.py` — the summary

**Not done yet**

- Nothing proposes fixes yet. Intervention synthesis will build the catalog — the candidate
  changes, each with the set of edges it removes and a cost carrying a label saying whether a
  human supplied that cost or we assumed it.
- Path extraction does not check graph invariants before it runs. Intervention synthesis does:
  an unusable exploit edge could otherwise produce a catalog that cannot sever every supplied
  route. The CLI will also check at the boundary.
- The observed and inferred edges that extraction discards are not stored anywhere for later.
  Bypass generation will re-read them from the graph.

## Intervention model and synthesis

**What changed in plain English**

Up to now Lumon could list the attack routes Armadin supplied, but it could not describe a
change that would break one. This change adds that missing half. An intervention is one
customer change, such as patching a vulnerability, removing an exposed credential, or
reducing an identity's permissions. It records every validated graph edge that change
would remove.

One intervention can remove several edges. If three kill chains all use the same
over-permissioned identity, reducing that identity's permissions is one change that can
break all three chains. The coverage matrix will turn these removal sets into the grid the optimizer
uses to compare one shared change against many isolated fixes.

Every cost now says who supplied it and why. The built-in low, medium, and high costs are
assumptions, not measurements of a customer's environment, so synthesized interventions
say `assumed_default`. A customer or operator can replace those assumptions through a
JSON or YAML override without changing what the intervention removes.

Synthesis uses validated edges only. It also refuses a graph when a validated exploit
does not name the vulnerability that enabled it. Continuing would leave an attack step
without a patch candidate and could make a later answer look complete when it was not.

**New things you can now do**

- Generate a deterministic catalog of customer changes from validated attack transitions
- See exactly which validated edges each proposed change removes
- Distinguish assumed implementation costs from operator-supplied and customer-supplied costs
- Replace assumed costs from a JSON or YAML file

**Files added or changed**

- `src/lumon/model/intervention.py` — the change, removal-set, and cost-provenance models
- `src/lumon/model/__init__.py` — exports the intervention models
- `src/lumon/interventions/defaults.py` — the documented assumed cost tiers
- `src/lumon/interventions/synthesize.py` — the deterministic edge-to-change rules
- `src/lumon/interventions/overrides.py` — JSON and YAML cost override loading
- `src/lumon/interventions/__init__.py` — exports the intervention functions and defaults
- `src/lumon/io/invariants.py` — rejects unusable exploit and boundary references
- `tests/unit/test_intervention_model.py` — checks models, costs, and stable serialization
- `tests/unit/test_synthesize.py` — checks every synthesis rule and validated-only behavior
- `tests/unit/test_overrides.py` — checks loading, replacement, and invalid overrides
- `tests/unit/test_invariants.py` — checks the graph requirements for intervention synthesis
- `pyproject.toml` and `uv.lock` — add typed YAML support
- Private intervention specification: records the clarified synthesis rules
- Private bypass-hypothesis plan: keeps future route substitution on the same
  boundary-crossing rule
- Private source-fixture plan: records how real transcripts must encode crossings

**Not done yet**

- Nothing selects the best interventions yet. The coverage matrix will connect interventions to paths,
  and the solvers and frontier analysis will choose portfolios and build the cost-versus-coverage frontier.
- `SERVICE_REMOVAL` is modeled, but automatic synthesis does not propose removing a service.
- Lumon records whether side effects were declared, but it cannot discover which
  legitimate workloads a change might break.

## Coverage matrix

**What changed in plain English**

Up to now Lumon had one list of validated attack paths and another list of proposed
environment changes. Nothing directly connected the two. This change adds that connection.

The coverage matrix is a grid. Each row is one proposed change, each column is one
validated attack path, and a cell is 1 when that change removes an edge used by that path.
Every calculation from here on is arithmetic on this grid. The later solvers will choose
rows that cover the most useful columns for the lowest cost.

Some paths may have an all-zero column because no proposed change can sever them. Lumon
reports those paths and their total weight, and says full severance is impossible. It does
not hide them or pretend the remaining paths are the whole result.

The grid stores positions, so row 0 and column 0 only have meaning when paired with the
original intervention and path lists. Lumon now records a repeatable fingerprint of those
inputs and rejects the matrix if their order, edge sets, weights, or costs change. Matrix
construction also rejects path or intervention edges that are not validated edges in the
supplied graph.

**New things you can now do**

- Build the intervention-by-path grid used by every later calculation
- Ask which validated paths a proposed change severs, and which changes sever a path
- Find uncoverable paths, redundant changes, and changes dominated by a cheaper alternative
- Calculate covered path weight without counting an overlapping path twice
- Reject stale matrices before their positions can be interpreted incorrectly

**Files added or changed**

- `src/lumon/coverage/matrix.py` — builds the grid, answers coverage queries, and guards
  its positional inputs
- `src/lumon/coverage/report.py` — summarizes coverage, uncoverable paths, and catalog noise
- `src/lumon/coverage/__init__.py` — exports the coverage API
- `tests/unit/test_coverage_matrix.py` — checks a hand-computed grid, stale inputs, edge
  references, empty cases, and the generated pipeline

**Not done yet**

- Nothing chooses an intervention portfolio yet. Reference solvers are next.

## Reference solvers

**What changed in plain English**

Lumon can now choose sets of proposed changes in two ways. The brute-force solver tries
every possible set and returns the best one. The greedy solver makes one quick choice at
a time and exists as the fallback for inputs too large for exact solving.

Brute force is deliberately slow. It is the answer key that generated verification will use to check the
fast production solver on small examples. Without an independent answer key, two solvers
could share the same bug and agree with each other for the wrong reason.

The easy trap is assuming that the best answer contains the fewest changes. Three LOW-cost
changes cost `3`, so they are cheaper than one HIGH-cost change costing `9`. Brute force
therefore checks every set instead of stopping when it finds the first full cover.

Each result says whether it is exact, approximate, or not proven either way. The original
specification overstated the budgeted greedy guarantee. The simple fallback covers at least half of
the stronger `1 - 1/e` bound, not the full bound, so its reported ratio now says exactly
that. Full-cover greedy counts newly broken paths rather than their weights because every
path must be broken in that formulation.

**New things you can now do**

- Find the exact cheapest set of changes for instances with at most 20 interventions
- Find the exact maximum path weight that can be severed within a budget on those instances
- Get a fast deterministic fallback with an explicit approximation guarantee
- Trace every solution back to the coverage matrix that produced it

**Files added or changed**

- `src/lumon/solve/solution.py` — records a portfolio, its coverage, and what the solver can prove
- `src/lumon/solve/brute_force.py` — exhaustively checks every small portfolio
- `src/lumon/solve/greedy.py` — provides the deterministic large-instance fallback
- `src/lumon/solve/__init__.py` — exports the solver API
- `tests/unit/test_solution_model.py` — checks guarantee and ratio validation
- `tests/unit/test_brute_force.py` — proves the answer key against hand-computed cases
- `tests/unit/test_greedy.py` — checks bounds, budgets, tie-breaking, and both corrected regressions
- `.private/00-design-doc.md` — corrects the general-cost budgeted coverage guarantee
- `.private/02-PROJECT-CONTEXT.md` — keeps the permanent solver summary mathematically honest
- Private reference-solver plan: records the clarified solver contract

**Not done yet**

- The production-solver plan adds CP-SAT and dispatches large inputs to greedy.
- Generated verification will check the exact solver against brute force across generated examples.

## Production solver plan simplified

**What changed in plain English**

The production plan now uses one solver, CP-SAT, for every request. A solver chooses which
environment changes to make. The earlier plan switched to a simpler greedy algorithm for
large inputs. Removing that switch gives us fewer algorithms and configuration choices to
maintain.

Every solve will have a time limit. If CP-SAT proves the answer is best, the result says
`EXACT`. If it finds a valid answer but runs out of time before proving that, the result
says `UNKNOWN` and explains the limit. If it finds no answer, the call raises an error.
A valid but unproven answer must never be presented as the cheapest or best possible one.

Brute force stays as an independent answer key in shared test code. Generated verification will compare
CP-SAT with that answer key for both questions: the cheapest way to sever every validated
path, and the most path weight that can be severed within a budget. The revised plan
removes greedy entirely, including its tests and approximation fields.

This entry records a documentation change. The original reference-solver Python code is still
present. The production-solver work now includes moving brute force into tests, deleting greedy,
simplifying the result model, and implementing CP-SAT. The original reference-solver changelog
entry remains above as a record of what was built at that time.

**New things you can now do**

- Follow one consistent production solver plan across the project and future changes
- Distinguish a proven optimum, a feasible unproven result, and a failure to find a result
- Review the required comparisons for both formulations against one shared test answer key

**Files added or changed**

- `README.md` — current library status and the planned production behavior
- `.private/00-design-doc.md` — solver policy, test role, and limits on optimality claims
- `.private/01-architecture.html` — replaces the obsolete solver note
- `.private/02-PROJECT-CONTEXT.md` — the production contract and revised code ownership
- Private implementation roadmap: revised feature names and the production-solver migration plan
- Private reference-solver plan: shared result model and test answer-key contract
- Private production-solver plan: code migration, CP-SAT calls, time limits, and status tests
- Private solver-verification plan: direct oracle comparisons for both formulations
- Private CLI plan: time-limit option, proof-status output, and solver error handling
- `CHANGELOG.md` — this entry, preserving the earlier implementation history

**Not done yet**

- The production-solver work must carry out the Python migration and implement CP-SAT.
- Generated verification must implement the revised checks after that migration.

## Test-only reference solver and simpler results

**What changed in plain English**

The reference-solver code now follows the simpler solver plan. Brute force moved into shared test
code, and the greedy solver and its tests were deleted. Production keeps the common
result type, which records the chosen changes, their cost, the validated paths they sever,
and whether the answer is proven best.

Results now support only `EXACT` and `UNKNOWN`. The approximation-ratio field and its
validation are gone. `UNKNOWN` still means a valid answer without a proof that it is best.
The production-solver work will add CP-SAT to produce answers.

The slow brute-force solver remains the independent answer key for both optimization
questions. It checks every set of changes because three cheap changes can cost less than
one expensive change. Tests also check that a tight budget favors greater total path
weight, overlapping fixes count each path once, and empty inputs have explicit results.

This completes the code cleanup previously planned alongside the production solver.
The remaining plans cover CP-SAT implementation and generated comparisons against
the shared answer key. Earlier changelog entries remain unchanged as history.

**New things you can now do**

- Import the same exact answer key from `tests.brute_force` in unit and property tests
- Serialize either supported guarantee and reject obsolete approximation fields
- Check weighted budget choices, empty inputs, overlapping coverage, and fingerprint notes

**Files added or changed**

- `tests/brute_force.py` — moved from production, with its 20-intervention cap
- `src/lumon/solve/greedy.py` — deleted
- `tests/unit/test_greedy.py` — deleted with the solver it tested
- `src/lumon/solve/solution.py` — removes approximation metadata and keeps shared result construction
- `src/lumon/solve/__init__.py` — exports only the shared result types and infeasibility error
- `tests/unit/test_brute_force.py` — uses the test reference and checks the remaining edge cases
- `tests/unit/test_solution_model.py` — checks both guarantees, validation, and serialization
- `README.md` — distinguishes the current library from the planned production solver
- Private design, project-context, and implementation-roadmap documents: remove the deferred
  production-solver migration
- Private reference-solver plan: assigns the simplified code and tests to that implementation
- Private production-solver plan: keeps the solver work without repeating this cleanup
- Private solver-verification plan: names the completed reference-solver prerequisites
- Private CLI plan: removes the obsolete solver-mode option test
- `CHANGELOG.md` — records the implementation change without rewriting earlier entries

**Not done yet**

- The production-solver work will implement CP-SAT, its time limit, and result-status handling.
- Generated verification will check both production formulations against brute force across generated inputs.

## CP-SAT production solver

**What changed in plain English**

Lumon can now choose environment changes with one production solver, CP-SAT. It answers
two questions: what is the cheapest set of changes that severs every validated attack
path, and which changes sever the greatest total path weight within a budget. Keeping
one solver makes the implementation simpler to maintain and gives later features one API.

Every solve has a time limit, defaulting to 30 seconds. A result marked `EXACT` means the
solver proved that its answer is best. A feasible answer at the time limit can still be
useful, but it is marked `UNKNOWN` because it is not proven best. If no answer has been
found, the call raises an error. If a validated path has no proposed fix, a request to
sever every path fails before solving and names the paths that cannot be severed.

Both optimization problems are NP-hard, so finding the best answer can become expensive
as inputs grow. We expect exact solving to be practical for tens of validated paths and
around 100 proposed changes. The performance test runs the existing realistic preset
through graph generation, path extraction, fix synthesis, and both solves in under one
second. That preset is one measured example, not a runtime promise for every environment.

The solver converts costs and optimization weights into integer thousandths. Values with
finer decimal precision are rejected instead of silently rounded. Budgets are never rounded
upward. Reported totals come from the original path and cost data, and a result that would
exceed the supplied budget raises an error. Tests compare both solver answers with an
independent answer key that tries every possible set of changes on small examples.

**New things you can now do**

- Find a proven cheapest portfolio that severs every validated attack path when feasible
- Find a proven maximum-weight portfolio within a supplied budget
- Set a finite time limit and distinguish a proven optimum from a feasible unproven answer
- Import both solver functions and `SolverError` directly from `lumon.solve`

**Files added or changed**

- `src/lumon/solve/ilp.py`: both formulations, numeric validation, time limits, and status handling
- `src/lumon/solve/__init__.py`: direct exports for the production functions and solver error
- `tests/unit/test_ilp.py`: independent answer comparisons, numeric boundaries, and all solver statuses
- `tests/unit/test_ilp_performance.py`: the realistic preset through the pipeline and both solves
- `CHANGELOG.md`: this entry

**Not done yet**

- Broader generated property checks against the independent answer key remain to be added.
- A budget sweep will produce the Pareto frontier.

## Demo release planning

**What changed in plain English**

Added a standalone plan for turning the existing solver into a small public
demonstration using the Kill Chains and Coffee transcripts. It covers checking
the source material, comparing the customer's fixes with Lumon's answer,
testing that answer, and producing the README, image, animation, and video.

The plan uses the existing solver that finds the cheapest set of changes
covering every supplied validated path. It does not require the later
cost-versus-coverage chart or the other deferred analysis features. It does
require a real, limited bypass queue, with every candidate clearly labeled
as something that still needs testing.

**New things you can now do**

- Give an implementation agent one plan containing the demo release
  requirements, review gates, evidence rules, and acceptance checks.

**Files added or changed**

- Private demo-release plan: the standalone implementation requirements.
- `CHANGELOG.md`: records this planning change.

**Not done yet**

- Transcript encoding, focused verification, the bypass queue, demo command,
  public media, README update, and release checks described in the new plan.
- Broader generated solver verification and later product features.

## Demo release source decisions

**What changed in plain English**

Updated the release plan to represent the single Fortune 600 route narrated
in the podcast. The 12 reported RCE findings stay a separate source count.
The other episodes retain the agreed distinctions between successful
routes, unsuccessful branches, and unresolved identities or route pairings.

The supplied evidence does not describe the customer's actual fixes.
The demo will report that limitation beside Lumon's computed result.
Customer costs, change counts, path coverage, and remaining access will
stay unknown. This prevents the demo from claiming savings it cannot check.

**New things you can now do**

- Follow a release plan that distinguishes reported remediation from
  a computed portfolio of proposed environment changes.

**Files added or changed**

- Private demo-release plan: records the source decisions and revised comparison.
- `CHANGELOG.md`: records this planning change.

**Not done yet**

- Fixtures, focused verification, bypass generation, demo command, media,
  README updates, fresh-run measurement, and public release checks.
- Broader generated solver verification, the full bypass-hypothesis rule set, and other deferred product features.
- The known fractional-budget issue remains unfixed.

## Demo release, Fortune 600 fixture

**What changed in plain English**

Added the one Fortune 600 attack route narrated in Episode 4. The graph
keeps the two exploited weaknesses and the stolen credential material
separate so proposed changes remove the correct steps.

Added short source excerpts and records connecting the graph to those
excerpts. Regression tests check the exact route and four approved changes,
including their assumed costs. They also check quotation matching and
source references. Human review still decides whether a quotation supports
the interpretation.

**New things you can now do**

- Load the Fortune 600 example and extract its single reviewed route.
- Trace its nodes, transitions, 12 reported findings, and remediation
  statement to the supplied excerpts from the episode.

**Files added or changed**

- `fixtures/armadin/graphs/episode4-fortune600.json`: the approved attack graph.
- `fixtures/armadin/sources/episode4-excerpts.txt`: selected source text.
- `fixtures/armadin/provenance/episode4-fortune600.json`: evidence and assumptions.
- `tests/unit/test_armadin_fixtures.py`: fixture and provenance regressions.
- `CHANGELOG.md`: records this stage.

**Not done yet**

- Other episode fixtures, the chain inventory, focused generated verification,
  bypass generation, demo command, media, README, timing, and public CI checks.
- Broader generated solver verification, the full bypass-hypothesis rule set, and other deferred product features.
- The known fractional-budget issue remains unfixed.

## Demo release, source inventory

**What changed in plain English**

Added an inventory of the supplied podcast chains. It distinguishes the
approved Fortune 600 fixture from routes whose graph still needs review.
It also records source gaps so later fixtures do not silently invent paths.

Recorded the decision to keep the exposed files in Episodes 1 and 2 as
evidence of how attackers discovered flaws, outside the paths being severed.
Hiding a file does not fix the vulnerability it revealed.

**New things you can now do**

- Find each supplied episode and see which route mappings remain unfinished.
- Check the approved source decisions before proposing another fixture.

**Files added or changed**

- `fixtures/armadin/AMBIGUITIES.md`: source inventory, decisions, and open mappings.
- `CHANGELOG.md`: records this documentation stage.

**Not done yet**

- Other fixtures, focused verification, bypass generation, demo command,
  media, README, fresh-run measurement, and public CI remain release work.
- Broader generated solver verification, the full bypass-hypothesis rule set, and later product features remain deferred.
- The known fractional-budget issue remains unfixed.

## Demo release, Episode 1 post-login fixture

**What changed in plain English**

Added the reported Episode 1 route from web access after admin login to
code execution on the database host. The graph keeps SQL injection
separate from the database permissions that enabled command execution.

The source does not say whether SQL injection required authentication.
The fixture therefore starts after the reported login. The earlier
authentication flaw and exposed source code remain in its evidence record,
but fixing them does not count as severing this modeled route.

Added approved excerpts and tests for the exact route, two candidate
changes, assumed costs, and source references. Both episode fixtures now
reuse the same quotation-and-reference checks.

**New things you can now do**

- Check the reported post-login route without inventing an authentication dependency.
- Trace the SQL injection and database-host execution to the supplied transcript.

**Files added or changed**

- `fixtures/armadin/graphs/episode1-post-login.json`: the post-login attack graph.
- `fixtures/armadin/sources/episode1-excerpts.txt`: approved source excerpts.
- `fixtures/armadin/provenance/episode1-post-login.json`: evidence and modeling limits.
- `fixtures/armadin/AMBIGUITIES.md`: records the approved scope and removal contract.
- `tests/unit/test_armadin_fixtures.py`: adds regressions and shares source checks.
- `CHANGELOG.md`: records this fixture stage.

**Not done yet**

- Remaining episode fixtures, focused verification, bypass generation, demo
  command, media, README, fresh-run measurement, and public CI.
- Broader generated solver verification, the full bypass-hypothesis rule set, and later product features remain deferred.
- The known fractional-budget issue remains unfixed.

## Demo release, Episode 2 auction-site fixture

**What changed in plain English**

Added the reported auction-site route from unauthenticated access to server
code execution. The graph separates the WebSocket authentication bug from
SQL injection and the account creation, login, and plugin execution that followed.

The final transition states that whole sequence explicitly. It does not
claim that SQL injection directly executed an operating-system command.
The fixture's candidate changes are limited to fixing the two reported
vulnerabilities. Broader policy changes are not modeled.

Added approved excerpts and tests for the exact route, two patch candidates,
assumed costs, and source references. The three episode fixtures now share
the catalog-summary check as well as the existing source checks.

**New things you can now do**

- Check the auction-site chain without inventing a separate Joomla vulnerability.
- Trace the abbreviated final transition to both account creation and plugin execution.

**Files added or changed**

- `fixtures/armadin/graphs/episode2-auction.json`: the two-transition attack graph.
- `fixtures/armadin/sources/episode2-excerpts.txt`: approved source excerpts.
- `fixtures/armadin/provenance/episode2-auction.json`: evidence and catalog limits.
- `fixtures/armadin/AMBIGUITIES.md`: records the approved mapping.
- `tests/unit/test_armadin_fixtures.py`: adds regressions and shares catalog checks.
- `CHANGELOG.md`: records this fixture stage.

**Not done yet**

- Remaining episode fixtures, focused verification, bypass generation, demo
  command, media, README, fresh-run measurement, and public CI.
- Broader generated solver verification, the full bypass-hypothesis rule set, and later product features remain deferred.
- The known fractional-budget issue remains unfixed.

## Demo release, Episode 3 building-management fixture

**What changed in plain English**

Added the reported route from an assumed corporate foothold to a building
management system. The attacker exploits PrintNightmare, reads a locally
stored operator credential, and uses it to log in.

The fixture ends at the reported console access, sensor data, and network
visibility. It does not claim control of physical equipment. The unsuccessful
service-account branch stays in the source record, outside this route.

Added source excerpts, diagram captions, and tests for the exact route,
candidate changes, assumed costs, and evidence references. These checks
keep the successful route separate from a branch that did not reach the goal.

**New things you can now do**

- Check the building-management route independently of Episode 3's cloud chain.
- Trace its three transitions and two modeled fixes to the reviewed evidence and assumptions.

**Files added or changed**

- `fixtures/armadin/graphs/episode3-building-management.json`: the three-transition graph.
- `fixtures/armadin/sources/episode3-building-management-excerpts.txt`: approved excerpts.
- `fixtures/armadin/provenance/episode3-building-management.json`: evidence and modeling limits.
- `fixtures/armadin/AMBIGUITIES.md`: records the approved scope and removal effects.
- `tests/unit/test_armadin_fixtures.py`: adds four regression checks using existing helpers.
- `CHANGELOG.md`: records this fixture stage.

**Not done yet**

- Remaining episode fixtures, focused verification, bypass generation, demo
  command, media, README, fresh-run measurement, and public CI.
- Broader generated solver verification, the full bypass-hypothesis rule set, and later product features remain deferred.
- The known fractional-budget issue remains unfixed.

## Demo release, Episode 5 post-registration fixture

**What changed in plain English**

Added a partial route that starts after account registration and token
issuance, then reaches successful SQL-query execution through the application.
It represents one unnamed SQL injection, not all three described in the episode.

The source also reports linked-server access and sensitive telecom data.
Those results stay in provenance because the source does not map individual
injections to the retrieved datasets. The fixture cannot claim that its
single patch prevents the full Internet-to-data attack.

Added nine source excerpts and tests for the exact partial route, its one
patch candidate, and the separation between that route and the broader case.
The source's count of three SQL injections remains separate from the number
of paths in the fixture.

**New things you can now do**

- Check the reported post-registration SQL injection without inventing endpoint pairings.
- Read the broader case evidence without counting it as this fixture's data coverage.

**Files added or changed**

- `fixtures/armadin/graphs/episode5-post-registration.json`: the partial attack graph.
- `fixtures/armadin/sources/episode5-excerpts.txt`: approved source excerpts.
- `fixtures/armadin/provenance/episode5-post-registration.json`: evidence and scope limits.
- `fixtures/armadin/AMBIGUITIES.md`: records the approved partial encoding.
- `tests/unit/test_armadin_fixtures.py`: adds four checks using existing helpers.
- `CHANGELOG.md`: records this fixture stage.

**Not done yet**

- Unresolved source mappings, including Episode 3's cloud chain and the complete
  external routes for the partial fixtures.
- Focused verification, bypass generation, demo command, media, README,
  fresh-run measurement, and public CI.
- Broader generated solver verification, the full bypass-hypothesis rule set, and later product features remain deferred.
- The known fractional-budget issue remains unfixed.

## Demo release, focused full-cover verification

**What changed in plain English**

Added generated tests for the workflow that finds the cheapest set of changes
severing every supplied validated path. They check the reported path IDs, cost,
weight, and input fingerprint, which identifies the paths and changes used.
They also compare small results with the existing brute-force answer key.

The tests include empty inputs, shared and overlapping changes, equal-cost
choices, paths that no available change can sever, and more expensive changes
that cannot improve the answer. Generated attack graphs run through the real
validation, path extraction, intervention synthesis, and solver code.

Added a deliberately broken toy that prefers one change even when a pair costs
less. Hypothesis must find its mistake and reduce the example to at most three
changes. A separate saved example keeps the cost-2 pair versus cost-9 single
change easy to inspect. This is a test of the checking process, not a production
bug report.

Added `make verify` for a deeper search with a fresh printed numeric seed and
a documented replay command. Normal runs use 200 cheap examples and 50 oracle
examples. The deeper profile uses 1000 and 250. These tests search for mistakes;
they are not a proof for every possible input.

**New things you can now do**

- Check full-cover results across varied inputs using existing cost tiers.
- Replay a deeper generated run using its printed seed.
- Add reviewed examples to the separate JSON regression directory.

**Files added or changed**

- `tests/conftest.py`: normal and deep Hypothesis profiles.
- `tests/property/strategies.py`: synthetic test inputs built through public models.
- `tests/property/test_full_cover.py`: the focused properties and overlap example.
- `tests/property/test_shrinking.py`: broken-toy shrinking and saved-example replay.
- `tests/property/regression/cheaper_pair.json`: the reviewed cost-2 example.
- `Makefile`: the deeper verification command.
- `README.md`: current solver status, verification commands, and limitations.
- `CHANGELOG.md`: records this verification stage.

**Not done yet**

- Budgeted and broader numeric verification remains deferred.
  The known fractional-budget issue is unchanged, and its regression still runs.
- The limited bypass generator, demo command, media, release README, fresh-run
  measurement, and public CI remain pending. The full bypass-hypothesis rule set is not complete.
- Frontier, robustness, normalization, and later product features remain deferred.

## Demo release, bounded bypass hypotheses

**What changed in plain English**

Added a queue of candidate routes to test after choosing environment changes.
Each candidate replaces one blocked step with an observed or inferred transition
already in the graph. The two supported rules change either the entry transition
into a service or the vulnerability enabling an exploit. These are unvalidated
hypotheses, not new findings or paths counted by the optimizer.

The generator checks the whole selected set of changes. It excludes a candidate
if any retained step is removed, and requires a reviewed explanation of whether
each selected change blocks the replacement. Missing explanations raise an error.
This prevents an alternate route from looking viable just because we checked
only one of the chosen fixes.

Observed replacements rank before inferred ones. Within each group, larger
objective weight times the fraction of original steps retained ranks first.
Stable IDs break ties, duplicate routes appear once, and the queue reports when
its size limit leaves candidates out. Every displayed hypothesis must use the
shared wording that calls it unvalidated and recommends validation.

The earlier live Fortune 600 library run returned EXACT and selected INT-003,
the modeled server-side request forgery patch, at an assumed cost of 1. It severs
the one supplied validated path, whose objective has assumed weight 10. That gives
N = 1 supplied validated path and M = 1 selected change. K = 12 is the podcast's
separate count of reported remote-code-execution findings. The fixture has no
observed or inferred replacements, so its generated queue is empty. This does not
establish that no bypasses exist or that Lumon independently reproduced the
source-reported attack.

Added 48 test cases, including nonempty synthetic queues, tied rankings, changed
evidence, blocking fixes, invalid inputs, and the real fixture's empty queue.
Synthetic routes stay inside tests and do not alter the source-backed counts.
These checks and the existing generated full-cover tests search for mistakes;
they are not a proof for every possible input.

**New things you can now do**

- Generate a bounded test queue for an explicit set of selected intervention IDs.
- Trace each candidate to its original path, replacement evidence, and assumptions.
- Repeat generation with the same inputs and obtain the same ordered queue.
- Run `.venv/bin/pytest` in the installed development environment to check the
  complete suite, including both substitution rules.

**Files added or changed**

- `src/lumon/model/hypothesis.py`: candidate records, queue metadata, and shared wording.
- `src/lumon/hypotheses/generate.py`: the two substitution rules and deterministic ranking.
- `tests/unit/test_hypotheses.py`: synthetic checks and the Fortune 600 empty-queue check.
- `CHANGELOG.md`: records this stage and the earlier live library result.

**Not done yet**

- The demo command and shared result artifact, PNG, GIF, 90-second video, release
  README, fresh-environment timing, and public CI still need to be completed.
- This is a demo-first stage, not completion of broader solver verification or the full bypass-hypothesis rule set.
  Broader bypass rules, budgeted verification, and broader numeric checks remain deferred.
- The known fractional-budget issue is unchanged and its regression still runs.
- Frontier, robustness, normalization, and later product features remain deferred.

## Demo release, live command and shared result

**What changed in plain English**

From the repository root, `uv run --frozen python demo/run_demo.py` now runs the
reviewed Fortune 600 example end to end. It validates the graph and source metadata
and checks that extracted paths match the reviewed route. It builds possible changes
using the existing assumed costs and calls the existing CP-SAT optimizer.
It prints the comparison and writes
`demo/output/result.json`. It computes a fresh answer on every run.

The verified result selects INT-003, the modeled server-side request forgery patch,
at an assumed cost of 1. It severs the one supplied source-validated path, with an
assumed objective weight of 10. The result is EXACT, meaning the optimizer proved
minimum cost over the supplied paths and available changes. N = 1 counts the
supplied path, M = 1 counts selected changes, and K = 12 is the podcast's separate
count of reported remote-code-execution findings. Lumon did not reproduce the attack.

The console output and JSON use one result object. The JSON includes the selected
changes, coverage, remaining transitions, evidence references, assumptions, and
bypass queue. Run timing and absolute machine paths stay out of this repeatable
output. The command rejects incomplete extraction, solver failures, and unproven
optima. It writes a complete temporary file before replacing the previous result;
the tested failures before replacement leave the previous result intact.

Added 39 demo test cases covering reviewed values, public-only inputs, repeatable
commands, invalid inputs, extraction limits, solver failures, and output handling.
One test compares the saved JSON with a fresh computation and checks the README
headline, repository link, and command. The full local suite passed 473 tests with
99.44 percent coverage, including the demo runner. Lint, formatting, and strict type
checks passed. Generated tests search for mistakes; they do not prove correctness
for every possible input.

**New things you can now do**

- Run the fixed example with Python 3.12 and uv, without private transcripts,
  API keys, Docker, a database, or external service accounts. Dependency setup may
  need internet access; the installed demo makes no runtime network calls.
- Inspect the computed JSON and trace its claims back to the reviewed input.
- Run `make check` to check the code and catch drift between the live result,
  saved JSON, and README. The coverage floor remains 90 percent.

**Files added or changed**

- `demo/run_demo.py`: runs the existing pipeline and renders its shared result.
- `demo/output/result.json`: the reviewed, repeatable output for the fixed input.
- `tests/unit/test_demo.py`: 39 regression cases for results and failure handling.
- `pyproject.toml`: includes the demo runner in coverage measurement.
- `.github/workflows/ci.yml`: runs the documented live command after existing checks.
- `README.md`: documents the working command, result, prerequisites, and limitations.
- `CHANGELOG.md`: records this locally completed work and remaining release requirements.

**Not done yet**

- Measure an isolated fresh install-and-run below two minutes and document the
  laptop, prerequisites, OS, Python version, and network conditions.
- Produce and inspect the PNG, GIF, and playable 90-second video with regeneration
  sources. Finish media/result consistency checks, the required README media layout,
  and the copyable share message.
- Obtain separate approval for commits, pushes, uploads, or visibility changes.
  Public asset access, a successful public CI run, and its live badge remain pending.
- This demo-first work does not complete broader solver verification or the full bypass-hypothesis rule set.
  Broader numeric and budgeted checks and additional bypass rules remain deferred.
  The known budget issue with costs 0.1 and 0.2 at budget 0.3 is unchanged; its
  regression still runs, and this demo does not use budgeted solving.
- Frontier, robustness sweeps, predicate normalization, LLM-assisted ingestion,
  general-purpose reporting, and the full CLI remain deferred.

## Demo release, waive fresh-install benchmarking

**What changed in plain English**

The user removed fresh-install benchmarking and the two-minute target from
this demo release. The README and local implementation brief no longer list that work
as a release requirement.

This is a scope change, not a successful benchmark. Existing-environment
timings remain exactly that. Earlier changelog entries are unchanged; this
entry supersedes their benchmark to-do items. No code, tests, source data,
cost assumptions, or computed results changed.

**New things you can now do**

- Continue the release work without a fresh-install timing gate.

**Files added or changed**

- `README.md`: removes fresh-install timing from the remaining work.
- Private demo-release plan: updates local requirements; excluded from Git.
- `CHANGELOG.md`: records the waiver without rewriting earlier history.

**Not done yet**

- Release PNG, GIF, playable 90-second video, and their regeneration sources.
- Final README media layout, copyable share message, and media/result checks.
- Public asset verification, successful public release CI, and its live badge.

## Demo release, silent media and README

**What changed in plain English**

Added an image, a short GIF, and a 90-second silent replay of the Fortune 600
demonstration. The user chose no narration or subtitles. The README explains
what appears at each point in the video and puts the result, image, command,
and limitations in the requested order.

The media authoring script checks a fresh computation against the reviewed
result, captures the real demo command's output, and uses those values in the
images. The result remains one supplied source-validated path, one selected
change, and 12 separately reported RCE findings. INT-003 removes the modeled
SSRF transition at an assumed cost of 1. EXACT establishes minimum cost over
the supplied paths and changes, not minimum change count or a unique answer.

Media checks compare the PNG and GIF with fresh renderings, decode the whole
video, and compare a frame from each scene. CI runs those checks alongside
the existing tests and type checks. Generated solver tests still search for
mistakes across many inputs; they do not prove correctness for every input.

**New things you can now do**

- Run the unchanged numeric demo with `uv run --frozen python demo/run_demo.py`.
- Regenerate or check the release media with the commands in the README.
- Read the explanation beside the silent video and copy the share message.

**Files added or changed**

- `docs/render_demo.py`: authors and checks the fixed demonstration media.
- `docs/demo.png`, `docs/demo.gif`, `docs/demo.mp4`: generated release assets.
- `README.md`: media, limitations, regeneration commands, and share message.
- `tests/unit/test_demo.py`: checks asset links, README order, and share text.
- `.github/workflows/ci.yml`: checks media source types and actual asset files.
- `CHANGELOG.md`: records this stage and the remaining release checks.

**Not done yet**

- Confirm playback from the public README and verify public access to the assets.
- Obtain separate commit and push approval, then check CI for that release revision.
  The badge follows the public master branch, not unpublished local work.
- This demo-first work does not complete broader solver verification or the full bypass-hypothesis rule set.
  Broader numeric and budgeted checks and additional bypass rules remain deferred.
  The known 0.1 + 0.2 budget issue is unchanged and its regression still runs.
- Frontier, robustness, normalization, LLM-assisted extraction, general reporting,
  and the full CLI remain deferred.

## Demo release, compact terminal previews

**What changed in plain English**

The demo now prints a bordered Lumon-only table and the selected change.
The customer column and longer explanatory sections no longer fill the
terminal. The full evidence, assumptions, customer unknowns, and generated
bypass queue remain in the saved JSON.

Recorded new silent video and GIF previews from the real demo command.
The results fit on one screen without scrolling. The video lasts 90 seconds;
the GIF is a 20-second excerpt. Both files were decoded completely and
sampled frames were inspected for readable text and correct values.

The calculation is unchanged: one selected change severs the one supplied
source-validated Fortune 600 path at assumed cost 1. The podcast separately
reports 12 RCE findings. All 475 tests and strict type checks pass, and the
saved result is byte-for-byte unchanged.

**New things you can now do**

- Run `uv run --frozen python demo/run_demo.py` for the compact result table.
- Watch the new local recording previews without narration or captions.

**Files added or changed**

- `demo/run_demo.py`: shortens console output without changing computation.
- `tests/unit/test_demo.py`: checks the exact compact display.
- `docs/demo.tape`: records the compact output without unnecessary scrolling.
- `.private/demo-release/terminal-compact.mp4` and `terminal-compact.gif`:
  local previews excluded from Git.
- `CHANGELOG.md`: records this reviewed stage.

**Not done yet**

- Replace the legacy slideshow checker and public media, update the README,
  and finish the graph/recommendation PNG in separately reviewed changes.
- Obtain commit and push approval, then verify public playback and release CI.
- This demo-first stage does not complete broader solver verification or the full bypass-hypothesis rule set.
  Broader numeric and budgeted checks, additional bypass rules, and the known
  fractional-budget issue remain deferred.
- Frontier, robustness, normalization, LLM-assisted extraction, general reporting,
  and the full CLI remain deferred.

## Demo release, approved video and GIF

**What changed in plain English**

Added the approved 90-second terminal recording and its 20-second GIF excerpt
to `docs/`, with links and a short explanation in the README. These are exact
copies of the compact previews reviewed by the user. Older media drafts and
the unfinished diagram are not included in this commit.

The commit also includes the compact console display, its regression test,
and the recording script. The calculation and saved JSON are unchanged:
one selected change severs one supplied source-validated Fortune 600 path at
assumed cost 1. The podcast separately reports 12 RCE findings.

**New things you can now do**

- Watch the approved GIF and silent video from the README.
- Run `uv run --frozen python demo/run_demo.py` for the matching compact output.

**Files added or changed**

- `docs/demo.mp4` and `docs/demo.gif`: the approved recording and excerpt.
- `README.md`: links the media and describes the recorded steps.
- `demo/run_demo.py`: prints the compact table and selected change.
- `tests/unit/test_demo.py`: checks the compact output.
- `docs/demo.tape`: records the real terminal commands.
- `CHANGELOG.md`: records this media publication stage.

**Not done yet**

- Finish the graph/recommendation PNG, final README layout, and media regeneration
  and automated checks. Those unfinished drafts remain local.
- Verify public playback and CI after pushing this commit.
- This demo-first stage does not complete broader solver verification or the full bypass-hypothesis rule set.
  Broader numeric and budgeted verification, additional bypass rules, and the known
  fractional-budget issue remain deferred.
- Frontier, robustness, normalization, LLM-assisted extraction, general reporting,
  and the full CLI remain deferred.

## Demo release, before-and-after diagram

**What changed in plain English**

The PNG now shows the supplied Fortune 600 kill chain beside the same graph
with Lumon's selected change applied. A small table identifies the change,
its assumed cost, and the supplied path it severs.

Both panels use one drawing function and the same computed result. The
after panel breaks only the SSRF transition removed by INT-003. The other
transitions remain visible. Vulnerabilities label the transitions they
enable; they are not added as extra steps in the attack.

**New things you can now do**

- See the recommended change and exactly where it breaks the supplied route.

**Files added or changed**

- `docs/render_demo.py`: draws the two graph panels and recommendation table.
- `docs/demo.png`: the local before-and-after diagram.
- `CHANGELOG.md`: records this diagram update.

**Not done yet**

- Replace the rejected slideshow entry point and its checks in a separate change.
  This update uses only the PNG-rendering function.
- Final README integration and publication of the updated PNG remain pending.
- Broader solver verification, the full bypass-hypothesis rule set, and other previously deferred work remain deferred.

## Demo release, media checks and simpler documentation

**What changed in plain English**

Removed the old slideshow code. The media command now regenerates only the
before-and-after PNG. Its check mode verifies the PNG against the live result,
decodes the complete 90-second recording, and checks all 200 GIF frames against
the matching video excerpt. It never replaces the approved recordings.

The README now focuses on running and watching the demo, with the final PNG,
video, and GIF together. It also explains the name's connection to Severance.
The longer evidence notes, model explanation, and development commands moved
into a linked guide, along with instructions for updating the media.

The calculation is unchanged. One selected change severs the one supplied
source-validated Fortune 600 path at assumed cost 1 and assumed path weight 10.
The podcast separately reports 12 RCE findings. All 475 tests pass at 99.44%
coverage, along with lint, formatting, strict typing, and the media checks.

**New things you can now do**

- Follow a short README to run the demo and watch the approved recordings.
- Check the shipped media and follow the guide to make a new recording.

**Files added or changed**

- `docs/render_demo.py`: renders only the PNG and checks the final recordings.
- `README.md`: shortens the introduction and links the final media and guide.
- `docs/demo-guide.md`: preserves the detailed notes and records the media workflow.
- `tests/unit/test_demo.py`: checks the guide link and relocated share message.
- `CHANGELOG.md`: records this reviewed stage.

**Not done yet**

- Commit and push approval, public playback checks, and green CI for the final
  release revision remain pending.
- This demo-first release does not complete broader solver verification or the full bypass-hypothesis rule set.
  Broader numeric and budgeted checks and additional bypass rules remain deferred.
  The known fractional-budget issue with costs 0.1 and 0.2 at budget 0.3 is unchanged.
- Frontier, robustness, normalization, LLM-assisted extraction, general reporting,
  and the full CLI remain deferred.

## Demo release, portable media checks and graph images

**What changed in plain English**

Replaced the GIF comparison that failed in Linux CI. Re-encoding the video
excerpt made that check depend on the platform's FFmpeg build. The checker now
identifies the exact reviewed video and GIF by their SHA-256 hashes, which are
file fingerprints. It still decodes every frame and checks duration and timing.

Added two dark-background images showing the supplied Fortune 600 route before
and after Lumon's recommendation. Both use the same graph and computed result.
The after image marks only the removed SSRF transition with a gap and red X.
The remaining transitions stay visible. No branches from the reference image
were added to the data.

The README includes both images beside the existing poster and keeps the
approved video and GIF. Removed the guide's Limitations section as requested,
kept its source links, and documented the direct PNG-rendering command.
No browser export or new dependency is needed.

The result is unchanged: INT-003 severs the one supplied source-validated path
at assumed cost 1, with an EXACT minimum-cost result. The podcast separately
reports 12 RCE findings. Run `uv run --frozen python demo/run_demo.py` to reproduce it.
All 475 tests pass locally at 99.44% coverage, along with lint, formatting,
strict typing, and media checks.

**New things you can now do**

- See the constructed route and the specific link Lumon's recommendation removes.
- Regenerate both graph PNGs with the guide's `--graphs` command.
- Check all three PNGs against fresh renders without replacing the recordings.

**Files added or changed**

- `docs/render_demo.py`: renders the new graphs and checks all release media.
- `docs/fortune600-before.png` and `docs/fortune600-after.png`: the two graph images.
- `README.md`: embeds the new images beside the existing poster.
- `docs/demo-guide.md`: removes the requested section and updates media instructions.
- `tests/unit/test_demo.py`: checks all five media links and their order.
- `CHANGELOG.md`: records this stage without changing earlier entries.

**Not done yet**

- Commit and push approval, public asset checks, and a green CI run for this
  release revision remain pending.
- This demo-first release does not complete broader solver verification or the full bypass-hypothesis rule set.
  Broader numeric and budgeted checks and additional bypass rules remain deferred.
  The known fractional-budget issue with costs 0.1 and 0.2 at budget 0.3 is unchanged.
- Frontier, robustness, normalization, LLM-assisted extraction, general reporting,
  and the full CLI remain deferred.

## Demo cleanup

**What changed in plain English**

Removed the old overview poster and its rendering code. The README keeps the
two dark attack-chain diagrams, the video, and the GIF. The media renderer now
creates both graph PNGs by default; `--check` still verifies the images and recordings.

Historical changelog entries now use feature names instead of numbered planning
references. Removed their date lines, repeated caveat sections, and introductory
audience note. Private planning files and Git history are unchanged.

**New things you can now do**

- Regenerate both graph images with `python -m docs.render_demo` in the documented
  media-authoring environment.
- Read the project history without internal planning labels.

**Files added or changed**

- `README.md`: removes the old poster.
- `docs/demo.png`: deleted; recoverable from Git history.
- `docs/render_demo.py`: removes poster rendering and simplifies the authoring command.
- `docs/demo-guide.md`: updates image instructions and uses feature names.
- `tests/unit/test_demo.py`: checks the four remaining media links in order.
- `tests/property/test_full_cover.py`: describes its scope without an internal label.
- `.gitignore`, `Makefile`, and `pyproject.toml`: remove planning references from comments.
- `CHANGELOG.md`: applies the requested cleanup and records it here.

**Not done yet**

- Public CI for this cleanup revision remains pending publication.
- Broader numeric and budgeted verification and additional bypass rules remain deferred.

## Constructed multi-path demo

**What changed in plain English**

The demo command now runs two separate cases. Episode 4 keeps its one
source-validated path and SSRF patch result. The second uses the unchanged
REALISTIC generator preset with seed 4. Its 40 paths are marked validated
inside a constructed graph, not reported as attacks exercised in an environment.

Lumon compares seven modeled changes and selects one shared access-control
change at assumed cost 1. It severs all 40 constructed validated paths, and
CP-SAT proves the minimum cost. The three observed and two inferred edges
do not match the existing bypass rules, so the generated queue remains empty.

Both cases must finish before the command replaces the saved JSON. Their
evidence stays separate, and elapsed solve times stay out of the repeatable
result. Tests check the constructed routes, compare the solve with the
independent brute-force answer key, and verify that second-case failures
preserve the previous output.

**New things you can now do**

- Run both cases with `uv run --frozen python demo/run_demo.py`.
- Inspect the constructed summary and generator settings under
  `constructed_case` in the saved JSON.

**Files added or changed**

- `demo/run_demo.py`: computes both cases and shares solve checks and display logic.
- `demo/output/result.json`: adds the constructed summary without changing Episode 4's fields.
- `tests/unit/test_demo.py`: checks both results, provenance, repeatability, and failures.
- `README.md`: adds the constructed result and identifies the Episode 4-only media.
- `docs/demo-guide.md`: explains both cases and the existing recording's scope.
- `docs/render_demo.py`: checks the combined result before rendering the unchanged graph images.
- `CHANGELOG.md`: records this addition.

**Not done yet**

- Publication and public CI for this revision require separate approval.
- New media for the constructed case and additional bypass rules are not included.
