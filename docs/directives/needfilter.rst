.. _needfilter:

needfilter
==========

.. deprecated:: 0.2.0

.. note:: Deprecated! Please use the more powerful directives :ref:`needlist`, :ref:`needtable` or  :ref:`needflow` instead of needfilter.
	        **needfilter** will be removed with version 1.0.0!

Example::

    .. needfilter::
       :status: open;in_progress
       :tags: user; login
       :types: req;Specification
       :filter: "my_tag" in tags and ("another_tag" in tags or "closed" in status)
       :show_status:
       :show_tags:
       :show_filters:
       :show_legend:
       :sort_by: id
       :layout: list

This prints a list with all found needs, which match the filters for status, tags and types.

For **:status:**, **:tags:** and **:types:** values are separated by "**;**".
**:filter:** gets evaluated.

The logic, if a need belongs to the needfilter result list, is as followed::

    status = (open OR in_progress) AND tags = (user OR login) AND types = (req OR spec) AND eval(filter) is True

For **:types:** the type itself and the human-readable type_title can be used as filter value.

If **:show_status:** / **:show_tags:** is given, the related information will be shown after the name of the need.

To show the used filters under a list, set **:show_filters:**

**:show_legend:** is supported only by **:layout:diagram**. It adds a legend with colors to the generated diagram.

The showed list is unsorted as long as the parameter **:sort_by:** is not used.
Valid options for **:sort_by:** are **id** and **status**.

.. _filter:

.. include:: directives/include_filter.rst

`:layout:`
~~~~~~~~~~
Three different types of layouts are available:

* list (default)
* table
* diagram

Only **list** supports each needfilter option.

**table** and **diagram** are supporting the filter options only (status, tags, types, filter) and their design is somehow fix.

diagram
+++++++

Diagrams are available only, if the sphinx extension
`sphinxcontrib-plantuml <https://pypi.python.org/pypi/sphinxcontrib-plantuml>`_ is installed, activated and has
a working configuration.

If the configured output is **svg**, the diagram elements are linked to the location of their definition.