.. _`namespaced_ids`:

Namespaced ids
==============

.. versionadded:: 9.1.0

.. warning::

   Namespaced ids are **experimental**. The switch, :ref:`needs_namespaced_ids`, is off by
   default, and what it does may change in a later release, except for one thing: the
   marker it writes into ``needs.json`` (below), which a file keeps for as long as it is read.

A namespaced id groups needs by where they belong, in the id itself:
``nc::testcase::T_001`` is the need ``T_001`` of the namespace ``nc::testcase``. Two
sources whose ids carry different namespaces can then each have a ``T_001`` without renaming
either; a namespace a source declares for its ids is planned.

Turning it on
-------------

.. code-block:: toml

   [needs]
   namespaced_ids = true

or ``needs_namespaced_ids = True`` in :file:`conf.py`.

With :ref:`needs_namespaced_ids` off, the default, nothing changes: a ``::`` in an id is a
character of it, and :ref:`needs_id_regex` validates the id whole.

The rules
---------

With the switch on, every need's id -- written in the source, generated, imported or
external -- is read as a namespace and a local id, split at its **last** ``::``:
``nc::testcase::T_001`` is the local id ``T_001`` in the namespace ``nc::testcase``, whose
segments are ``nc`` and ``testcase``. An id without ``::`` has no namespace: it is its own
local id. The id itself does not change: links, roles, filters and ``needs.json`` name a
need by its whole id, as they always have.

- A namespace segment is an ASCII letter followed by ASCII letters, digits, ``_`` or
  ``-``.
- A local id is not empty, does not begin with ``:``, and holds neither ``::`` nor ``.``
  (a ``.`` starts a :ref:`need part <need_part>`).

A need written in the sources whose id breaks either rule is not created, and its warning
names the rule it breaks, as for an id that does not match :ref:`needs_id_regex`.

The rules apply after a ``::``. An id without ``::`` keeps today's rules:
:ref:`needs_id_regex` alone decides its shape, so ``REQ_001.x`` is created with the switch
on, as it is with the switch off.

:ref:`needs_id_regex` applies to the **local** id, so a project's pattern keeps its meaning:
with the default ``^[A-Z0-9_]{5,}``, ``nc::REQ_001`` is a valid id and ``NS::r1`` is not.
A pattern a project wrote for whole ids that already hold ``::`` (``^[a-z]+::[A-Z0-9_]+$``)
must be rewritten for the local id when it turns the switch on.
Imported and external needs are exempt from it, as they are with the switch off.

A generated id is split like any other, so a need type whose ``prefix`` holds ``::``
(``prefix = "nc::testcase::T_"``) gives its generated ids that namespace; a generated id
already changes when its need is re-typed, so this puts no identity at a new risk.

Links name a namespaced need as they name any need, with parts and conditions:
``nc::testcase::T_001.p1``, ``NS::REQ_001[status=="open"]``.

A need and a namespace may share a name: a need ``nc::testcase`` and the needs of the
namespace ``nc::testcase`` coexist. An id names one need and a namespace names a set of
needs, so nothing that refers to either is ambiguous.

Reserved names
--------------

With the switch on, ``ns`` and ``local_id`` are reserved for the namespace and the local id:
a field or link type of either name -- a :ref:`needs_fields`, :ref:`needs_extra_options`,
:ref:`needs_links` or :ref:`needs_extra_links` entry, a need type's ``fields`` or
``links``, or a service's options -- is a configuration error. With the switch off they are ordinary names.

needs.json
----------

Each version a project writes with the switch on carries ``"namespaced_ids": true``. The
ids and the link targets keep their joined spelling, so a reader that does not know the
marker reads the same needs as before. The marker is the version's: in a :ref:`needs_file`
that accumulates versions, the versions written before the switch was turned on stay
unmarked.

Per-id files (:ref:`needs_build_json_per_id`) cannot be written for an id holding ``::`` on
Windows, where ``:`` is not a legal file-name character; a file naming for namespaced ids is
planned.

Reading a needs.json with :ref:`needimport` or :ref:`needs_external_needs`:

- into a project with the switch on, every id is split as above, whether the version read
  is marked or not. A version that is not marked but holds an id with ``::`` is reported
  once per source, as an informational message: its ids are read as namespaced ids, which
  the file does not say they are;
- into a project with the switch off, a marked version's ids are read as plain ids, ``::``
  included, with one informational message per source;
- an imported or external id that does not split is not read: one warning per need, as for
  any record that cannot be read.

What is planned
---------------

These are not in this release; :file:`design/namespaced-ids.md` in the repository records
why and in what order:

- filters on a need's namespace and local id: ``ns == "nc::testcase"`` (one namespace),
  ``in_namespace("nc")`` (a namespace and every namespace under it), and ``local_id``;
- a namespace declared by an import or external source, replacing ``id_prefix`` for it;
- a ``local_id`` property for schema validation, so that an id pattern written for the
  local id can move there.

A project whose schemas, :ref:`needs_warnings` or constraints test the shape of ``id``
sees the whole id, namespace included, until then.
