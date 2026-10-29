"""Tests of how pyfaradaycup sets up logging."""

from __future__ import annotations

import datetime
import importlib
import logging
import re
from typing import TYPE_CHECKING, Any

import pytest

import pyfaradaycup

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterator


def test_package_logger_has_only_null_handler() -> None:
    """Test that importing pyfaradaycup adds only a NullHandler."""
    handlers = logging.getLogger(pyfaradaycup.__name__).handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.NullHandler)


@pytest.mark.parametrize(
    "module_name",
    [
        "pyfaradaycup.decommutator.ccsds_reader_pipeline",
        "pyfaradaycup.decommutator.main",
        "pyfaradaycup.decommutator.swp_spc_l0_to_l05",
    ],
)
def test_module_logger(module_name: str) -> None:
    """Test that each module has a logger named after it with no handlers."""
    module = importlib.import_module(module_name)
    assert module.logger is logging.getLogger(module_name)
    assert not module.logger.handlers
    assert module.logger.propagate


@pytest.fixture(autouse=True)
def _remove_configured_handlers() -> Iterator[None]:
    """Remove handlers added by configure_logging after each test."""
    logger = logging.getLogger("pyfaradaycup")
    level = logger.level
    yield
    for handler in list(logger.handlers):
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)
            handler.close()
    logger.setLevel(level)


def _configured_handlers() -> list[logging.Handler]:
    """Return the handlers on the package logger other than the NullHandler."""
    return [
        handler
        for handler in logging.getLogger("pyfaradaycup").handlers
        if not isinstance(handler, logging.NullHandler)
    ]


def test_configure_logging_console(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that messages at or above ``level`` are printed to stderr."""
    logger = logging.getLogger("pyfaradaycup.decommutator")
    with pyfaradaycup.configure_logging(level=logging.INFO):
        logger.debug("hidden")
        logger.info("shown")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "INFO: shown\n"


def test_configure_logging_level_as_string(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that levels can be given by name."""
    logger = logging.getLogger("pyfaradaycup")
    with pyfaradaycup.configure_logging(level="WARNING"):
        logger.info("hidden")
        logger.warning("shown")
    assert capsys.readouterr().err == "WARNING: shown\n"


@pytest.mark.parametrize("kwargs", [{"level": "LOUD"}, {"file_level": "LOUD"}])
def test_configure_logging_invalid_level(
    tmp_path: pathlib.Path, kwargs: dict[str, Any]
) -> None:
    """Test that an unknown level raises ValueError and adds no handlers."""
    log_file = tmp_path / "run.log"
    with pytest.raises(ValueError, match="Unknown level"):
        pyfaradaycup.configure_logging(log_file=log_file, **kwargs)
    assert not _configured_handlers()
    assert not log_file.exists()


def test_configure_logging_file(tmp_path: pathlib.Path) -> None:
    """Test that the log file has messages at all levels with UTC timestamps."""
    log_file = tmp_path / "new_dir" / "run.log"
    logger = logging.getLogger("pyfaradaycup.decommutator.main")
    before = datetime.datetime.now(datetime.timezone.utc)
    with pyfaradaycup.configure_logging(log_file=log_file, console=False) as config:
        logger.debug("a debug message")
    after = datetime.datetime.now(datetime.timezone.utc)

    assert config.log_file == log_file
    line = log_file.read_text(encoding="utf-8")
    match = re.fullmatch(
        r"(\S+)Z DEBUG    pyfaradaycup\.decommutator\.main: a debug message\n",
        line,
    )
    assert match is not None
    timestamp = datetime.datetime.fromisoformat(match.group(1)).replace(
        tzinfo=datetime.timezone.utc
    )
    assert before - datetime.timedelta(seconds=1) <= timestamp <= after


def test_configure_logging_file_level(tmp_path: pathlib.Path) -> None:
    """Test that ``file_level`` sets the minimum level written to the log file."""
    log_file = tmp_path / "run.log"
    logger = logging.getLogger("pyfaradaycup")
    with pyfaradaycup.configure_logging(
        log_file=log_file, file_level=logging.WARNING, console=False
    ):
        logger.info("hidden")
        logger.warning("shown")
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert lines[0].endswith("WARNING  pyfaradaycup: shown")


def test_configure_logging_file_mode_append(tmp_path: pathlib.Path) -> None:
    """Test that the log file is appended to by default."""
    log_file = tmp_path / "run.log"
    log_file.write_text("existing line\n", encoding="utf-8")
    with pyfaradaycup.configure_logging(log_file=log_file, console=False):
        logging.getLogger("pyfaradaycup").info("new line")
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "existing line"
    assert lines[1].endswith("new line")


def test_configure_logging_file_mode_exclusive(tmp_path: pathlib.Path) -> None:
    """Test that ``file_mode="x"`` refuses to overwrite an existing log file."""
    log_file = tmp_path / "run.log"
    log_file.touch()
    with pytest.raises(FileExistsError):
        pyfaradaycup.configure_logging(log_file=log_file, file_mode="x")
    assert not _configured_handlers()


def test_configure_logging_close(tmp_path: pathlib.Path) -> None:
    """Test that closing removes and closes the handlers and restores the level."""
    logger = logging.getLogger("pyfaradaycup")
    logger.setLevel(logging.ERROR)
    config = pyfaradaycup.configure_logging(
        level=logging.WARNING, log_file=tmp_path / "run.log"
    )
    assert _configured_handlers() == config.handlers
    assert logger.level == logging.DEBUG

    config.close()
    assert not _configured_handlers()
    assert logger.level == logging.ERROR
    file_handler = config.handlers[-1]
    assert isinstance(file_handler, logging.FileHandler)
    assert file_handler.stream is None

    config.close()  # closing again has no further effect
    assert logger.level == logging.ERROR


def test_configure_logging_replaces_earlier_handlers(tmp_path: pathlib.Path) -> None:
    """Test that a second call replaces only the handlers from the first."""
    logger = logging.getLogger("pyfaradaycup")
    other_handler = logging.StreamHandler()
    logger.addHandler(other_handler)

    first = pyfaradaycup.configure_logging(log_file=tmp_path / "first.log")
    second = pyfaradaycup.configure_logging(level=logging.WARNING)
    assert _configured_handlers() == [other_handler, *second.handlers]
    assert logger.level == logging.WARNING

    # Closing the replaced configuration leaves the new one in place.
    first.close()
    assert _configured_handlers() == [other_handler, *second.handlers]
    assert logger.level == logging.WARNING


def test_configure_logging_no_handlers() -> None:
    """Test that disabling every destination removes earlier handlers."""
    pyfaradaycup.configure_logging()
    config = pyfaradaycup.configure_logging(console=False)
    assert config.handlers == []
    assert config.log_file is None
    assert not _configured_handlers()


def test_configure_logging_propagates(caplog: pytest.LogCaptureFixture) -> None:
    """Test that messages still propagate to the root logger."""
    with pyfaradaycup.configure_logging(console=False):
        logging.getLogger("pyfaradaycup").warning("propagated")
    assert caplog.messages == ["propagated"]
