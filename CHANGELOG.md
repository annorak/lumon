# Changelog

Written for a junior engineer who just joined and has not read the design doc. Plain English,
newest entry at the bottom.

---

## Repository initialization — README and .gitignore
_2026-08-26_

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
thing: the planning material. The design doc, the 19 task files, and the agent preamble used to
sit in a folder called `files/`. That folder is now `.private/` and is ignored. It stays on the
author's machine and is not distributed with the repo. If you cloned this and are wondering where
the design doc went, that is where — ask for it directly.

`CHANGELOG.md` is this file, started here so that task 01 has something to append to.

No code exists yet. The repo does not install, lint, type check, or test, because there is no
package and no `pyproject.toml`. Task 01 builds all of that. The install and `make check`
instructions in the README describe the interface task 01 will create, and the README says so
plainly in its Status section rather than implying you can run them today.

**New things you can now do**

- Understand what the project is, and what it deliberately refuses to do, from the repo alone
- Clone the repo without dragging the private planning material along with it
- Append your task's entry to a changelog that already exists

**Files added or changed**

- `README.md` — what Lumon is, the optimization it solves, the honest limitations, the tech stack
- `.gitignore` — Python, `uv`, coverage, and editor artifacts, plus `.private/`
- `CHANGELOG.md` — this file
- `files/` renamed to `.private/` — the planning material, now untracked

**Gotchas worth knowing**

- `.private/` is ignored, so `git status` will never remind you it exists. Do not put anything in
  there you actually want committed, and do not rename it back.
- `uv.lock` is deliberately **not** ignored. A committed lock file is what lets someone else
  reproduce our results, which is the entire point of the project.
- `.claude/settings.local.json` is ignored — it is per-machine tool permissions, not project
  configuration.
- The README states the complexity result in both halves: the problem is NP-hard, *and* real
  instances are far too small for that to matter. Any doc or comment that states only one half is
  wrong. Do not fix one half by deleting the other.

**Not done yet**

- Everything. There is no Python package, no dependencies declared, no `Makefile`, and no CI.
  Task 01 lays down the scaffold and adds its own entry below this one.
- The README links no design doc, because the design doc is intentionally not in the repo.

---

## Task 01 — Repo scaffold and tooling
_2026-08-26_

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
Every one of the eighteen remaining tasks will run `make check` and trust the result, so the
settings are deliberately unforgiving. `mypy` is strict, which means every function you write
needs type annotations including the return type, and that applies to test functions too — a
test that says `def test_thing():` will fail type checking until you write
`def test_thing() -> None:`. That catches real bugs and it is much cheaper to accept now than to
retrofit later.

The package skeleton exists as thirteen empty importable packages — `model`, `io`, `paths`,
`solve`, and so on — one per stage of the pipeline. They contain nothing but an `__init__.py`.
That is on purpose: the directory layout is fixed by the project context, and having it in place
means no later task has to invent where its code goes.

One number to know about: the coverage gate is set to `--cov-fail-under=0`, not 90. There are
two lines of real code in the whole repo right now, so a 90% gate would fail the build for no
useful reason. There is a `TODO(task-02)` comment on it in `pyproject.toml`. **Task 02 raises it
to 90 and it should not come back down after that.**

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
- `uv.lock` — committed on purpose, see the gotcha below
- `README.md` — Status section updated from "pre-scaffold" to what actually exists now
- `docs/`, `fixtures/armadin/`, `tests/fixtures/` — created with `.gitkeep`, since git does not
  track empty directories

**Gotchas worth knowing**

- **`networkx` and `ortools` ship no type information.** Nothing imports them yet, so there is no
  mypy override for them and none is needed today. The first task that imports either one will
  see `import-untyped` errors from strict mypy. The fix is a per-module override in
  `pyproject.toml` naming *only* `networkx.*` and `ortools.*`. Do **not** reach for a global
  `ignore_missing_imports` — that would quietly loosen type checking for every dependency, which
  is the exact failure this scaffold is trying to prevent. There is a comment in `pyproject.toml`
  at the spot where the override goes.
- **`uv.lock` is committed and must stay committed.** Lumon's whole premise is that a skeptic can
  check our results. They cannot do that if they cannot reproduce our environment.
- **`make lint` also fails on formatting**, because it runs `ruff format --check`. If it complains
  about formatting rather than a real lint rule, run `make format` and re-run.
- **`--strict-markers` and `--strict-config` are on.** A typo in a pytest marker is an error, not
  a silently ignored decorator.
