.. basic test documentation master file, created by
   sphinx-quickstart on Thu May 19 21:05:52 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Page 1
------

.. test:: Test story
   :id: TEST_001
   :status: open

.. story:: test 3
   :id: TEST_003
   :links: TEST_001
   :status: closed


.. needextend:: ST_001
   :+status: _extended

The is :need:`TEST_001`


.. needtable::
   :filter: status == "open"


.. needpie::

   status == "open"
   status == "closed"


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
