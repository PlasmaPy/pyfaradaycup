.. _python:

=================================
Converting L0 files from Python
=================================

The :ref:`pfc_decommutator <cli>` command line tool calls
:func:`~pyfaradaycup.decommutator.l0_to_l05`, which can also be called
directly. Calling it from Python is better suited to a pipeline such as
Dagster than running the command line tool in a subprocess, since the
pipeline can then capture exceptions, log messages, and the result.

.. code-block:: python

   from pyfaradaycup.decommutator import l0_to_l05

   result = l0_to_l05("/path/to/0523462910_4_EA", l05dir="/path/to/l05dir")

This writes one L0.5 CDF file for each APID in the L0 file, and returns
a :class:`~pyfaradaycup.decommutator.DecommutationResult` with the CDF
files that were written, the APIDs that could not be converted, and the
inputs and software versions that were used. Every argument other than
the L0 file must be given by keyword.

Handling failures
=================

An APID that cannot be converted, for example because its CDF skeleton
is missing, does not stop the other APIDs from being converted. By
default, the reason is recorded in
:attr:`~pyfaradaycup.decommutator.DecommutationResult.failures` and no
exception is raised, so a caller that ignores the result can mistake a
partial conversion for a successful one. To raise a
:class:`~pyfaradaycup.decommutator.DecommutationError` instead, either
pass ``raise_on_failure=True``, or call
:meth:`~pyfaradaycup.decommutator.DecommutationResult.raise_for_failures`
on the result:

.. code-block:: python

   result = l0_to_l05(l0file, l05dir=l05dir, raise_on_failure=True)

The exception has the result in its ``result`` attribute, so the CDF
files that were written can still be found.

Using Dagster
=============

This asset converts one L0 file for each partition, fails if any APID
could not be converted, and records the result as metadata of the
materialization:

.. code-block:: python

   import dagster

   from pyfaradaycup.decommutator import l0_to_l05

   l0_files = dagster.DynamicPartitionsDefinition(name="l0_files")


   @dagster.asset(partitions_def=l0_files)
   def l05_cdf_files(
       context: dagster.AssetExecutionContext,
   ) -> dagster.MaterializeResult:
       result = l0_to_l05(
           context.partition_key,
           l05dir="/path/to/l05dir",
           overwrite=True,
           raise_on_failure=True,
       )
       return dagster.MaterializeResult(metadata=result.to_metadata())

Here the partition key is the path of the L0 file. ``overwrite=True``
lets a retry replace CDF files written by an earlier attempt, which would
otherwise raise a `FileExistsError`.

:meth:`~pyfaradaycup.decommutator.DecommutationResult.to_metadata`
returns the result with paths and APIDs converted to strings, so that it
can be serialized as JSON.

To show log messages from the conversion in the Dagster event log, see
:ref:`logging-dagster`.
