.. _needlist:

needlist
========

.. versionadded:: 0.2.0

**needlist** creates a list of elements based on the result of given filters.

.. syntax-example::

   .. needlist::
      :tags: main_example

Options
-------

.. note::

    **needlist** supports the full filtering possibilities of **Sphinx-Needs**.
    Please see :ref:`filter` for more information.

Some further options are accepted only for :ref:`ubCode compatibility <ubcode_compat_options>`, and are otherwise ignored.


.. _needlist_show_status:

show_status
~~~~~~~~~~~
Flag for adding status information to the needs list results filtered.

If a filtered need has no status information, we write no status output for the need.

.. syntax-example::

   .. needlist::
      :show_status:
      :status: done; implemented

.. _needlist_show_tags:

show_tags
~~~~~~~~~
Flag for adding tag information to the needs list results filtered.

If a filtered need has no tag information, we write no tag output for the need.


.. syntax-example::

   .. needlist::
      :show_tags:
      :status: done; implemented

.. _needlist_show_filters:

show_filters
~~~~~~~~~~~~

If set, we add the used filter below the needlist results:


.. syntax-example::

   .. needlist::
      :show_filters:
      :status: done; implemented

.. _needlist_max_items:

max_items
~~~~~~~~~

.. versionadded:: 8.4.0

The maximum number of needs to show.

We apply the limit after filtering and sorting, so the list keeps the first needs it would otherwise have shown,
and tells the reader how many needs it is hiding.

``:max_items: 0`` means no limit, also for a project that sets :ref:`needs_views_max_items`.
Without the option, the list shows as many needs as that configuration allows.

.. syntax-example::

   .. needlist::
      :tags: flow_example
      :max_items: 2

common filters
~~~~~~~~~~~~~~

* :ref:`option_status`
* :ref:`option_tags`
* :ref:`option_types`
* :ref:`option_filter`
