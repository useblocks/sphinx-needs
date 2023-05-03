.. _runtime_debugging:

Runtime debugging
=================

.. versionadded:: 1.3.0

The build time of Sphinx is based on a lot of indicators, especially when Sphinx-Needs is used and self-written
filters and warning functions got registered. Then it might happen that a build gets quite slow and it is hard to figure
out why this is the case.

To get an overview about what takes how long, an integrated time measurement is available, which
supports user defined elements and internal functions.

To activate it, simply add the following to the project ``conf.py`` file::

   needs_debug_measurement = True

This will perform measurements and gives some output in three formats:

* Some basic stats on the command line after the build
* A JSON file ``debug_measurement.json`` in the current build folder, which contains **all** captured data
* A HTML report ``debug_measurement.html`` in the current build folder.

.. figure:: /_images/sn_debug_measurement_html_report.png
   :width: 1000%
   :align: center
   :target: ../debug_measurement.html

   HTML report example of timing measurements (*Click to open complete HTML report*)


.. warning::

   Do not use this function in Sphinx parallel mode, as this will result in incorrect data.
   Mainly because the used result variables get not synced between the different worker processes.

Technical details
-----------------
If you need to activate the measurement for additional Sphinx-Needs functions, use the ``measure_time()`` decorator.


.. autofunction:: sphinx_needs.debug.measure_time