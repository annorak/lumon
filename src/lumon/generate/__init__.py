"""Synthetic attack graphs that arrive with their own answers already attached."""

from lumon.generate.generator import generate
from lumon.generate.params import GeneratorParams
from lumon.generate.presets import DEEP, MEDIUM, PRESETS, REALISTIC, SMALL, TINY, WIDE
from lumon.generate.truth import GroundTruth

__all__ = [
    "DEEP",
    "MEDIUM",
    "PRESETS",
    "REALISTIC",
    "SMALL",
    "TINY",
    "WIDE",
    "GeneratorParams",
    "GroundTruth",
    "generate",
]
