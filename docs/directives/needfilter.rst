.. _needfilter:

needfilter
==========

.. deprecated:: 0.2.0

.. note::

   Deprecated! Please use the more powerful directives :ref:`needlist`, :ref:`needtable` or  :ref:`needflow` instead of needfilter.
   **needfilter** will be removed in version 1.0.0!

|ex|

.. code-block:: rst

    .. needfilter::
       :status: open;in_progress
       :tags: user;login
       :types: req;Specification
       :filter: "my_tag" in tags and ("another_tag" in tags or "closed" in status)
       :show_status:
       :show_tags:
       :show_filters:
       :show_legend:
       :sort_by: id
       :layout: list

This prints a list of needs matching the filters for the ``:status:``, ``:tags:`` and ``:types:`` options.

Separate the values for the ``:status:``, ``:tags:`` and ``:types:`` options with "**;**".
The ``:filter:`` gets evaluated.

The logic to check if a need belongs to the ``needfilter`` result list, is:

.. code:: jinja

    status = (open OR in_progress) AND tags = (user OR login) AND types = (req OR spec) AND eval(filter) is True

Options
-------

types
~~~~~
For the ``:types:`` option, you can use the type itself and the human-readable type_title as filter value.

show_status / show_tags
~~~~~~~~~~~~~~~~~~~~~~~
If you set the ``:show_status:`` / ``:show_tags:`` options, the related information will be shown after the name of the need.

show_filters
~~~~~~~~~~~~
To show the used filters under a list, set the ``:show_filters:`` option.

show_legend
~~~~~~~~~~~
The ``:show_legend:`` option is supported only if ``:layout: diagram``. It adds a legend with colors to the generated diagram.

sort_by
~~~~~~~
You can sort the showed list by setting the ``:sort_by:`` option.
Valid options for ``:sort_by:`` are *id* and *status*.

.. note:: Please read the common filter page :ref:`filter` for more detailed information about filter possibilities.


layout
~~~~~~
Three different types of layouts are available:

* list (default)
* table
* diagram

Only the **list** layout supports each ``needfilter`` option.

**table** and **diagram** only supports filter options (status, tags, types, filter) and their design is somehow fix.

diagram
+++++++

Diagrams are available only, if the sphinx extension
`sphinxcontrib-plantuml <https://pypi.python.org/pypi/sphinxcontrib-plantuml>`_ is installed, activated and has
a working configuration.

If the configured output is **svg**, the diagram elements are linked to the location of their definition.