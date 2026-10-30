.. _logging:

=======
Logging
=======

pyFaradayCup reports log messages through the ``pyfaradaycup`` logger
from Python's `logging` module. These messages are not shown unless the
application chooses where to send them. Applications that do not already
manage logging can use `~pyfaradaycup.configure_logging` to send them to
the console and a log file.

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
different log file for each step, since a ``file_mode`` of ``"w"`` would
overwrite the log of another step and ``"x"`` would raise an exception.
