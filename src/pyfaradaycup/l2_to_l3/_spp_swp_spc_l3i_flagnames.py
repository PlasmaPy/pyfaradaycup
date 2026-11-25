"""Port of ``spp_swp_spc_l3i_flagnames.pro``."""

from __future__ import annotations

__all__ = [
    "DEFAULT_FLAGNAMES",
    "FLAGNAME_LENGTH",
    "N_FLAGS",
    "spp_swp_spc_l3i_flagnames",
]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

N_FLAGS = 32
"""The number of data quality flags in each L3i record."""

FLAGNAME_LENGTH = 70
"""The number of characters in each flag name, as in IDL's ``(A-70)`` format."""

DEFAULT_FLAGNAMES = (
    "(0) general flag",
    "(1) primary peak low signal",
    "(2) no primary peak detected",
    "(3) cold primary peak or current spike detected",
    "(4) sensor saturated",
    "(5) primary peak not bound",
    "(6) poor Maxwellian fit to primary peak",
    "(7) flow direction poorly constrained or undetermined",
    "(8) alpha peak low signal/not identified",
    "(9) poor Maxwellian fit to alpha peak",
    "(10) alpha peak not bound",
    "(11) wind speed off scale high",
    "(12) wind speed off scale low",
    "(13) wind speed off scale unknown",
    "(14) likely proton-alpha confusion",
    "(15) unusually high noise levels detected",
    "(16) proton full-scan mode (not peak-tracking)",
    "(17) reduced data quality: anomalous periodic noise type A (>1 Hz)",
    "(18) reduced data quality: anomalous periodic noise type B (< 1Hz)",
    "(19) temperature/survival heater cycling: potential fluctuations",
    "(20) reduced data quality: broadband or other anomalous noise (type C)",
    "(21) fragmented or incomplete spectrum measured",
    "(22) energy ranging/peak tracking error",
    "(23) spacecraft maneuver",
    "(24) crosstalk in AD, BC pairs. Angle in XZ_{SC} likely affected",
    "(25) crosstalk in AB, BD pairs. Angle in XY_{SC} likely affected",
    "(26) high crosstalk across sensors. Flow angles affected",
    "(27) reduced data quality: low voltage noise",
    "(28) not used/TBD",
    "(29) not used/TBD",
    "(30) not used/TBD",
    "(31) not used/TBD",
)
"""The names of the data quality flags hard-coded in IDL, without padding."""


def _format_a70(name: str) -> str:
    """
    Format ``name`` like IDL's ``string(name, format='(A-70)')``.

    The name is left-justified and padded with spaces to 70 characters,
    or cut to its first 70 characters if it is longer.
    """
    return name[:FLAGNAME_LENGTH].ljust(FLAGNAME_LENGTH)


def spp_swp_spc_l3i_flagnames(flagnames: Sequence[str] | None = None) -> list[str]:
    """
    Return the names of the 32 data quality flags of the L3i files.

    These are written into the ``DQF_flagnames`` variable.

    Parameters
    ----------
    flagnames : sequence of str, optional
        Names to use instead of `DEFAULT_FLAGNAMES`. If there are fewer
        than 32, the rest are empty.

    Returns
    -------
    list of str
        32 names, each padded with spaces (or cut) to 70 characters.

    Raises
    ------
    ValueError
        If there are more than 32 names, where IDL would stop with a
        subscript error.

    Notes
    -----
    The ``version`` keyword of IDL is not ported, since IDL ignores it.
    """
    if flagnames is None:
        flagnames = DEFAULT_FLAGNAMES
    if len(flagnames) > N_FLAGS:
        msg = (
            f"There are {len(flagnames)} flag names, but at most {N_FLAGS} are allowed"
        )
        raise ValueError(msg)
    names = [*flagnames, *[""] * (N_FLAGS - len(flagnames))]
    return [_format_a70(name) for name in names]
