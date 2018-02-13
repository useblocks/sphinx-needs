.. _needtable:

needtable
=========

.. versionadded:: 0.2.0

Options
-------

columns
~~~~~~~
Needs a comma/semicolon separated string, which is used to define the position of specific columns.
For instance::

	.. needtable::
		:columns: id;title;tags

This will show the columns *id*, *title* and *tags* in the given order.

Supported columns are:

* id
* title
* type
* status
* tags
* incoming
* outgoing

If **:columns:** is set, the value of config parameter **needs_table_layout** is not used for the current table.

show_filters
~~~~~~~~~~~~