- `src/lumon/io/` shares a name with Python's standard-library `io` module. This is safe — Python 3
  uses absolute imports, so `import io` inside the package still gets the standard library — but do
  not "fix" it by renaming the directory, since the layout is fixed by the project context.

**Not done yet**

- No product logic of any kind. No graph, no paths, no interventions, no solver. Task 02 adds the
  domain model.
- Coverage gate is at 0. Task 02 raises it to 90.
- CI has never actually run — the workflow file is valid YAML and the same `make check` passes
  locally on macOS, but the first push is the first time it executes on Linux.
- `docs/` and `fixtures/armadin/` are empty placeholders. Task 14 fills the fixtures.

---

## Task 02 — Core domain model
_2026-08-26_

**What changed in plain English**

The repo now has a vocabulary. Everything after this task manipulates the three types added
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

One thing this task deliberately does *not* do: it does not check that an edge's `source` and
`target` actually exist in the node list. A graph full of dangling edges constructs happily.
That is on purpose — ingest assembles a graph as evidence arrives and needs to hold partial
state — and there is a test asserting it stays that way. Task 03 is where a graph gets judged
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

**Gotchas worth knowing**

- **Frozen is not deep.** `node.label = "x"` raises, but `node.attributes["x"] = "y"` succeeds,
  and so does `graph.nodes.append(...)`. Pydantic only guards attribute assignment. Treat the
  dicts and lists as read-only by convention; nothing enforces it.
- **Only objectives carry a weight.** An objective without one is a validation error, and so is
  a weight on anything that is not an objective. The weight is how much the business loses if
  that objective falls, which is what makes "percent of weighted paths severed" mean anything.
  A weight on, say, a service would silently mean nothing, so it is rejected outright.
- **Ids must have no whitespace and must not be empty.** Ids are the join key between graphs,
  paths, coverage matrices, and the final report. `"n 1"` versus `"n1"` would be a very quiet
  bug. Note that this rule lives in Python and does *not* show up in the exported JSON Schema,
  so an external tool generating input files will not be warned by the schema alone.
- **The enums serialize as lowercase strings** (`"entry_point"`, `"validated"`), not integers,
  so hand-written fixture files stay readable and a diff of two graphs is meaningful.
- **`node_by_id` and `edge_by_id` scan the list.** Fine at the real sizes (tens of paths, around
  a hundred interventions). If some later stage does these lookups inside a hot loop, build a
  dict there rather than caching one on the model.

**Not done yet**

- Nothing loads a graph from a file yet, nothing checks that a graph makes sense, and nothing
  converts it to NetworkX. That is all task 03.
- `Path`, `PathSet`, and the intervention types are not here. Tasks 05 and 06 add them to this
  same `model/` package.

---

## Task 03 — Graph I/O and invariants
_2026-08-27_

**What changed in plain English**

Task 02 gave us types you could build in Python. This task lets a graph come from a file, and
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

**Gotchas worth knowing**

- **`to_networkx` does not check invariants, on purpose.** Hand it a graph with a dangling edge
  and NetworkX will invent the missing endpoint as a node with no attributes, so
  `G.nodes["n_clod"]` is `{}` and a later stage reading `data["node"]` will raise `KeyError`.
  Call `assert_usable` where the graph enters the pipeline. It is not done inside the converter
  so that you can still convert a graph you already know is broken in order to look at it.
- **`enabled_by` counts for `ORPHAN_NODE`.** A node is an orphan only if no edge names it as
  source, target, *or* `enabled_by`. Vulnerability nodes are never edge endpoints — they are
  only ever referenced as an enabler — so the stricter reading would flag every vulnerability in
  every graph and the warning would be pure noise.
- **A graph that loads is not a graph that is usable.** `load_graph` only proves the file matches
  the schema. `AttackGraph` still deliberately permits edges pointing at nodes it does not
  contain, because ingest assembles graphs as evidence arrives. The two checks are separate on
  purpose; run both.
- **`save_graph` output is semantically equal to a hand-written fixture, not byte-identical.**
  Pydantic writes every field, so you get `"weight": null` and `"attributes": {}` on nodes that
  omitted them. Round-trip tests compare parsed graphs, never file text.
- **Violation codes are plain strings**, not an enum. If you match on one, a typo is a silently
  empty result. There is a test per code, so a typo in the checker itself is caught.
- **The mypy override names only `networkx.*`.** When the solver task imports `ortools`, add a
  second scoped override next to it. Do not reach for a global `ignore_missing_imports`.

