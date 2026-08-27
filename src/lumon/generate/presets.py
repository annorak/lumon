"""Named graph shapes the rest of the project generates its test data from.

Sizes are picked against the constraints the later stages actually impose. A path count is
`n_entry_points * branching ** (depth - n_planted_chokepoints) * n_objectives`, and an
intervention count on these graphs is the number of non-entry nodes, since every validated
edge is a `REACHES` and task 06 answers that with one access control per target node.

`TINY` and `WIDE` stay under the 20-intervention brute-force cap so the exact oracle in task
08 can run on them. `REALISTIC` is sized to the engagement that motivates the project: 40
validated paths, against the 38 that engagement reported.
"""

from lumon.generate.params import GeneratorParams

TINY = GeneratorParams(
    seed=1, n_entry_points=1, n_objectives=1, depth=2, branching=2, n_planted_chokepoints=1
)
"""2 paths over 5 nodes, 4 of them non-entry. Small enough to check by hand."""

SMALL = GeneratorParams(
    seed=2, n_entry_points=2, n_objectives=2, depth=3, branching=2, n_planted_chokepoints=1
)
"""16 paths over 9 nodes."""

MEDIUM = GeneratorParams(
    seed=3, n_entry_points=2, n_objectives=2, depth=4, branching=2, n_planted_chokepoints=1
)
"""32 paths over 11 nodes."""

REALISTIC = GeneratorParams(
    seed=4, n_entry_points=5, n_objectives=2, depth=3, branching=2, n_planted_chokepoints=1
)
"""40 paths over 12 nodes: real engagement scale."""

WIDE = GeneratorParams(
    seed=5, n_entry_points=2, n_objectives=2, depth=3, branching=5, n_planted_chokepoints=1
)
"""100 paths over 15 nodes. Many alternate routes, few hops."""

DEEP = GeneratorParams(
    seed=6, n_entry_points=2, n_objectives=1, depth=8, branching=2, n_planted_chokepoints=2
)
"""128 paths over 17 nodes. Long chains, and two chokepoints rather than one."""

PRESETS: dict[str, GeneratorParams] = {
    "TINY": TINY,
    "SMALL": SMALL,
    "MEDIUM": MEDIUM,
    "REALISTIC": REALISTIC,
    "WIDE": WIDE,
    "DEEP": DEEP,
}
"""Every preset by name, for tests and callers that want to sweep all of them."""
