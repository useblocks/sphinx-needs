.. _needlist:

needlist
========

.. versionadded:: 0.2.0

**needlist** creates a list of elements based on the result of given filters.

.. need-example::

   .. needlist::
      :tags: main_example

Options
-------

.. note::

    **needlist** supports the full filtering possibilities of **Sphinx-Needs**.
    Please see :ref:`filter` for more information.


.. _needlist_show_status:

show_status
~~~~~~~~~~~
Flag for adding status information to the needs list results filtered.

If a filtered need has no status information, we write no status output for the need.

.. need-example::

   .. needlist::
      :show_status:
      :status: done; implemented

.. _needlist_show_tags:

show_tags
~~~~~~~~~
Flag for adding tag information to the needs list results filtered.

If a filtered need has no tag information, we write no tag output for the need.


.. need-example::

   .. needlist::
      :show_tags:
      :status: done; implemented

.. _needlist_show_filters:

show_filters
~~~~~~~~~~~~

If set, we add the used filter below the needlist results:


.. need-example::

   .. needlist::
      :show_filters:
      :status: done; implemented

common filters
~~~~~~~~~~~~~~

* :ref:`option_status`
* :ref:`option_tags`
* :ref:`option_types`
* :ref:`option_filter`
