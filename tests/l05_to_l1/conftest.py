"""Fixtures for testing the conversion of L0.5 files into L1 files."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pytest
from spacepy import pycdf

from pyfaradaycup._paths import data_dir

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

repo_root = Path(__file__).parent.parent.parent
spc_dir = repo_root / "_psp" / "data" / "sci" / "sweap" / "spc"
l05_dir = spc_dir / "L05"
l1_dir = spc_dir / "L1"

skeleton_353 = data_dir / "cdf_skeletons" / "psp_swp_spc_l1_353_skeleton.cdf"


def write_l05_file(
    path: Path,
    epoch: Sequence[int],
    seqcnt: Sequence[int] | None = None,
    skeleton: Path = skeleton_353,
) -> Path:
    """
    Write a small L0.5 file from a skeleton.

    Parameters
    ----------
    path : Path
        The file to write. Its parent directories are created.
    epoch : sequence of int
        The ``CDF_TIME_TT2000`` value of each record.
    seqcnt : sequence of int, optional
        The value of ``CCSDS_SeqCnt`` for each record, which identifies
        records in tests. Defaults to ``0, 1, 2, ...``. Every other
        variable is zero.
    skeleton : Path, optional
        The skeleton CDF file, which defaults to the APID353 L1 skeleton.

    Returns
    -------
    Path
        ``path``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    epoch_values = np.asarray(epoch, dtype=np.int64)
    seqcnt_values = (
        np.arange(epoch_values.size) if seqcnt is None else np.asarray(seqcnt)
    )
    cdf = pycdf.CDF(str(path), str(skeleton))
    try:
        for name in cdf:
            var = cdf.raw_var(name)
            dtype = pycdf.lib.numpytypedict[var.type()]
            if name == "Epoch":
                var[...] = epoch_values
            elif name == "CCSDS_SeqCnt":
                var[...] = seqcnt_values.astype(dtype)
            else:
                var[...] = np.zeros(epoch_values.size, dtype=dtype)
    finally:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message="DID_NOT_COMPRESS", category=pycdf.CDFWarning
            )
            cdf.close()
    return path


def read_raw(path: Path, name: str) -> np.ndarray:
    """Return the raw values of a variable in a CDF file."""
    with pycdf.CDF(str(path)) as cdf:
        return np.asarray(cdf.raw_var(name)[...])


@pytest.fixture
def l05_file() -> Callable[..., Path]:
    """Return `write_l05_file`, for writing small L0.5 files."""
    return write_l05_file


@pytest.fixture(name="read_raw")
def read_raw_fixture() -> Callable[[Path, str], np.ndarray]:
    """Return `read_raw`, for reading the raw values of a variable."""
    return read_raw
