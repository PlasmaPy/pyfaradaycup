"""Convert SPC L0.5 CDF files into daily L1 CDF files."""

__all__ = [
    "SPC_L1_APIDS",
    "NoL05DataError",
    "cdf_merge_to_daily",
    "main",
    "spp_swp_spc_l05_to_l1_date",
    "spp_swp_spc_l05_to_l1_dates",
    "spp_swp_spc_which_apid",
]

from pyfaradaycup.l05_to_l1 import main
from pyfaradaycup.l05_to_l1._spp_swp_spc_l05_to_l1 import (
    SPC_L1_APIDS,
    NoL05DataError,
    spp_swp_spc_l05_to_l1_date,
    spp_swp_spc_l05_to_l1_dates,
    spp_swp_spc_which_apid,
)
from pyfaradaycup.utils.cdf_to_survey import cdf_merge_to_daily
