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
