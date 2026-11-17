.. _namespaced_ids:

Namespaced ids
==============

.. versionadded:: 9.3.0

A need id may name a **namespace**: ``nc::m2::REQ_1`` is the need ``REQ_1`` in the namespace ``nc::m2``.
Namespaces keep the ids of a sub-project, a supplier or a component apart without a prefix convention of
their own, and let a filter select a namespace and everything below it.

Turning it on
-------------

Namespaced ids are **off by default** in the 9.x series, and **on by default from 10.0**. Turn them on with
:ref:`needs_namespaced_ids`:

.. code-block:: python

   needs_namespaced_ids = True

or in ``ubproject.toml``:

.. code-block:: toml

   [needs]
   namespaced_ids = true

Off, every id is a plain id, whatever it holds: nothing below applies, but for the filter names, which stay
defined (every need is in no namespace). Set the value either way to keep a project's reading through 10.0.
Changing it re-reads every document.

How an id splits
----------------

An id is split at its **last** ``::``. What follows is the **local id**; what precedes it is the namespace,
whose **segments** are separated by ``::`` and are each one or more ASCII letters, digits, ``_`` or ``-``,
in any position. Segments are case-sensitive.

.. list-table::
   :header-rows: 1
   :widths: 30 25 25

   * - id
     - namespace
     - local id
   * - ``REQ_1``
     - none (``""``)
     - ``REQ_1``
   * - ``nc::REQ_1``
     - ``nc``
     - ``REQ_1``
   * - ``nc::m2::REQ_1``
     - ``nc::m2`` (segments ``nc``, ``m2``)
     - ``REQ_1``
   * - ``2024::REQ_5``
     - ``2024``
     - ``REQ_5``

The id itself does not change: it stays the need's key, its anchor in the HTML, its id in ``needs.json``, and
what a link, a ``:need:`` role or a filter on ``id`` names. **A link names the full id**, ``nc::REQ_1``, from
inside the namespace too. A need's namespace and local id are read once, when the need is created, whichever
way it is created.

Ids that do not split
---------------------

With namespaced ids on, an id that holds ``::`` but is not a namespace and a local id by these rules is a
**plain id**: it is never refused for that. That is an id where nothing follows the last ``::`` (``NS::``), where a segment is empty
(``A::::B``, ``::REQ_1``), or where a segment holds another character (``std::vector<int>::size``,
``a.b::REQ_1``). A need written in the project's documents, or whose id the project generates (from a need
type's ``prefix`` or its title), with such an id is reported at the need, as ``needs.id_namespace``, once per
need directive (a duplicate of the id is reported for its id too, beside its refusal as a duplicate); a need
refused for another reason, by an id pattern say, is reported for that alone::

   Need id 'A::::B' contains '::' but is not a namespaced id (a namespace segment is empty), so it is read as a
   plain id. Correct the id, set needs_namespaced_ids = False to read no id as namespaced, or suppress the
   warning type needs.id_namespace.

An imported or external need is the data of the project that wrote it, and is not reported.

Id patterns
-----------

With namespaced ids on, :ref:`needs_id_regex` and a need type's ``id_regex`` accept an id whose local id matches,
or which matches as a whole: with the default ``^[A-Z0-9_]{5,}``, ``nc::REQ_00001`` is accepted through its local id, an id
accepted before as a whole (``REQ_1::A``, whose local id ``A`` does not match) still is, and ``nc::req`` is
refused. Imported and external needs are not checked, as before.

Because the local id is tried first, a pattern cannot refuse a namespace:
``^(?!.*::)[A-Z_]+``, written to refuse every id holding ``::``, accepts ``nc::REQ_1`` through its local id
``REQ_1``. Off, the pattern sees the whole id, as before, and refuses ``nc::REQ_1``.

Namespaces from an import
-------------------------

With namespaced ids on, an :ref:`needimport` or :ref:`needs_external_needs` ``id_prefix`` that ends in ``::``
puts the imported needs into a namespace: with ``:id_prefix: supplier::`` the file's ``REQ_1`` is ``supplier::REQ_1``, and its
``nc::REQ_2`` is ``supplier::nc::REQ_2``. A prefix that does not end in ``::`` (``SUP_``) joins the id's first
segment instead.

Filtering by namespace
----------------------

``c.id.ns``, ``c.id.local`` and ``c.in_namespace()`` read a need's namespace and local id in a filter
(:ref:`filter_namespace`):

.. code-block:: rst

   .. needtable::
      :filter: c.in_namespace("nc")

With namespaced ids on, a dead link (an external need's too) or a ``:need:`` role naming a bare id that no need has, and that exactly
one need has as its local id in a namespace, says which, after its usual text: ``linked need REQ_2 not found
(did you mean 'nc::REQ_2'?)``. A part the link names is re-attached when that need has it
(``(did you mean 'nc::REQ_2.p1'?)``); otherwise, and with no such need or several, the message is as before.
The three warnings that carry it are ``needs.link_outgoing``, ``needs.external_link_outgoing`` and
``needs.link_ref``.

Turning it off
--------------

With :ref:`needs_namespaced_ids` ``False`` (``[needs] namespaced_ids = false``), the default until 10.0, every id
is a plain id: no id is split, nothing is reported or hinted, the id patterns read the whole id, and the filter
names above stay defined, every need being in no namespace. Keep it off in a project whose ids hold ``::`` for
another reason (a C++ name, say).

The namespace names are **experimental** in this release (:ref:`api_public`): ``c.id.ns``, ``c.id.local``,
``c.in_namespace()`` and the attributes ``id_ns``, ``id_ns_segments`` and ``id_local`` of a need may change
before they are declared stable. :ref:`needs_namespaced_ids` itself is not experimental; its default changes
in 10.0.
