.. _needtable:

needtable
=========

.. versionadded:: 0.2.0

Options
-------

.. note:: **needtable** supports the full filtering possibilities of sphinx-needs.
          Please see :ref:`filter` for more information.

Supported options:

 * :ref:`needtable_columns`
 * :ref:`needtable_show_filters`
 * :ref:`needtable_style`
 * :ref:`option_status`
 * :ref:`option_tags`
 * :ref:`option_types`
 * :ref:`option_filter`


.. _needtable_columns:

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

* id
* title
* type
* status
* tags
* incoming
* outgoing

If **:columns:** is set, the value of config parameter :ref:`needs_table_columns` is not used for the current table.


.. _needtable_show_filters:

show_filters
~~~~~~~~~~~~

If set, the used filter is added in front of the table::

   .. needtable::
      :show_filters:


.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needtable::
         :tags: test
         :show_filters:

   .. needtable::
      :tags: test
      :columns: id;title;tags
      :show_filters:


.. _needtable_style:

style
~~~~~
Allows to set a specific style for the current table.

Supported values are:

 * table
 * datatables

Overrides config parameter :ref:`needs_table_style` if set.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needtable::
         :style: table

      .. needtable::
         :style: datatables

   .. needtable::
         :tags: awesome
         :columns: id;title
         :style: table

   .. needtable::
      :tags: awesome
      :columns: id;title
      :style: datatables