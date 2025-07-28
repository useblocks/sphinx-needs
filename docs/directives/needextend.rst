.. _needextend:

needextend
==========
.. versionadded:: 0.7.0

``needextend`` allows to modify existing needs. It doesn't provide any output, as the modifications
get presented at the original location of the changing need, for example:

.. code-block:: rst

   .. needextend:: <filter_string>
      :option: new value
      :+option: additional value
      :-option:

The following modifications are supported:

* ``option``: replaces the value of an option
* ``+option``: add new value to an existing value of an option.
* ``-option``: delete a complete option.

The argument of ``needextend`` will be taken as, by order of priority:

- a single need ID, if it is enclosed by ``<>``,
- a :ref:`filter_string` if it is enclosed by ``""``,
- a single need ID, if it is a single word (no spaces),
- a :ref:`filter_string` otherwise.

``needextend`` can modify all string-based and list-based options.
Also, you can add links or delete tags.

.. need-example::

   .. req:: needextend Example 1
      :id: extend_test_001
      :status: open
      :author: Foo
      :tags: tag_1, tag_2

      This requirement got modified.

      | Status was **open**, now it is :ndf:`copy('status')`.
      | Also author got changed from **Foo** to :ndf:`copy('author')`.
      | And a tag was added.
      | Finally all links got removed.

   .. req:: needextend Example 2
      :id: extend_test_002
      :tags: extend_example
      :status: open

      Contents

   .. needextend:: extend_test_001
      :status: closed
      :+author: and me

   .. needextend:: <extend_test_001>
      :+tags: new_tag

   .. needextend:: id == "extend_test_002"
      :status: New status

   .. needextend:: ""extend_example" in tags"
      :+tags: other

Options
-------

.. _needextend_strict:

strict
~~~~~~
The purpose of the ``:strict:`` option is to handle whether an exception gets thrown or a warning log message gets written, if there is no need object to match the ``needextend's`` required argument (e.g. an ID).

If you set the ``:strict:`` option value to ``true``,
``needextend`` raises an exception because the given ID does not exist, and the build stops.

If you set  the ``:strict:`` option value to ``false``,
``needextend`` logs an warning-level message in the console, and the build continues.

Allowed values:

* true or
* false

Default: false

.. note::

    We have a configuration (conf.py) option called :ref:`needs_needextend_strict`
    that deactivates or activates the ``:strict:`` option behaviour for all ``needextend`` directives in a project.

Extending needs in current page
-------------------------------

.. versionadded:: 5.0.0

The ``c.this_doc()`` function is made available,
to filter for needs only in the same document as the ``needextend``.

The following example would set the status of all needs in the current document,
which do not have the status set explicitly, to ``open``.

.. need-example::

   .. needextend:: c.this_doc() and status is None
      :status: open

To address all needs in the current document, use this syntax:

.. need-example::

   .. needextend:: "c.this_doc()"
      :status: open

See also, :ref:`filter_current_page` and :ref:`needs_global_options` for setting a default option value for all needs.

Changing links
--------------
Options containing links get handled in two steps:

1. Options for the need are set as above.
2. The referenced need get updated as well and incoming links may get deleted, added or replaced.

.. need-example::

   .. req:: needextend Example 3
      :id: extend_test_003

      Had no outgoing links.
      Got an outgoing link ``extend_test_004``.

   .. req:: needextend Example 4
      :id: extend_test_004

      Had no links.
      Got an incoming links ``extend_test_003`` and ``extend_test_006``.

   .. req:: needextend Example 5
      :id: extend_test_005
      :links: extend_test_003, extend_test_004

      Had the two links: ``extend_test_003`` and ``extend_test_004``.
      Both got deleted.

   .. req:: needextend Example 6
      :id: extend_test_006
      :links: extend_test_003

      Had the link ``extend_test_003``, got another one ``extend_test_004``.

   .. needextend:: extend_test_003
      :links: extend_test_004

   .. needextend:: extend_test_005
      :-links:

   .. needextend:: extend_test_006
      :+links: extend_test_004

   .. Same as above, so it should not do anything.
   
   .. But it raises the modified-counter by one.

   .. needextend:: extend_test_006
      :+links: extend_test_004

Monitoring modifications
------------------------
All needs have this two internal parameters:

* ``is_modified``: A boolean value. Defaults to ``False``
* ``modifications``: A number. Defaults to ``0``.

If a need gets changed by a ``needextend`` directive, ``is_modified`` is changed to ``True``.
Also, the ``modifications`` number is increased by one.
+1 for each executed ``needextend`` on this need.

To see these values, use ``:layout: debug`` on the need or by :ref:`own_layouts`.

Also filtering for these values is supported:

.. need-example::

   We have :need_count:`is_modified` modified needs.

   .. needtable::
      :filter: "needextend" in title
      :columns: id, title, status, is_modified, modifications
      :style: table
