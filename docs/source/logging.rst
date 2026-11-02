.. _logging:

=======
Logging
=======

pyFaradayCup reports log messages through the ``pyfaradaycup`` logger
from Python's `logging` module. These messages are not shown unless the
application chooses where to send them. Applications that do not already
manage logging can use `~pyfaradaycup.configure_logging` to send them to
the console and a log file.

.. _logging-concepts:

Logging concepts
================

These terms from Python's `logging` module are used throughout this page
and in `~pyfaradaycup.configure_logging`.

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

.. _logging-dagster:

Using Dagster
=============

Dagster has its own system for collecting log messages, so the
recommended approach is to let Dagster manage the ``pyfaradaycup`` logger
rather than calling `~pyfaradaycup.configure_logging` in a step. To do
this, add the following to :file:`dagster.yaml`:

.. code-block:: yaml

   python_logs:
     managed_python_loggers:
       - pyfaradaycup
     python_log_level: INFO

Messages at ``python_log_level`` and above then appear in the Dagster
event log with their levels. If ``python_log_level`` is not set, then
only messages at the ``WARNING`` level and above appear.

.. warning::

   Do not call `~pyfaradaycup.configure_logging` in a step while Dagster
   manages the ``pyfaradaycup`` logger. Doing so has these effects:

   - The call changes the level of the logger, overriding
     ``python_log_level``. With a log file, this sends ``DEBUG`` messages
     to the event log by default.
   - Dagster adds its job name, run ID, and step name to each message
     before the handlers from `~pyfaradaycup.configure_logging` receive
     it, so these details also appear in the log file and on the console.
   - Messages printed to the console are duplicated in the compute logs.

If a step needs a separate log file with unaltered messages, leave
``pyfaradaycup`` out of ``managed_python_loggers``, and call
`~pyfaradaycup.configure_logging` inside the step:

.. code-block:: python

   with pyfaradaycup.configure_logging(log_file=log_file, console=False):
       ...  # decommutate here

Messages then go to the log file but not to the Dagster event log.

Handlers belong to a single process, and each call to
`~pyfaradaycup.configure_logging` replaces the handlers from the previous
call in that process. Steps should therefore not call it while running
concurrently in threads of the same process. Steps should also use a
different log file for each step, since a ``file_mode`` of ``"overwrite"``
would overwrite the log of another step and ``"exclusive"`` would raise
an exception.
