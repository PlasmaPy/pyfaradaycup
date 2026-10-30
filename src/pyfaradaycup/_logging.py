"""Configure logging for pyfaradaycup from Python or the command line."""

from __future__ import annotations

__all__ = ["LoggingConfiguration", "configure_logging"]

import logging
import pathlib
import time
from typing import TYPE_CHECKING, Literal, final

if TYPE_CHECKING:
    import os
    import types

_PACKAGE_LOGGER_NAME = "pyfaradaycup"

# The logger used by logging.captureWarnings
_WARNINGS_LOGGER_NAME = "py.warnings"

# Handlers added by configure_logging are named with this prefix, so
# that a later call can find and replace them without touching handlers
# added by anyone else.
_HANDLER_NAME_PREFIX = "pyfaradaycup.configure_logging."

# Timestamps are ISO 8601 in UTC, like 2026-10-29T14:23:01.123Z.
_FILE_FORMAT = "%(asctime)s.%(msecs)03dZ %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_CONSOLE_FORMAT = "%(levelname)s: %(message)s"


@final
class LoggingConfiguration:
    """
    Handlers that `~pyfaradaycup.configure_logging` added to the
    ``pyfaradaycup`` logger.

    Use `close` or a ``with`` block to remove and close the handlers.
    Instances should be created with `~pyfaradaycup.configure_logging`
    rather than directly.

    Parameters
    ----------
    handlers : list of `logging.Handler`
        The handlers that were added to the ``pyfaradaycup`` logger.

    log_file : `pathlib.Path` or `None`
        The path to the log file, or `None` if there is no log file.

    previous_level : int
        The level of the ``pyfaradaycup`` logger before the handlers
        were added, which is restored by `close`.

    capture_warnings : bool
        Whether the handlers were also added to the ``py.warnings``
        logger, with warnings captured by `logging.captureWarnings`.
    """

    def __init__(
        self,
        handlers: list[logging.Handler],
        log_file: pathlib.Path | None,
        previous_level: int,
        *,
        capture_warnings: bool,
    ) -> None:
        self.handlers = handlers
        self.log_file = log_file
        self.capture_warnings = capture_warnings
        self._previous_level = previous_level

    def close(self) -> None:
        """
        Remove and close the handlers.

        The level of the ``pyfaradaycup`` logger is restored only if
        these handlers had not already been replaced by a later call to
        `~pyfaradaycup.configure_logging`. Calling this method more than
        once has no further effect.
        """
        logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
        warnings_logger = logging.getLogger(_WARNINGS_LOGGER_NAME)
        if any(handler in logger.handlers for handler in self.handlers):
            logger.setLevel(self._previous_level)
        if self.capture_warnings and any(
            handler in warnings_logger.handlers for handler in self.handlers
        ):
            logging.captureWarnings(False)  # ruff:ignore[FBT003]
        for handler in self.handlers:
            logger.removeHandler(handler)
            warnings_logger.removeHandler(handler)
            handler.close()

    def __enter__(self) -> LoggingConfiguration:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        self.close()


