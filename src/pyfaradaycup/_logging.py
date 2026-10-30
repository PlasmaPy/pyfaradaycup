"""
Configure logging for pyfaradaycup from Python or the command line.

Python's `logging` module is an alternative to ``print`` for reporting
what a program is doing. With ``print``, the code that reports a message
also decides where the message goes. With `logging`, code only reports
the message, and whoever runs the program separately decides which
messages to keep and where to send them. This module makes those
decisions for pyfaradaycup. Several terms are used throughout:

logger
    The object that code calls to report a message, as in
    ``logger.info("Read 12 packets")``. Loggers are identified by name
    and are created with `logging.getLogger`. Asking for the same name
    always returns the same object, so changes to a logger apply to the
    whole program.

level
    How important a message is. The standard levels, from least to most
    important, are ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, and
    ``CRITICAL``, each of which is also an integer. A logger or handler
    with a level ignores messages below that level.

handler
    An object that sends messages to one destination. For example, a
    `logging.StreamHandler` prints messages to the console, and a
    `logging.FileHandler` appends them to a file. A logger can have any
    number of handlers. A message is filtered twice: first by the level
    of the logger where it was reported, and then by the level of each
    handler. For example, a program can write ``DEBUG`` messages to a
    file while printing only ``WARNING`` messages to the console.

formatter
    An object attached to a handler that turns a message into the line
    of text that gets written, for example by adding a timestamp.

propagation
    Loggers form a hierarchy based on their dotted names, so
    ``pyfaradaycup.decommutator`` is a child of ``pyfaradaycup``, and
    every logger descends from the *root logger*. After a logger's own
    handlers receive a message, the message is also passed to the
    handlers of its ancestors. This is why code anywhere in the package
    can report messages to its own logger while the handlers are added
    only to the ``pyfaradaycup`` logger. The levels of the ancestor
    loggers are not checked, but the levels of their handlers are.
"""

from __future__ import annotations

__all__ = ["LoggingConfiguration", "configure_logging"]

import logging
import pathlib
import sys
import time
from typing import TYPE_CHECKING, Literal, TextIO, final

if TYPE_CHECKING:
    import os
    import types

_PACKAGE_LOGGER_NAME = "pyfaradaycup"

# logging.captureWarnings reports warnings from warnings.warn as log
# messages. It reports them to the logger with this name.
_WARNINGS_LOGGER_NAME = "py.warnings"

# The result of the latest call to configure_logging, which the next call
# closes. This leaves alone any handlers added by anyone else, such as an
# application that uses this package.
_latest_configuration: LoggingConfiguration | None = None

# Templates for each line of output. Each %(...)s is filled in by the
# logging module. For example, %(levelname)s becomes INFO, and %(name)s
# becomes the name of the logger that reported the message. Timestamps
# are ISO 8601 in UTC, like 2026-10-29T14:23:01.123Z.
_FILE_FORMAT = "%(asctime)s.%(msecs)03dZ %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_CONSOLE_FORMAT = "%(levelname)s: %(message)s"


class _StderrHandler(logging.StreamHandler):
    """
    A handler that prints messages to the current value of `sys.stderr`.

    A `logging.StreamHandler` keeps using the stream that it was created
    with, even after `sys.stderr` is replaced and that stream is closed.
    Tools such as pytest and click's test runner replace `sys.stderr`.
    """

    def __init__(self) -> None:
        # Skip StreamHandler.__init__, which would assign to stream.
        logging.Handler.__init__(self)

    @property
    def stream(self) -> TextIO:
        return sys.stderr


