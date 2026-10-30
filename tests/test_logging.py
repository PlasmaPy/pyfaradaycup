"""Tests of how pyfaradaycup sets up logging."""

from __future__ import annotations

import datetime
import io
import logging
import re
import sys
import warnings
from typing import TYPE_CHECKING, Any

import pytest

import pyfaradaycup
from pyfaradaycup import _logging

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Callable, Iterator


def test_package_logger_has_only_null_handler() -> None:
    """Test that importing pyfaradaycup adds only a NullHandler."""
    handlers = logging.getLogger(pyfaradaycup.__name__).handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.NullHandler)


@pytest.fixture(autouse=True)
def _remove_configured_handlers() -> Iterator[None]:
    """Remove handlers added by configure_logging after each test."""
    logger = logging.getLogger("pyfaradaycup")
    level = logger.level
    yield
    latest_configuration = _logging._latest_configuration
    if latest_configuration is not None:
        latest_configuration.close()
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


def test_configure_logging_capture_warnings(tmp_path: pathlib.Path) -> None:
    """Test that warnings go to the log file only while captured."""
    log_file = tmp_path / "run.log"
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        with pyfaradaycup.configure_logging(
            log_file=log_file, console=False, capture_warnings=True
        ) as config:
            warnings.warn("captured", UserWarning, stacklevel=1)
            assert logging.getLogger("py.warnings").handlers == config.handlers
    assert "WARNING  py.warnings:" in log_file.read_text(encoding="utf-8")
    assert "UserWarning: captured" in log_file.read_text(encoding="utf-8")
    assert not logging.getLogger("py.warnings").handlers
    assert warnings.showwarning is not logging._showwarning  # ty: ignore[unresolved-attribute]


def test_configure_logging_replacement_stops_capturing_warnings() -> None:
    """Test that replacing a configuration that captured warnings stops capturing."""
    pyfaradaycup.configure_logging(capture_warnings=True)
    pyfaradaycup.configure_logging()
    assert not logging.getLogger("py.warnings").handlers
    assert warnings.showwarning is not logging._showwarning  # ty: ignore[unresolved-attribute]


def test_configure_logging_replacement_restores_original_level() -> None:
    """Test that closing a replacement restores the level before the first call."""
    logger = logging.getLogger("pyfaradaycup")
    logger.setLevel(logging.ERROR)
    pyfaradaycup.configure_logging(level=logging.DEBUG)
    second = pyfaradaycup.configure_logging(level=logging.WARNING)
    assert logger.level == logging.WARNING
    second.close()
    assert logger.level == logging.ERROR


def test_configure_logging_replacement_without_handlers_restores_level() -> None:
    """Test that replacing a configuration with no handlers restores the level."""
    logger = logging.getLogger("pyfaradaycup")
    logger.setLevel(logging.ERROR)
    pyfaradaycup.configure_logging(level=logging.DEBUG)
    pyfaradaycup.configure_logging(console=False)
    assert logger.level == logging.ERROR


def test_close_without_handlers_leaves_level() -> None:
    """Test that closing a configuration with no handlers leaves the level alone."""
    logger = logging.getLogger("pyfaradaycup")
    config = pyfaradaycup.configure_logging(console=False)
    logger.setLevel(logging.ERROR)
    config.close()
    assert logger.level == logging.ERROR


def test_close_twice_leaves_level_set_after_first_close() -> None:
    """Test that closing a second time does not restore the level again."""
    logger = logging.getLogger("pyfaradaycup")
    config = pyfaradaycup.configure_logging()
    config.close()
    logger.setLevel(logging.ERROR)
    config.close()
    assert logger.level == logging.ERROR


def test_configure_logging_capture_warnings_without_handlers() -> None:
    """Test that warnings are not captured when there is nowhere to send them."""
    with pyfaradaycup.configure_logging(console=False, capture_warnings=True) as config:
        assert not config.capture_warnings
        assert warnings.showwarning is not logging._showwarning  # ty: ignore[unresolved-attribute]


def test_configure_logging_console_uses_current_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the console handler follows replacements of ``sys.stderr``."""
    original = io.StringIO()
    monkeypatch.setattr(sys, "stderr", original)
    logger = logging.getLogger("pyfaradaycup")
    with pyfaradaycup.configure_logging():
        original.close()
        replacement = io.StringIO()
        monkeypatch.setattr(sys, "stderr", replacement)
        logger.info("shown")
    assert replacement.getvalue() == "INFO: shown\n"


def _dagster_event_log_messages(
    tmp_path: pathlib.Path,
    body: Callable[[], None],
    python_logs: dict[str, Any] | None,
) -> list[str]:
    """Run ``body`` in a Dagster asset and return the messages it logged."""
    dagster = pytest.importorskip("dagster")

    @dagster.asset
    def asset() -> None:
        body()

    instance_dir = tmp_path / "dagster"
    instance_dir.mkdir()
    overrides = None if python_logs is None else {"python_logs": python_logs}
    with dagster.DagsterInstance.local_temp(
        tempdir=str(instance_dir), overrides=overrides
    ) as instance:
        result = dagster.materialize([asset], instance=instance)
        assert result.success
        return [
            entry.user_message
            for entry in instance.all_logs(result.run_id)
            if entry.dagster_event is None
        ]


def _log_at_each_level() -> None:
    """Report one message at each of three levels."""
    logger = logging.getLogger("pyfaradaycup.decommutator")
    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")


# Dagster and its dependencies can issue warnings on import or during a
# run, which would otherwise be treated as errors.
@pytest.mark.filterwarnings("ignore")
def test_dagster_managed_logger(tmp_path: pathlib.Path) -> None:
    """Test the configuration for Dagster recommended in the documentation."""
    messages = _dagster_event_log_messages(
        tmp_path,
        _log_at_each_level,
        {"managed_python_loggers": ["pyfaradaycup"], "python_log_level": "INFO"},
    )
    assert "debug message" not in messages
    assert "info message" in messages
    assert "warning message" in messages


@pytest.mark.filterwarnings("ignore")
def test_dagster_unmanaged_logger_with_log_file(tmp_path: pathlib.Path) -> None:
    """Test that a step can write unaltered messages to its own log file."""
    log_file = tmp_path / "run.log"

    def body() -> None:
        with pyfaradaycup.configure_logging(log_file=log_file, console=False):
            _log_at_each_level()

    messages = _dagster_event_log_messages(tmp_path, body, None)
    assert "info message" not in messages
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert [line.split(": ", 1)[1] for line in lines] == [
        "debug message",
        "info message",
        "warning message",
    ]
