"""Helpers for CDF files that are shared by the steps of the pipeline."""

from __future__ import annotations

__all__ = ["close_cdf", "temporary_path"]

import secrets
import warnings
from typing import TYPE_CHECKING

from spacepy import pycdf

if TYPE_CHECKING:
    import pathlib


def close_cdf(cdf: pycdf.CDF) -> None:
    """
    Close a CDF file.

    spacepy warns when a variable that the CDF skeleton marks for
    compression does not get smaller when compressed, which is harmless,
    so this warning is not shown.

    Parameters
    ----------
    cdf : spacepy.pycdf.CDF
        The CDF file to close.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="DID_NOT_COMPRESS", category=pycdf.CDFWarning
        )
        cdf.close()


def temporary_path(path: pathlib.Path) -> pathlib.Path:
    """
    Return a new path next to ``path``, for writing a CDF file first.

    A CDF file is written at this path and then renamed to ``path`` when
    it is complete, so that ``path`` is never an incomplete file. The
    name starts with ``.`` so that it is hidden, and ends with ``.cdf``,
    because the CDF library adds ``.cdf`` to names that do not end
    with it.

    Parameters
    ----------
    path : pathlib.Path
        The final path of the CDF file.

    Returns
    -------
    pathlib.Path
        A path in the same directory as ``path``, with a random part so
        that it is not used by another run at the same time.
    """
    return path.with_name(f".{path.stem}.{secrets.token_hex(8)}.tmp.cdf")