@final
class LoggingConfiguration:
    """
    The logging setup created by `~pyfaradaycup.configure_logging`.

    This object keeps track of the handlers that were added to the
    ``pyfaradaycup`` logger, so that they can be undone later. A handler
    is an object that sends log messages to one destination, such as the
    console or a file.

    Use `close` or a ``with`` block to stop sending messages to these
    destinations and to close the log file. Instances should be created
    with `~pyfaradaycup.configure_logging` rather than directly.

    Parameters
    ----------
    handlers : list of `logging.Handler`
        The handlers that were added to the ``pyfaradaycup`` logger.

    log_file : `pathlib.Path` or `None`
        The path to the log file, or `None` if there is no log file.

    previous_level : int
        The level of the ``pyfaradaycup`` logger before the handlers
        were added, which is restored by `close`. A logger ignores
        messages below its level.

    capture_warnings : bool
        Whether warnings issued with `warnings.warn` are also being sent
        to the handlers. If `True`, the handlers were also added to the
        ``py.warnings`` logger, which receives these warnings after
        calling `logging.captureWarnings`.
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
        Stop sending messages to these handlers, and close them.

        Closing a handler flushes any buffered messages and closes its
        log file, if it has one.

        The level of the ``pyfaradaycup`` logger is restored only if
        these handlers had not already been replaced by a later call to
        `~pyfaradaycup.configure_logging`, so that this method does not
        interfere with the newer handlers. Calling this method more than
        once has no further effect.
        """
        logger = logging.getLogger(_PACKAGE_LOGGER_NAME)
        warnings_logger = logging.getLogger(_WARNINGS_LOGGER_NAME)
        if any(handler in logger.handlers for handler in self.handlers):
            logger.setLevel(self._previous_level)
        if self.capture_warnings and any(
            handler in warnings_logger.handlers for handler in self.handlers
        ):
            logging.captureWarnings(capture=False)
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

    Log messages are progress reports and diagnostics that the package
    creates with Python's `logging` module instead of ``print``. Each
    message has a level that says how important it is. From least to
    most important, the levels are ``DEBUG``, ``INFO``, ``WARNING``,
    ``ERROR``, and ``CRITICAL``. Unless this function or the application
    sets up somewhere for them to go, these messages are not shown.

    This function adds *handlers*, which are objects that send messages
    to one destination, such as the console or a file. They are added to
    the *logger* named ``pyfaradaycup``, which is the object that
    receives all messages from this package. Logging for other packages
    is left unchanged. Calling this function again replaces the handlers
    added by earlier calls, and restores the logger to the level it had
    before the first of those calls.

    Parameters
    ----------
    level : int or str, default: ``logging.INFO``
        The minimum level of messages printed to standard error, such as
        ``logging.DEBUG`` or ``"WARNING"``. Strings must be uppercase.

    log_file : path-like, optional
        The path to a log file. Missing parent directories are created.
        If not provided, no log file is written.

    file_level : int or str, default: ``logging.DEBUG``
        The minimum level of messages written to ``log_file``. The
        default keeps every message, so a log file can contain more
        detail than is printed to the console.

    file_mode : {"a", "w", "x"}, default: ``"a"``
        Whether to append to ``log_file``, overwrite it, or require that
        it does not already exist.

    console : bool, default: `True`
        If `True`, print messages to standard error.

    capture_warnings : bool, default: `False`
        If `True`, send warnings issued with `warnings.warn` to the same
        console and log file, using `logging.captureWarnings`. This
        changes how warnings from all packages are shown for the whole
        program until the handlers are closed, so it is intended for
        applications such as command line tools rather than for
        libraries. This has no effect if ``console`` is `False` and
        ``log_file`` is not provided.

    Returns
    -------
    `~pyfaradaycup._logging.LoggingConfiguration`
        An object that keeps track of the added handlers. Use it in a
        ``with`` block, or call its ``close`` method, to stop sending
        messages to the console and log file and to close the file.

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

    Messages are also passed along to the *root logger*, which is the
    program-wide logger that applications often set up, and it may have
    its own handlers. If the root logger also prints to the console, as
    it does after `logging.basicConfig`, then use ``console=False`` to
    avoid printing each message twice.

    The level of the ``pyfaradaycup`` logger is set to the lowest level
    of its new handlers, so a log file lowers it to ``DEBUG`` by default.
    Messages passed along to the root logger are filtered by the levels
    of its handlers, but not by the level of the root logger itself. A
    handler created by ``logging.basicConfig(level="WARNING")`` has no
    level of its own, so it would print these ``DEBUG`` messages. To
    prevent this, set a level on that handler or raise ``file_level``.

    Examples
    --------
    To print messages at the ``INFO`` level and above, and to write all
    messages to a log file while decommutating:

    >>> import pyfaradaycup
    >>> with pyfaradaycup.configure_logging(log_file="run.log"):  # doctest: +SKIP
    ...     ...  # decommutate here
    """
    global _latest_configuration  # ruff:ignore[PLW0603]

    logger = logging.getLogger(_PACKAGE_LOGGER_NAME)

    handlers: list[logging.Handler] = []
    if console:
        console_handler = _StderrHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter(_CONSOLE_FORMAT))
        handlers.append(console_handler)

    log_path = None if log_file is None else pathlib.Path(log_file)
    if log_path is not None:
        handlers.append(_make_file_handler(log_path, file_level, file_mode))

    # Closing the earlier configuration restores the original level of the
    # logger, which then becomes the level for this configuration to restore.
    if _latest_configuration is not None:
        _latest_configuration.close()

    warnings_logger = logging.getLogger(_WARNINGS_LOGGER_NAME)
    previous_level = logger.level
    for handler in handlers:
        logger.addHandler(handler)
        if capture_warnings:
            warnings_logger.addHandler(handler)
    if handlers:
        # The logger filters messages before its handlers see them, so
        # its level must let through what the most verbose handler wants.
        logger.setLevel(min(handler.level for handler in handlers))
    # Warnings stay as they are when there is nowhere to send them.
    capture_warnings = capture_warnings and bool(handlers)
    if capture_warnings:
        logging.captureWarnings(True)  # ruff:ignore[FBT003]

    _latest_configuration = LoggingConfiguration(
        handlers, log_path, previous_level, capture_warnings=capture_warnings
    )
    return _latest_configuration


def _make_file_handler(
    log_path: pathlib.Path,
    level: int | str,
    mode: Literal["a", "w", "x"],
) -> logging.FileHandler:
    """Create a handler that writes to a log file with UTC timestamps."""
    # Check the level before creating the file, so that an invalid level
    # does not leave an empty log file behind. Setting the level on a
    # throwaway handler raises ValueError if the level is not valid.
    logging.Handler().setLevel(level)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode=mode, encoding="utf-8")
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(_FILE_FORMAT, datefmt=_DATE_FORMAT)
    # Formatters use local time unless told otherwise.
    file_formatter.converter = time.gmtime
    file_handler.setFormatter(file_formatter)
    return file_handler