**Not done yet**

- Nothing enumerates paths through the graph. `to_networkx` exists so task 05 can, but no code
  walks entry to objective yet.
- Nothing calls `assert_usable` anywhere, because there is no pipeline and no CLI yet. Task 18
  wires it in at the boundary where a graph is loaded.
- No generator, so every graph in the repo is hand-written. Task 04 adds the synthetic generator.

---

## Task 04 — Synthetic attack graph generator
_2026-08-27_

**What changed in plain English**

Every graph in the repo up to now was hand-written, and there were three of them. That does not
carry us far. Task 10 wants to throw hundreds of randomly shaped graphs at the solvers and check
the answers, and nobody is hand-writing hundreds of graphs. So this task adds a generator: give it
a seed and a shape, and it hands back an attack graph.

The interesting part is the second thing it hands back. Alongside the graph comes a `GroundTruth`
object saying what the answers are — every attack path in the graph, which nodes every path is
forced through, and what each objective is worth. And the generator knows all of that **because it
built the graph that way**, not because it went and looked afterwards.

That distinction is the whole point of this task, so it is worth being clear about. Suppose we had
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
over, and so that task 13 has raw material for bypass hypotheses. They are placed carefully: a
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

**Gotchas worth knowing**

- **Do not make the ground truth come from our own code.** If you ever find yourself tempted to
  call path extraction or a solver from inside the generator to work out an expected answer, that
  is the failure this whole design exists to prevent. Change the construction instead.
- **The order of the random draws is load-bearing.** `generate` draws chokepoint placement first,
  then objective weights, then decoy edges, all from one `random.Random`. Reorder those three
  calls and every existing seed produces a different graph, which will silently change what every
  downstream test is testing.
- **The ratios are a fraction of the validated edge count, not of the total.**
  `observed_edge_ratio=0.2` on a graph with 15 validated edges gives you 3 observed edges, so
  observed edges are 3 of 18 — about 17% of the file, not 20%. On small graphs the rounding bites:
  `TINY` has 5 validated edges, so the default `inferred_edge_ratio` of 0.1 rounds to zero and
  `TINY` has no inferred edges at all. If your test needs one, use a bigger preset.
- **`minimum_chokepoint_cover_size` is 1 whenever any chokepoint was planted.** That is not a
  placeholder. Every planted chokepoint is the sole link between two layers, so every path already
  runs through every one of them, and any single one on its own therefore covers the lot. `DEEP`
  plants two chokepoints and its minimum cover is still 1.
- **Decoy edges are allowed to skip past a chokepoint**, and that is deliberate rather than a bug
  in the placement rule. An unexercised route around the fix is exactly what task 13 wants to
  queue up for testing. It is safe because a decoy is never validated, and nothing that is not
  validated can reach the solver.
- **Every validated edge is a `reaches` edge and every middle node is a `service`.** These graphs
  are not trying to look like real networks; task 04 puts realism out of scope. The consequence
  worth knowing is that when task 06 synthesizes interventions from one of these graphs, it will
  produce exactly one access-control intervention per non-entry node.
- **`n_planted_chokepoints` cannot exceed `depth`.** Each chokepoint eats one middle layer, so
  asking for more chokepoints than layers is rejected at construction rather than quietly clamped.

**Not done yet**

- Nothing consumes these graphs yet. Task 05 adds path extraction, and its key test is that the
  paths it finds match `GroundTruth.path_node_sequences` exactly, for every preset.
- The generator makes no vulnerability or credential nodes and sets no `enabled_by` on anything,
  so the task 06 synthesis rules keyed to those will not fire on a generated graph. They get
  tested against hand-built graphs instead.
- No graphs are checked into the repo from this. Everything is generated on demand in tests, since
  a seed and a parameter set reproduce a graph exactly.

## Task 05 — Path extraction
_2026-08-27_

**What changed in plain English**

Up to now we had graphs and nothing that read them. This task adds the step that turns a graph
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
back — task 13 picks them up as raw material for bypass hypotheses, which are explicitly a queue
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

**Gotchas worth knowing**

- **`Path` shadows `pathlib.Path`.** If a module needs both, alias one of them. Nothing in the
  codebase currently does, which is why this has not bitten anyone yet.
- **`PathSet.truncated` has no default and is deliberately required.** You cannot construct a
  path set without stating whether it is complete. That is 16 extra characters in every test and
  it is worth it: the one failure this type must never allow is a partial result that looks whole.
