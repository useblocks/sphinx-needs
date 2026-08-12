.. _needtable:

needtable
=========

.. versionadded:: 0.2.0

**needtable** generates a table, based on the result of given filters.

.. syntax-example::

   .. needtable:: Example table
      :tags: main_example
      :style: table

We use the argument of a ``needtable`` as caption for the table.

Options
-------

.. note::

    **needtable** supports the full filtering possibilities of **Sphinx-Needs**.
    Please see :ref:`filter` for more information.

Some further options are accepted only for :ref:`ubCode compatibility <ubcode_compat_options>`, and are otherwise ignored.


.. _needtable_columns:

columns
~~~~~~~
A comma/semicolon separated string used to define the position of specific columns.
For instance::

    .. needtable::
       :columns: id;title;tags


This will show the columns *id*, *title* and *tags* in the order given.

.. syntax-example::

   .. needtable::
      :columns: id;title;tags

You can set all options of a need (incl. :ref:`needs_fields`) as a column.
This also includes internal options like ``docname`` (Use ``:layout: debug`` on a need for a complete list)

If you set **:columns:**, the current table will not use the value of config parameter :ref:`needs_table_columns`.

Tables with a lot of columns will get a horizontal scrollbar in HTML output.

**DataTable style**

.. syntax-example::

   .. needtable::
      :tags: test
      :columns: id;title;tags;status;docname;lineno,is_external,is_need;is_part;content

**Normal style**

.. syntax-example::

   .. needtable::
      :tags: test
      :style: table
      :columns: id;title;tags;status;docname;lineno,is_external,is_need;is_part;content

.. _needtable_colwidths:

colwidths
~~~~~~~~~

.. versionadded:: 0.7.4

A comma separated list of lengths or percentages used to define the width of each column.

It has the same meaning as the ``width options`` of
`listtable <https://docutils.sourceforge.io/docs/ref/rst/directives.html#list-table>`_ directive.

.. syntax-example::

  .. needtable::
     :tags: test
     :columns: id,title,status
     :colwidths: 50,40,10
     :style: table

.. _needtable_custom_titles:

Custom column titles
....................
You can customize each column title by following this syntax for its definition: ``OPTION as "My custom title"``.
The characters ``,`` or ``;`` are not allowed.

.. syntax-example::

   .. needtable::
      :tags: test
      :columns: id;title as "Headline"; tags as "Labels"
      :style: table

.. _needtable_show_filters:

show_filters
~~~~~~~~~~~~

If set, we add the used filter above the table:

.. syntax-example::

   .. needtable::
      :tags: test
      :columns: id;title;tags
      :show_filters:
      :style: table

.. _needtable_style:

style
~~~~~
Allows you to set a specific style for the current table.

Supported values are:

* table
* datatables

Overrides config parameter :ref:`needs_table_style` if set.

.. dropdown:: Show example

   .. syntax-example::

      .. needtable::
         :style: table

      .. needtable::
         :style: datatables

.. _needtable_show_parts:

show_parts
~~~~~~~~~~

.. versionadded:: 0.3.6

Adds an extra table row for each :ref:`need_part` found inside a filtered need.

It adds the part rows directly under the related need’s row, and their id and title get a prefix.

To change the prefix please read :ref:`needs_part_prefix`.

.. syntax-example::

   .. needtable::
      :tags: test_table
      :filter: is_need
      :show_parts:
      :columns: id;title;outgoing;incoming
      :style: table

.. dropdown:: Show above example's configuration

   .. syntax-example::

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

.. _needtable_style_row:

style_row
~~~~~~~~~

.. versionadded:: 0.4.1

You can use the ``style_row`` option to set a specific class-attribute for the table-row representation and use **CSS** to select the class-attribute

Also, you can set specific layout for the row.

.. syntax-example::

  .. needtable::
     :tags: ex_row_color
     :style_row: needs_blue_border


Row style based on specific need value
......................................

You can use :ref:`dynamic_functions` to derive the value for ``style_row`` based on a specific value of the
documented need in the row.

.. syntax-example::

   .. needtable::
      :tags: ex_row_color
      :columns: id, title, status
      :style_row: needs_[[copy("status")]]

In this example we set ``style_row`` to ``needs_[[copy("status")]]``, so the status of each need will be
part of the row style.

.. note::

   If ``style_row`` contains whitespaces, they get automatically replaced by ``_`` to get a valid css class name.

   So a copied status value like ``in progress`` will become ``in_progress``.

.. dropdown:: Show used configuration

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

Option to sort the filtered-results based on a key.

The sort-value must be compatible with the options supported by the :ref:`filter_string`, and the addressed need-value
must have the type ``string``, ``float`` or ``int``.

By default, we use ``id_complete`` if we don't set a sort option.

.. syntax-example::

   .. needtable::
      :tags: ex_row_color
      :style: table

In this case, we set the sort option to ``status``. So *EX_ROW_3* is above of *EX_ROW_2*.

.. syntax-example::

   .. needtable::
      :tags: ex_row_color
      :style: table
      :sort: status

.. dropdown:: Show used configuration

   .. code-block:: rst

      .. needtable::
         :tags: ex_row_color
         :style: table

      .. needtable::
         :tags: ex_row_color
         :style: table
         :sort: status

.. note::

   Sorting only works if you use the standard sphinx-table for output: ``:style: table``.
   By default, tables generated with DataTables uses Javascript to sort results.


.. _needtable_class:

class
~~~~~
.. versionadded:: 0.7.4

You can set additional class-names for a ``needtable`` using the ``class`` option. Mostly used for HTML output.
It supports comma separated values and will add classes to the already set classes by Sphinx-Needs.

.. code-block:: css
   :caption: custom.css

    table.class_red_border {
        border: 3px solid red;
    }


.. syntax-example::

   .. needtable::
      :tags: test
      :columns: id,title,status
      :style: table
      :class: class_red_border

.. _needtable_max_items:

max_items
~~~~~~~~~

.. versionadded:: 8.4.0

The maximum number of needs to show.

We apply the limit after filtering and after the :ref:`sort <needtable_sort>`,
so the table keeps the first rows it would otherwise have shown,
and tells the reader how many needs it is hiding.

The limit counts the needs that passed the filter.
A table that also sets :ref:`show_parts <needtable_show_parts>` can therefore render more rows than that,
since the part rows of a kept need are all shown.

``:max_items: 0`` means no limit, also for a project that sets :ref:`needs_views_max_items`.
Without the option, the table shows as many needs as that configuration allows.

.. syntax-example::

   .. needtable::
      :tags: flow_example
      :style: table
      :sort: id
      :max_items: 2

common filters
~~~~~~~~~~~~~~

* :ref:`option_status`
* :ref:`option_tags`
* :ref:`option_types`
* :ref:`option_filter`