def configure_logging(  # ruff:ignore[PLR0913]
    *,
    level: int | str = logging.INFO,
    log_file: str | os.PathLike[str] | None = None,
    file_level: int | str = logging.DEBUG,
    file_mode: Literal["a", "w", "x"] = "a",
    console: bool = True,
    capture_warnings: bool = False,
) -> LoggingConfiguration:
    """
    Send log messages from pyfaradaycup to the console and a log file.

    Handlers are added to the ``pyfaradaycup`` logger only, so logging
    for other packages and the root logger is left unchanged. Calling
    this function again replaces the handlers added by earlier calls.

    Parameters
    ----------
    level : int or str, default: ``logging.INFO``
        The minimum level of messages printed to standard error, such as
        ``logging.DEBUG`` or ``"WARNING"``.

    log_file : path-like, optional
        The path to a log file. Missing parent directories are created.
        If not provided, no log file is written.

    file_level : int or str, default: ``logging.DEBUG``
        The minimum level of messages written to ``log_file``.

    file_mode : {"a", "w", "x"}, default: ``"a"``
        Whether to append to ``log_file``, overwrite it, or require that
        it does not already exist.

    console : bool, default: `True`
        If `True`, print messages to standard error.

    capture_warnings : bool, default: `False`
        If `True`, send warnings issued with `warnings.warn` to the same
        console and log file, using `logging.captureWarnings`. This
        changes how warnings are shown for the whole program until the
        handlers are closed, so it is intended for applications such as
        command line tools.

    Returns
    -------
    `~pyfaradaycup._logging.LoggingConfiguration`
        The added handlers. Use it in a ``with`` block, or call its
        ``close`` method, to remove and close them.

    Raises
    ------
    ValueError
        If ``level`` or ``file_level`` is not a known logging level.

    FileExistsError
        If ``file_mode`` is ``"x"`` and ``log_file`` already exists.

    Notes
    -----
    Messages are written to the log file with timestamps in UTC, in
    ISO 8601 format.

    Messages still propagate to the root logger. If the root logger also
    prints to the console, as it does after `logging.basicConfig`, then
    use ``console=False`` to avoid printing each message twice.

    Examples
    --------
    To print messages at the ``INFO`` level and above, and to write all
    messages to a log file while decommutating:

    >>> import pyfaradaycup
    >>> with pyfaradaycup.configure_logging(log_file="run.log"):  # doctest: +SKIP
    ...     ...  # decommutate here
    """
    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)

    handlers: list[logging.Handler] = []
    if console:
        console_handler = logging.StreamHandler()
        console_handler.set_name(f"{_HANDLER_NAME_PREFIX}console")
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
        handlers.append(console_handler)

    log_path = None if log_file is None else pathlib.Path(log_file)
    if log_path is not None:
        handlers.append(_make_file_handler(log_path, file_level, file_mode))

    _remove_configured_handlers(capture_warnings=capture_warnings)

    warnings_logger = logging.getLogger(_WARNINGS_LOGGER_NAME)
    previous_level = logger.level
    for handler in handlers:
        logger.addHandler(handler)
        if capture_warnings:
            warnings_logger.addHandler(handler)
    if handlers:
        logger.setLevel(min(handler.level for handler in handlers))
    if capture_warnings:
        logging.captureWarnings(True)  # ruff:ignore[FBT003]

    return LoggingConfiguration(
        handlers, log_path, previous_level, capture_warnings=capture_warnings
    )


def _make_file_handler(
    log_path: pathlib.Path,
    level: int | str,
    mode: Literal["a", "w", "x"],
) -> logging.FileHandler:
    """Create a handler that writes to a log file with UTC timestamps."""
    # Check the level before creating the file, so that an invalid level
    # does not leave an empty log file behind.
    logging.Handler().setLevel(level)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode=mode, encoding="utf-8")
    file_handler.set_name(f"{_HANDLER_NAME_PREFIX}file")
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT)
    file_formatter.converter = time.gmtime
    file_handler.setFormatter(file_formatter)
    return file_handler


def _remove_configured_handlers(*, capture_warnings: bool) -> None:
    """
    Remove and close the handlers added by earlier calls to
    `configure_logging`, and stop capturing warnings if they were
    captured but ``capture_warnings`` is `False`.
    """
    warnings_logger = logging.getLogger(_WARNINGS_LOGGER_NAME)
    for handler in list(warnings_logger.handlers):
        if (handler.name or "").startswith(_HANDLER_NAME_PREFIX):
            warnings_logger.removeHandler(handler)
            if not capture_warnings:
                logging.captureWarnings(False)  # ruff:ignore[FBT003]

    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
    for handler in list(logger.handlers):
        if (handler.name or "").startswith(_HANDLER_NAME_PREFIX):
            logger.removeHandler(handler)
            handler.close()
