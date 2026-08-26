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
