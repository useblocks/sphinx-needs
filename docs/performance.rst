Performance
===========
The performance of ``Sphinx-Needs`` can be tested by a script called ``performance_test.py`` inside
folder ``/performance`` of the checked out github repository.

The performance can be tested with different amounts of ``needs``, ``needtables`` and not Sphinx-Needs related
``dummies`` (simple rst code).

Test series
-----------

To start a series of test with a maximum amount of **1000 needs**, run ``python performance_test.py series``

.. program-output:: python ../performance/performance_test.py series

The test series configuration is calculated automatically.
The amounts of needs is reduced with each new round to 10%.
``needtables`` and ``dummies`` starts with a value based on 10% of the needs value.

But you can modify the details and set some static values by setting various parameters.
Just run ``python performance_test.py series --help`` to get an overview

.. program-output:: python ../performance/performance_test.py series --help

Also if ``--needs`` is set multiple times, one performance test is executed per ``--needs``.

Example:: ``python performance_test.py series --needs 150 --needs 175 --needs 200 --needtables 0 --dummies 0``

.. program-output:: python ../performance/performance_test.py series --needs 150 --needs 175 --needs 200 --needtables 0 --dummies 0

Single test
-----------
To run only one specific test, use ``python performance_test.py single``.

.. program-output:: python ../performance/performance_test.py single

A more complex test, which also opens the generated documentation in the browser and prints some more debug information
is
``python performance_test.py single --needs 340 --needtables 2 --dummies 0 --debug --browser``

.. program-output:: python ../performance/performance_test.py single --needs 340 --needtables 2 --dummies 0 --debug --keep

To see all available options run ``python performance_test.py single --help``.

.. program-output:: python ../performance/performance_test.py single --help


Used rst template
-----------------
For all performance tests the same rst-template is used:

.. literalinclude:: /../performance/project/index.rst
