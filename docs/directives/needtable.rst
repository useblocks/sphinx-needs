.. _needtable:

needtable
=========

.. versionadded:: 0.2.0

**needtable** generates a table, based on the result of given filters.

.. code-block:: rst

   .. needtable::
      :tags: main_example
      :style: table

.. needtable::
   :tags: main_example
   :style: table


Options
-------

.. note:: **needtable** supports the full filtering possibilities of sphinx-needs.
          Please see :ref:`filter` for more information.

Supported options:

 * :ref:`needtable_columns`
 * :ref:`needtable_show_filters`
 * :ref:`needtable_style`
 * :ref:`needtable_show_parts`
 * Common filters:
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
      :style: table


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

   Table with ``:style: table``:

   .. needtable::
         :tags: awesome
         :style: table

   Table with ``:style: datatables``:

   .. needtable::
      :tags: awesome
      :style: datatables

.. _needtable_show_parts:

show_parts
~~~~~~~~~~

.. versionadded:: 0.3.6

Adds an extra table row for each :ref:`need_part` found inside a filtered need.

The part rows are added directly under the related need rows and their id and title get a prefix.

To change the prefix please read :ref:`needs_part_prefix`.

.. needtable::
   :tags: test_table
   :show_parts:
   :columns: id;title;outgoing;incoming
   :style: table

.. container:: toggle

   .. container::  header

      **Show example configuration**

   .. code-block:: rst


      .. req:: Test need with need parts
         :id: table_001

         :np:`(1) Part 1 of requirement`.

         :np:`(2) Part 2 of requirement`.

         :np:`(3) Part 3 of requirement`.

      .. spec:: Specifies part 1
         :id: table_002
         :links: table_001.1

      .. spec:: Specifies part 2
         :id: table_003
         :links: table_001.2

      .. needtable::
         :show_parts:
         :columns: id;title;outgoing;incoming
         :style: table


   .. req:: Test need with need parts
      :id: table_001
      :tags: test_table

      :np:`(1) Part 1 of requirement`.

      :np:`(2) Part 2 of requirement`.

      :np:`(3) Part 3 of requirement`.


   .. spec:: Specifies part 1
      :id: table_002
      :tags: test_table
      :links: table_001.1

   .. spec:: Specifies part 2
      :id: table_003
      :tags: test_table
      :links: table_001.2

