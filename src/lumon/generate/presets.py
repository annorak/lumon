from lumon.generate.params import GeneratorParams

TINY = GeneratorParams(
    seed=1, n_entry_points=1, n_objectives=1, depth=2, branching=2, n_planted_chokepoints=1
)

SMALL = GeneratorParams(
    seed=2, n_entry_points=2, n_objectives=2, depth=3, branching=2, n_planted_chokepoints=1
)

MEDIUM = GeneratorParams(
    seed=3, n_entry_points=2, n_objectives=2, depth=4, branching=2, n_planted_chokepoints=1
)

REALISTIC = GeneratorParams(
    seed=4, n_entry_points=5, n_objectives=2, depth=3, branching=2, n_planted_chokepoints=1
)

WIDE = GeneratorParams(
    seed=5, n_entry_points=2, n_objectives=2, depth=3, branching=5, n_planted_chokepoints=1
)

DEEP = GeneratorParams(
    seed=6, n_entry_points=2, n_objectives=1, depth=8, branching=2, n_planted_chokepoints=2
)

PRESETS: dict[str, GeneratorParams] = {
    "TINY": TINY,
    "SMALL": SMALL,
    "MEDIUM": MEDIUM,
    "REALISTIC": REALISTIC,
    "WIDE": WIDE,
    "DEEP": DEEP,
}
