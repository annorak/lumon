# Demo guide

[Back to the README](../README.md)

Run all commands below from the repository root.

The demo command reads the public fixtures, computes the answer live, and replaces
`demo/output/result.json` with the result. It never reads that file as a cached answer.

Private transcripts are not needed. The installed demo makes no runtime network
calls and needs no API keys, Docker, database, service account, or media tools.

## Limitations

- Armadin reports validating the attack. Lumon did not reproduce it. The
  [graph](../fixtures/armadin/graphs/episode4-fortune600.json),
  [provenance](../fixtures/armadin/provenance/episode4-fortune600.json), and
  [approved excerpts](../fixtures/armadin/sources/episode4-excerpts.txt)
  support one narrated route. They do not establish 12 complete paths.
  Other episode fixtures and clearly labeled synthetic examples do not enter this headline.
- Extraction uses a maximum depth of 12 and a maximum of 5000 paths.
  The demo checks the extracted edge sequence against the reviewed route.
  The exact CVE identifier, credential identities, and Kubernetes permission bindings
  are not supplied or separately modeled.
- Costs use assumed implementation units, with tiers of 1, 3, and 9.
  The path's objective weight of 10 is also assumed. These are not measured customer
  effort or customer-supplied priorities. `EXACT` proves minimum cost over the supplied
  validated paths and candidate changes. It does not prove minimum change count,
  unique optimality, or coverage of every conceivable fix or attack.
- The podcast reports that the customer remediated all 12 RCE findings.
  Its actual changes, count, cost, removal effects, modeled coverage, and remaining
  access are unknown. A numerical comparison with the customer's actual changes is
  unavailable. Its bypass queue is unavailable too.
- Intervention effects are modeled edge removals. Applicability and operational side
  effects remain untested. The selected patch leaves credential-read and authentication
  steps in the graph; those steps do not prove a surviving complete route.
- Bypass hypotheses are unvalidated candidates to test. This release supports entry
  and vulnerability substitution using supplied observed or inferred transitions.
  The Fortune 600 queue is empty because no such alternatives were supplied.
  Empty queues and unsupported substitutions do not establish that no bypasses exist.
- This demo-first release does not complete the original Task 10 or full Task 13.
  Broader numeric and budgeted verification remain deferred. The budgeted solver can
  raise at budget 0.3 when selected costs 0.1 and 0.2 sum to 0.30000000000000004.
  Its regression remains in the complete suite; this demo does not use budgeted solving.
- The Pareto frontier, robustness sweep, predicate normalization, LLM-assisted
  extraction, general-purpose reporting, and full CLI remain deferred.
  Fresh-install benchmarking is not required, and no fresh-install timing is claimed.

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

Run `uv sync --frozen` to install the development dependencies, then `make check`
for lint, formatting, strict typing, and the complete test suite with the existing
90 percent coverage floor.

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

## Updating the media

The media tools are separate from the dependencies used to run the numeric demo.
The PNG comes from [render_demo.py](render_demo.py); the recording commands
live in [demo.tape](demo.tape).

To regenerate only `docs/demo.png` from the current result:

```sh
uv run --frozen --with pillow==12.3.0 --with imageio-ffmpeg==0.6.0 \
  python -m docs.render_demo
```

The command refuses to render if the computed result differs from the saved JSON.
Review any result change first. It never replaces the video or GIF.

To check the existing PNG, video, and GIF without replacing them:

```sh
uv run --frozen --with pillow==12.3.0 --with imageio-ffmpeg==0.6.0 \
  python -m docs.render_demo --check
```

The checker compares the PNG with a fresh render, decodes all 2160 video frames,
and compares every GIF frame with the corresponding video excerpt. The video is
90 seconds at 24 frames per second. The GIF is a 20-second excerpt starting at
13.5 seconds, at 10 frames per second.

### Record a new video

The accepted recording was made on macOS with Menlo, VHS 0.12.0, ttyd 1.7.7,
and FFmpeg 9.0.1. Follow the [VHS installation instructions](https://github.com/charmbracelet/vhs#installation)
to install the recorder and its ttyd and FFmpeg dependencies.

Use a fresh checkout for a new recording. These commands refuse to reuse the
tape's frame directory or terminal snapshots:

```sh
mkdir -p .private/demo-release
test ! -e .private/demo-release/terminal-compact-frames &&
test ! -e .private/demo-release/terminal-compact.txt &&
vhs docs/demo.tape
```

The tape runs the real demo and exports paired text and cursor PNGs.
The `.private/` paths here are generated outputs, not required private inputs.
Never mix frames from different recordings.

Check that both layers contain the same consecutive frame numbers, then
calculate how many copies of the final frame will bring the video to 90 seconds:

```sh
uv run --frozen python - <<'PY'
from pathlib import Path

frames = Path(".private/demo-release/terminal-compact-frames")
text_frames = sorted(
    path.name.removeprefix("frame-text-") for path in frames.glob("frame-text-*.png")
)
cursor_frames = sorted(
    path.name.removeprefix("frame-cursor-") for path in frames.glob("frame-cursor-*.png")
)
frame_count = len(text_frames)
assert text_frames == cursor_frames == [
    f"{index:05d}.png" for index in range(1, frame_count + 1)
]
assert 0 < frame_count <= 2160
print(f"Captured frames: {frame_count}")
print(f"Final hold frames: {2160 - frame_count}")
PY
```

The accepted capture had 1964 frames, so it needs 196 final hold frames.
Replace `stop=196` below with the value printed for your recording.
If the capture exceeds 2160 frames, shorten reading pauses and record again.
Do not trim or speed up command execution.

```sh
ffmpeg -nostdin -v error -xerror -n \
  -framerate 24 -start_number 1 \
  -i .private/demo-release/terminal-compact-frames/frame-text-%05d.png \
  -framerate 24 -start_number 1 \
  -i .private/demo-release/terminal-compact-frames/frame-cursor-%05d.png \
  -filter_complex '[0:v][1:v]overlay=shortest=1:format=auto,pad=1800:1080:(ow-iw)/2:(oh-ih)/2:color=0x171717,tpad=stop_mode=clone:stop=196[v]' \
  -map '[v]' -c:v libx264 -crf 20 -pix_fmt yuv420p -an \
  -movflags +faststart .private/demo-release/terminal-compact.mp4

ffmpeg -nostdin -v error -xerror -n -ss 13.5 -t 20 \
  -i .private/demo-release/terminal-compact.mp4 \
  -filter_complex '[0:v]fps=10,split[frames][colors];[colors]palettegen=stats_mode=diff[palette];[frames][palette]paletteuse=dither=none' \
  -loop 0 .private/demo-release/terminal-compact.gif
```

Watch the new files before replacing `docs/demo.mp4` and `docs/demo.gif`.
Check the visible headline, selected change, assumed cost, and `EXACT` status
against the live result. The GIF must visibly include the command and result.
If its timing needs to change, update the excerpt start in both the command
and checker together, then review again.

Rerecord when the graph, result, or console output changes. Matching a GIF to
its video does not establish that the recorded text is current. Run the checker
again after replacing reviewed assets, and verify playback from the public README.
The 90 seconds include reading pauses and a final still, not a runtime benchmark.

## Share the result

```text
For the Fortune 600 chain reported in Armadin, Kill Chains and Coffee, episode 4, Lumon selects 1 modeled change at minimum cost to sever the 1 supplied source-validated path under the stated cost assumptions; the podcast separately reports 12 remote-code-execution findings.

https://github.com/annorak/lumon
```
