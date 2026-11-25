"""Test that modules can be imported."""

import importlib

import pytest

from pyfaradaycup.decommutator import (
    DecommutationError,
    DecommutationResult,
    _l0_to_l05,
    l0_to_l05,
)


@pytest.mark.parametrize(
    "package_name",
    [
        "pyfaradaycup",
        "pyfaradaycup.decommutator",
        "pyfaradaycup.decommutator.ccsds_reader",
        "pyfaradaycup.l05_to_l1",
        "pyfaradaycup.l05_to_l1.main",
        "pyfaradaycup.l1_to_l2",
        "pyfaradaycup.l1_to_l2.swp_spc_l12l2_35f",
        "pyfaradaycup.l1_to_l2._calibration",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_get_currents",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_apid35x_to_ivt",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_config_and_hsk_lookup",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalk_correct",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_ev2kms",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalks",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_crosstalk_correction_factor",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_flagfullscanwindows",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_get_effective_area",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_get_gainoffsets",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_get_gains",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_get_startdate",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_hvpsthermalcorrection",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_ivt_to_spectra",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_l1_to_l2_date",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_merge_ivt",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_moments",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_parse_cycles",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_sincosgain2curr",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_spectra_to_l2cdf",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_split_l2cdf_by_mode",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_totalharmonicdistortion",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_voltwin2kmswin",
        "pyfaradaycup.l1_to_l2._spp_swp_spc_win2volt",
        "pyfaradaycup.l1_to_l2.main",
        "pyfaradaycup.l2_to_l3",
        "pyfaradaycup.l2_to_l3._spp_swp_spc_get_angle_table",
        "pyfaradaycup.l2_to_l3._spp_swp_spc_get_angles",
        "pyfaradaycup.l2_to_l3._spp_swp_spc_l3i_flagnames",
        "pyfaradaycup.l2_to_l3._spp_swp_spc_load_l2",
        "pyfaradaycup.l2_to_l3._spp_swp_spc_pmax_response",
        "pyfaradaycup.l2_to_l3._spp_swp_spc_splineinvert",
        "pyfaradaycup.l2_to_l3._spp_swp_spc_zmoments",
        "pyfaradaycup.utils",
        "pyfaradaycup.utils.cdf_to_survey",
        "pyfaradaycup.utils.idl",
    ],
)
def test_import(package_name: str) -> None:
    """Test that the package, subpackage, and modules can be imported."""
    module = importlib.import_module(package_name)
    assert module is not None


def test_decommutator_exports() -> None:
    """
    Test that the function for converting L0 files, its result, and its
    exception can be imported from the subpackage, and are the ones in
    ``_l0_to_l05``.
    """
    assert l0_to_l05 is _l0_to_l05.l0_to_l05
    assert DecommutationResult is _l0_to_l05.DecommutationResult
    assert DecommutationError is _l0_to_l05.DecommutationError
