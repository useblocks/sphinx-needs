.. _performance_script:

Performance & Profiling script
==============================

.. note::

   The performance script got its own Sphinx extension:
   `Sphinx-Performance <https://sphinx-performance.readthedocs.io/en/latest/>`_.

   This extension is based on the described script, but is more powerfull and better maintained.
   It can also be used for general performance analysis of Sphinx and its extensions.

The performance of **Sphinx-Needs** can be tested by a script called ``performance_test.py`` inside
folder ``/performance`` of the checked out github repository.

The performance can be tested with different amounts of ``needs``, ``needtables`` and not Sphinx-Needs related
``dummies`` (simple rst code).

Test series
-----------

To start a series of test with some predefined values, run ``python performance_test.py series``

.. .. program-output:: python ../performance/performance_test.py series
.. literalinclude:: series_output.txt

But you can modify the details and set some static values by setting various parameters.
Just run ``python performance_test.py series --help`` to get an overview

.. .. program-output:: python ../performance/performance_test.py series --help
.. literalinclude:: help.txt

Also if ``--needs``, ``--pages`` or ``parallel`` is set multiple times, one performance test is executed per it.

Example:: ``python performance_test.py series --needs 1 --needs 10 --pages 1 --pages 10 --parallel 1 --parallel 4 --needtables 0 --dummies 0``.
This will set 2 values for ``needs``, 2 for ``pages`` and 2 for parallel. So in the end it will run **8** test
configurations (2 needs x 2 pages x 2 parallel = 8).


.. .. program-output:: python ../performance/performance_test.py series --needs 1 --needs 10 --pages 1 --pages 10 --parallel 1 --parallel 4 --needtables 0 --dummies 0
.. literalinclude:: complex.txt

Parallel execution
------------------
:versionadded: 0.7.1

You may have noticed, the parallel execution on multiple cores can lower the needed runtime.

This parallel execution is using the
`"-j" option from sphinx-build <https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-j>`_.
This mostly brings benefit, if dozens/hundreds of files need to be read and written.
In this case sphinx starts several workers to deal with these files in parallel.

If the project contains only a few files, the benefit is not really measurable.

Here an example of a 500 page project, build once on 1 and 8 cores. The benefit is ``~40%`` of build time, if 8 cores
are used.

.. code-block:: text

      runtime s    pages #    needs per page    needs #    needtables #    dummies #    parallel cores
    -----------  ---------  ----------------  ---------  --------------  -----------  ----------------
         169.46        500                10       5000               0         5000                 1
         103.08        500                10       5000               0         5000                 8

Used command: ``python performance_test.py series --needs 10 --pages 500 --dummies 10 --needtables 0 --parallel 1 --parallel 8``

The parallel execution can used by any documentation build , just use `-j` option.
Example, which uses 4 processes in parallel: ``sphinx-build -j 4 -b html . _build/html``


Used rst template
-----------------
For all performance tests the same rst-template is used:

index
~~~~~
.. literalinclude:: /../performance/project/index.template

pages
~~~~~
.. literalinclude:: /../performance/project/page.template

.. _profiling:

Profiling
---------
With option ``--profile NAME`` a code-area specific profile can be activated.

Currently supported are:

* NEEDTABLE: Profiles the needtable processing (incl. printing)
* NEED_PROCESS: Profiles the need processing (without printing)
* NEED_PRINT: Profiles the need painting (creating final nodes)

If this option is used, a ``profile`` folder gets created in the current working directory and a profile file with
``<NAME>.prof`` is created. This file contains
`CProfile Stats <https://docs.python.org/3/library/profile.html#pstats.Stats>`_ information.

``--profile`` can be used several times.

These profile can be also created outside the performance test with each documentation project.
Simply set a environment variable called ``NEEDS_PROFILING`` and set the value to the needed profiles.

Example for Linux: ``export NEEDS_PROFILING=NEEDTABLE,NEED_PRINT``.



Analysing profile
~~~~~~~~~~~~~~~~~
Use ``snakeviz`` together with ``--profile <NAME>`` to open automatically a graphical analysis of the generated
profile file.

For this ``snakeviz`` must be installed: ``pip install snakeviz``.

Example::

    python performance_test.py series --needs 10 --pages 10 --profile NEEDTABLE --profile NEED_PROCESS --snakeviz

.. image:: /_images/snakeviz_needtable.png
   :width: 80%
   :align: center

Measurements
------------
The measurements were performed with the following setup:

* Sphinx-Needs **0.7.0** on **1** core as parallel build is not supported by version.
* Sphinx-Needs **0.7.1**, with **1** core.
* Sphinx-Needs **0.7.1**, with **4** cores.


.. list-table::
   :header-rows: 1
   :stub-columns: 1

   * - Test details
     - 0.7.0 with 1 core
     - 0.7.1 with 1 core
     - 0.7.1 with 4 cores
   * - 30 pages with overall 1500 needs and 30 needtables
     - 55.02 s
     - 36.81 s
     - 34.31 s
   * - 100 pages with overall 10.000 needs and 100 needtables
     - 6108.26 s
     - 728.82 s
     - 564.76 s
