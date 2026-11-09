"""Convert SPC L0 files into L0.5 CDF files."""

__all__ = [
    "DecommutationError",
    "DecommutationResult",
    "ccsds_reader_pipeline",
    "l0_to_l05",
    "main",
]

from pyfaradaycup.decommutator import ccsds_reader_pipeline, main
from pyfaradaycup.decommutator._l0_to_l05 import (
    DecommutationError,
    DecommutationResult,
    l0_to_l05,
)
