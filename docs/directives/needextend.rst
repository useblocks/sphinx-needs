.. _needextend:

needextend
==========
.. versionadded:: 0.7.0

``needextend`` allows to modify existing needs. It doesn’t provide any output, as the modifications
get presented at the original location of the changing need.

|ex|

.. code-block:: rst

   .. needextend:: <filter_string>
      :option: new value
      :+option: additional value
      :-option:

The following modifications are supported:

* ``option``: replaces the value of an option
* ``+option``: add new value to an existing value of an option.
* ``-option``: delete a complete option.

The argument of ``needextend`` must be a :ref:`filter_string` which defines the needs to modify.

``needextend`` can modify all string-based and list-based options.
Also, you can add links or delete tags.

|ex|

.. code-block:: rst

    .. req:: needextend Example 1
       :id: extend_test_001
       :status: open
       :author: Foo
       :tags: tag_1, tag_2

       This requirement got modified.

       | Status was **open**, now it is **[[copy('status')]]**.
       | Also author got changed from **Foo** to **[[copy('author')]]**.
       | And a tag was added.
       | Finally all links got removed.

    .. needextend:: id == "extend_test_001"
       :status: closed
       :+author: and me
       :+tags: new_tag

|out|

.. req:: needextend Example 1
   :id: extend_test_001
   :status: open
   :author: Foo
   :tags: tag_1, tag_2
   :links: FEATURE_1

   This requirement got modified.

   | Status was **open**, now it is **[[copy('status')]]**.
   | Also author got changed from **Foo** to **[[copy('author')]]**.
   | And a tag was added.
   | Finally all links got removed.

.. needextend:: id == "extend_test_001"
   :status: closed
   :+author: and me
   :+tags: new_tag
   :+links: FEATURE_2, FEATURE_3

.. This is a useless comment, but needed to supress a bug in docutils 0.18.1 , which can not handle
.. the above needextend if followed by a new sections. 


Single need modification
------------------------
If only one single need shall get modified, the argument of ``needextend`` can just be the need-id.

|ex|

.. code-block:: rst

    .. req:: needextend Example 2
       :id: extend_test_002
       :status: open

    .. needextend:: extend_test_002
       :status: New status

|out|

.. req:: needextend Example 2
   :id: extend_test_002
   :status: open

.. needextend:: extend_test_002
   :status: New status

.. attention::

    The given argument must fully match the regular expression defined in
    :ref:`needs_id_regex` and a need with this ID must exist!
    Otherwise the argument is taken as normal filter string.

Setting default option values
-----------------------------
You can use ``needextend``'s filter string to set default option values for a group of needs.

|ex|

The following example would set the status of all needs in the document
``docs/directives/needextend.rst``, which do not have the status set explicitly, to ``open``.

.. code-block:: rst

   .. needextend:: (docname == "docs/directives/needextend") and (status is None)
      :status: open

See also: :ref:`needs_global_options` for setting a default option value for all needs.

Changing links
--------------
Options containing links get handled in two steps:

1. Options for the need are set as above.
2. The referenced need get updated as well and incoming links may get deleted, added or replaced.

|ex|

.. code-block:: rst

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

    .. -- MANIPULATIONS --

    .. needextend:: extend_test_003
       :links: extend_test_004

    .. needextend:: extend_test_005
       :-links:

    .. needextend:: extend_test_006
       :+links: extend_test_004

    .. needextend:: extend_test_006
       :+links: extend_test_004

       Same as above, so it should not do anything.
       But it raises the modified-counter by one.

|out|

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

|ex|

.. code-block:: rst

    We have :need_count:`is_modified` modified needs.

    .. needtable::
       :filter: "needextend" in title
       :columns: id, title, is_modified, modifications

|out|

We have :need_count:`is_modified` modified needs.

.. needtable::
   :filter: "needextend" in title
   :columns: id, title, is_modified, modifications
   :style: table