- **`max_depth` does not set `truncated`, and that is on purpose.** `max_depth` is a hop count
  (12 by default, meaning at most 12 edges and 13 nodes), and a route longer than it is silently
  absent from the output. That sounds like exactly the thing the previous bullet is against, but
  the difference is that we genuinely cannot tell cheaply whether a longer route exists — proving
  it does not is a longest-path problem. Flagging every graph "we might have missed something"
  would make the flag meaningless. `truncated` means one specific, checkable thing: enumeration
  stopped early because it ran out of budget. If you shrink `max_depth`, know that you are
  choosing to not look, and say so wherever the result is used.
- **NetworkX's `all_simple_paths` is the wrong function for this graph type.** On a
  `MultiDiGraph` it yields the same node list once per combination of parallel edges, so pairing
  it with your own edge expansion double-counts. `all_simple_edge_paths` is the right one — it
  hands back the edge keys directly. This was caught by the two-edge-types test, which is a good
  argument for that test existing.
- **The cap is checked one path past itself.** A graph with exactly `max_paths` paths comes back
  complete and unflagged, because nothing was actually dropped. A false truncation flag sends a
  reviewer hunting for paths that never existed, which is its own kind of wrong.
- **Path weight is the weight of the objective it reaches, and paths are counted per route.** An
  objective worth 10 that 40 routes reach contributes 400 to `total_weight`, not 10. That is the
  intended behaviour — severing one of those 40 routes is worth something — but it does mean
  `total_weight` is not "the value of everything at risk."
- **`PathStats` reports `None`, not zero, for lengths when there are no paths.** A graph where no
  validated route reaches any objective has no shortest path, and "0 hops" would be a false
  statement dressed as a tidy default. A validator keeps those fields `None` exactly when the
  count is zero.
- **Path ids are positional.** `p0000` is just "first after sorting." Re-run extraction on a
  changed graph and the same id can name a different path. Never persist a path id as a stable
  reference to a route; pair it with the `graph_id` the `PathSet` carries.

**Not done yet**

- Nothing proposes fixes yet. Task 06 synthesizes the intervention catalog — the candidate
  changes, each with the set of edges it removes and a cost carrying a label saying whether a
  human supplied that cost or we assumed it.
- Path extraction does not check graph invariants before it runs. Intervention synthesis does:
  an unusable exploit edge could otherwise produce a catalog that cannot sever every supplied
  route. Task 18 will also check at the CLI boundary.
- The observed and inferred edges that extraction discards are not stored anywhere for later.
  Task 13 re-reads them from the graph when it generates bypass hypotheses.

## Task 06 — Intervention model and synthesis
_2026-09-07_

**What changed in plain English**

Up to now Lumon could list the attack routes Armadin supplied, but it could not describe a
change that would break one. This task adds that missing half. An intervention is one
customer change, such as patching a vulnerability, removing an exposed credential, or
reducing an identity's permissions. It records every validated graph edge that change
would remove.

One intervention can remove several edges. If three kill chains all use the same
over-permissioned identity, reducing that identity's permissions is one change that can
break all three chains. Task 07 will turn these removal sets into the grid the optimizer
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
- `tests/unit/test_invariants.py` — checks the task 06 graph requirements
- `pyproject.toml` and `uv.lock` — add typed YAML support
- `.private/task-06-interventions.md` — records the clarified task 06 rules
- `.private/task-13-bypass-hypotheses.md` — keeps future route substitution on the same
  boundary-crossing rule
- `.private/task-14-armadin-fixtures.md` — records how real transcripts must encode crossings

**Gotchas worth knowing**

- A boundary is crossed only when a `REACHES` edge says
  `crosses_boundary: <boundary node id>`. Ending at a boundary is not the same thing.
- `READS` has a narrow meaning in Lumon's graph: an execution context reads credential
  material. Credential removal groups `READS.target` with
  `AUTHENTICATES_AS.source`. It does not mean deleting a database that a process reads.
- Removing credential material and rotating a credential are different actions. This task
  models removal only.
- Synthesized ids are stable for one catalog construction and start at `INT-000`. They
  should be regenerated after the graph changes.

**Not done yet**

- Nothing selects the best interventions yet. Task 07 connects interventions to paths,
  and tasks 08 through 11 choose portfolios and build the cost-versus-coverage frontier.
- `SERVICE_REMOVAL` is modeled, but automatic synthesis does not propose removing a service.
- Lumon records whether side effects were declared, but it cannot discover which
  legitimate workloads a change might break.
