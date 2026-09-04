.. basic test documentation master file, created by
   sphinx-quickstart on Thu May 19 21:05:52 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to basic test's documentation!
======================================

 little more complex basic doc for latex

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   page_1
   page_2


.. story:: Test story
   :id: ST_001
   :status: open

.. story:: No ID
   :status: open

.. story:: Story 3
   :id: ST_003
   :links: ST_001
   :status: closed

The is :need:`ST_001`


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
