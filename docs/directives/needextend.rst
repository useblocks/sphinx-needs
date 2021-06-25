.. _needextend:

needextend
==========
.. versionadded:: 0.7.0

``needextend`` allows to modify existing needs. It doesn't provide any output, as the modifications get presented
at the original location of the modified need.

.. code-block:: rst

   .. needextend:: <filter_string>
      :option: new value
      :+option: additional value
      :-option:

The following modifications are supported:

* ``option``: replaces the value of an option
* ``+option``: add new value to an existing value of an option.
* ``-option``: delete a complete option.

The argument of ``needextend`` must be a :ref:`filter_string`, which defines the needs to modify.

``needextend`` can modify all string-based and list-based options. So also links can be added or tags can get deleted.

**Example**

.. code-block:: rst

    .. req:: needextend Example 1
       :id: extend_test_001
       :status: open
       :author: Foo
       :tags: tag_1, tag_2
       :links: extend_test_001

       This requirement got modified.

       | Status was **open**, now it is **[[copy('status')]]**.
       | Also author got changed from **Foo** to **[[copy('author')]]**.
       | And a tag was added.
       | Finally all links got removed.

    .. needextend:: id == "extend_test_001"
       :status: closed
       :+author: and me
       :+tags: new_tag
       :-links:
       :-links_back:


.. req:: needextend Example 1
   :id: extend_test_001
   :status: open
   :author: Foo
   :tags: tag_1, tag_2
   :links: extend_test_001

   This requirement got modified.

   | Status was **open**, now it is **[[copy('status')]]**.
   | Also author got changed from **Foo** to **[[copy('author')]]**.
   | And a tag was added.
   | Finally all links got removed.

.. needextend:: id == "extend_test_001"
   :status: closed
   :+author: and me
   :+tags: new_tag
   :-links:
   :-links_back:

Removing links
--------------
``Outgoing`` and ``Incoming`` links got already calculated, when ``needextend`` gets handled.
This means outgoing and incoming links must get handled separately. For incoming links ``_back`` must be added to
the option name.

Example: Lets say ``Requirement A`` is referencing ``Requirement B``. To remove this link, set ``:-links:`` in
a ``needextend`` for ``Requirement A``. But ``Requirement B`` will keep its "incoming link". So only one direction got
removed.
To remove also the incoming link, a ``needextend`` for ``Requirment B`` is needed, which contains ``:-links_back:``.

Monitoring modifications
------------------------
All needs have this two internal parameters:

* ``is_modified``: A boolean value. Default ``False``
* ``modifications``: A number. Default ``0``.

If a need gets changed by a ``needextend`` directive, ``is_modified`` is changed to ``True``.
Also the ``modifications`` number is increased by one. +1 for each executed ``needextend`` on this need.

To see these values, use ``:layout: debug`` on the need or by :ref:`own_layouts`.

Also filtering for these values is supported::

    .. needtable::
       :filter: is_modified
       :columns: id, title, is_modified, modifications

.. needtable::
   :filter: is_modified
   :columns: id, title, is_modified, modifications
   :style: table







