"""Convert SPC L1 CDF files into L2 CDF files."""

__all__ = [
    "main",
    "spp_swp_spc_l1_to_l2_date",
    "spp_swp_spc_split_l2cdf_by_mode",
    "swp_spc_l12l2_35f",
]

from pyfaradaycup.l1_to_l2 import main, swp_spc_l12l2_35f
from pyfaradaycup.l1_to_l2._spp_swp_spc_l1_to_l2_date import spp_swp_spc_l1_to_l2_date
from pyfaradaycup.l1_to_l2._spp_swp_spc_split_l2cdf_by_mode import (
    spp_swp_spc_split_l2cdf_by_mode,
)
