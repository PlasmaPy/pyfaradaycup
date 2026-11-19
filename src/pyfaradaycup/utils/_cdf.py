"""Helpers for CDF files that are shared by the steps of the pipeline."""

from __future__ import annotations

__all__ = ["close_cdf"]

import warnings

from spacepy import pycdf


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
