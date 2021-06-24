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
 * :ref:`needtable_style_row`
 * :ref:`needtable_sort`
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


All values of a need (incl. :ref:`needs_extra_options`) can be set as column.
This includes also internal values like ``docname`` (Use `:layout: debug` on a need for a complete list)

If **:columns:** is set, the value of config parameter :ref:`needs_table_columns` is not used for the current table.

Tables with a lot of columns will get a horizontal scrollbar in HTML output.

**DataTable style**

.. needtable::
  :tags: test
  :columns: id;title;tags;status;docname;lineno,is_external,is_need;is_part;content

**Normal style**

.. needtable::
  :tags: test
  :style: table
  :columns: id;title;tags;status;docname;lineno,is_external,is_need;is_part;content


.. _needtable_custom_titles:

Custom column titles
....................
Each column can get a customized title by following this syntax for its definition: ``OPTION as "My custom title"``.
The characters ``,`` or ``;`` are not allowed.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

        .. needtable::
          :tags: test
          :columns: id;title as "Headline"; tags as "Labels"
          :style: table

   .. needtable::
      :tags: test
      :columns: id;title as "Headline"; tags as "Labels"
      :style: table








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

.. _needtable_style_row:

style_row
~~~~~~~~~

.. versionadded:: 0.4.1

``style_row`` can be used to set a specific class-attribute for the table-row representation.

The class-attribute can then be addressed by css and specific layout can be set for the row.

.. needtable::
      :tags: ex_row_color
      :style_row: needs_blue_border

.. container:: toggle

   .. container::  header

      **Show used configuration**

   .. code-block:: rst

      .. needtable::
         :tags: ex_row_color
         :style_row: needs_blue_border

Row style based on specific need value
......................................

:ref:`dynamic_functions` can be used to calculate a value for ``style_row`` based on a specific value of the
documented need in the row.

.. needtable::
   :tags: ex_row_color
   :columns: id, title, status
   :style_row: needs_[[copy("status")]]

In this example we set ``style_row`` to ``needs_[[copy("status")]]``, so the status of each need will be
part of the row style.

.. note::

   If ``style_row`` contains whitespaces, they get automatically replaced by ``_`` to get a valid css class name.

   So a copied status value like ``in progress`` will become ``in_progress``.

.. container:: toggle

   .. container::  header

      **Show used configuration**

   **needtable**

   .. code-block:: rst

      .. needtable::
         :tags: ex_row_color
         :columns: id, title, status
         :style_row: needs_[[copy("status")]]

   **needs as input**

   .. req:: Implemented spec
      :id: EX_ROW_1
      :tags: ex_row_color
      :status: implemented

   .. req:: Not implemented spec
      :id: EX_ROW_2
      :tags: ex_row_color
      :status: open

   .. req:: Spec under progress
      :id: EX_ROW_3
      :tags: ex_row_color
      :status: in progress

   **inside a provided css file**

   .. code-block:: css

      tr.needs_implemented {
       background-color: palegreen !important;
      }

      tr.needs_open {
          background-color: palevioletred !important;
      }

      tr.needs_in_progress {
          background-color: palegoldenrod !important;
      }

      /* This sets values for the status column */
      tr.needs_in_progress td.needs_status p {
          background-color: #1b6082;
          padding: 3px 5px;
          text-align: center;
          border-radius: 10px;
          border: 1px solid #212174;
          color: #ffffff;
      }


.. _needtable_sort:

sort
~~~~
.. versionadded:: 0.4.3

``.. needtable::`` provides a ``sort`` option to sort the filter-results for a given key.

The sort-value must be compatible to the options supported by :ref:`filter_string` and the addressed need-value
must be from type ``string``, ``float`` or ``int``.

If no sort option is given, ``id_complete`` is used by default:

.. needtable::
   :tags: ex_row_color
   :style: table

In this case, ``status`` is given for sort. So *EX_ROW_3* is above of *EX_ROW_2*.

.. needtable::
   :tags: ex_row_color
   :style: table
   :sort: status

.. container:: toggle

   .. container::  header

      **Show used configuration**

   .. code-block:: rst

      .. needtable::
         :tags: ex_row_color
         :style: table

      .. needtable::
         :tags: ex_row_color
         :style: table
         :sort: status

.. note::

   Sorting may only work if the standard sphinx-table is used for output: ``:style: table``.
   The default DatabTables table uses Javascript to sort results by its own.


