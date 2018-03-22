.. _needflow:

needflow
========

.. versionadded:: 0.2.0

Options
-------

.. note:: **needflow** supports the full filtering possibilities of sphinx-needs.
          Please see :ref:`filter` for more information.

Supported options:

 * :ref:`needflow_columns`
  * :ref:`option_status`
 * :ref:`option_tags`
 * :ref:`option_types`
 * :ref:`option_filter`


.. _needflow_columns:

columns
~~~~~~~
Needs a comma/semicolon separated string, which is used to define the position of specific columns.
For instance::

    .. needtable::
       :columns: id;title;tags


This will show the columns *id*, *title* and *tags* in the given order.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needtable::
         :columns: id;title;tags

   .. needtable::
      :tags: test
      :columns: id;title;tags
      :style: table


Supported columns are: