.. basic test documentation master file, created by
   sphinx-quickstart on Thu May 19 21:05:52 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

MEASURE TIME TEST
=================

.. toctree::
   :maxdepth: 2
   :caption: Contents:


.. story:: Test story 1
   :id: ST_001
   :status: open

.. story:: Test story 2
   :id: ST_002
   :status: open

.. story:: Test story 3
   :id: ST_003
   :status: open

.. story:: Test story 4
   :id: ST_004
   :status: closed
   :tags: [[another_func()]]

.. story:: Test story 5
   :id: ST_005
   :status: closed
   :tags: [[dyn_func()]]

.. story:: Test story 6
   :id: ST_006
   :status: closed
   :tags: [[dyn_func()]]

.. story:: Test story 7
   :id: ST_007
   :status: closed
   :tags: [[dyn_func()]]

Filtering
---------

.. needtable::
   :export_id: needtable_1
   :filter: status == "open"

.. needtable::
   :filter-func: filters.own_filter_code

.. needflow::
   :filter: status == "open"


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
