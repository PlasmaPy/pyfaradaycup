"""
Test converting L0 files in a Dagster asset.

These tests are skipped unless Dagster is installed, which it is only in
the ``dagster_with_coverage`` nox session.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from pyfaradaycup.decommutator import _l0_to_l05, l0_to_l05

if TYPE_CHECKING:
    from collections.abc import Callable

dagster = pytest.importorskip("dagster")

l0file = (
    Path(__file__).parent.parent / "data/sci/sweap/raw/ssr/2026/215/0523462910_4_EA"
)

# Dagster and its dependencies can issue warnings on import or during a
# run, which would otherwise be treated as errors.
pytestmark = pytest.mark.filterwarnings("ignore")


def _materialize(tmp_path: Path, body: Callable[[], Any]) -> Any:  # ruff:ignore[ANN401]
    """Materialize an asset that returns what ``body`` returns."""

    @dagster.asset
    def l05_cdf_files() -> Any:  # ruff:ignore[ANN401]
        return body()

    instance_dir = tmp_path / "dagster"
    instance_dir.mkdir()
    with dagster.DagsterInstance.local_temp(tempdir=str(instance_dir)) as instance:
        return dagster.materialize(
            [l05_cdf_files], instance=instance, raise_on_error=False
        )


def test_l0_to_l05_in_dagster_asset(tmp_path: Path) -> None:
    """
    Test that an asset can convert an L0 file and record the result as
    metadata of the materialization.
    """
    l05dir = tmp_path / "l05"

    def body() -> Any:  # ruff:ignore[ANN401]
        result = l0_to_l05(l0file, l05dir=l05dir, apidreq=0x352, raise_on_failure=True)
        return dagster.MaterializeResult(metadata=result.to_metadata())

    result = _materialize(tmp_path, body)
    assert result.success
    (materialization,) = result.asset_materializations_for_node("l05_cdf_files")
    metadata = materialization.metadata
    assert metadata["succeeded"].value is True
    assert metadata["cdf_files"].value == {
        "0x352": str(l05dir / "0523462910_4_EA_APID352_L1.cdf")
    }
    assert metadata["l0file"].value == str(l0file)


def test_l0_to_l05_failure_fails_dagster_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Test that an APID that cannot be converted fails the asset when
    ``raise_on_failure=True``, with the reason in the error.
    """
    monkeypatch.setattr(
        _l0_to_l05, "_get_newest_skeleton", lambda _apid: str(tmp_path / "missing")
    )

    def body() -> None:
        l0_to_l05(l0file, l05dir=tmp_path, apidreq=0x352, raise_on_failure=True)

    result = _materialize(tmp_path, body)
    assert not result.success
    (failure,) = result.get_step_failure_events()
    error = failure.step_failure_data.error
    assert "DecommutationError" in error.to_string()
    assert "0x352: Could not read skeleton file" in error.to_string()
