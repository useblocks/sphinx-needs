.. _`needs_derive`:

Derived fields
==============

.. versionadded:: 9.0.0

A field whose entry carries a ``derive`` table is **derived**: a rule computes its value
for every need the project creates from its sources, and an author does not write it.
The table names a ``kind``, and the kind's operands, each under a fixed role name.
In the :ref:`TOML file <needs_from_toml>`:

.. code-block:: toml

   [needs.fields.hours]
   schema = { type = "number" }

   [needs.fields.total_hours]
   schema = { type = "number" }
   derive = { kind = "sum", field = "hours", over = "links" }

   [needs.fields.verified]
   schema = { type = "boolean" }
   derive = { kind = "all", test = "status == 'passed'", over = "tests_back", where = "type == 'test'" }

   [needs.links.mentions]
   derive = { kind = "content_links" }

or in :file:`conf.py`, as every other key of the entry:

.. code-block:: python

   needs_fields = {
       "total_hours": {
           "schema": {"type": "number"},
           "derive": {"kind": "sum", "field": "hours", "over": "links"},
       },
   }

A link type is derived the same way, with ``derive`` on its :ref:`needs_links` entry
and one of the kinds that compute a link list: ``links``, ``content_links`` and ``union``.
How a rule relates to the ``[[…]]`` calls that compute a value per need is described in :ref:`dynamic_functions_derived`.

.. _`needs_derive_kinds`:

The kinds
---------

.. list-table::
   :header-rows: 1
   :widths: 14 10 16 26 34

   * - kind
     - declared on
     - required roles
     - optional roles
     - result, which the field's ``schema`` must hold
   * - ``copy``
     - a field
     - ``field``
     - one of ``from``, ``over`` and ``join``; ``select`` (with ``over`` or ``join``);
       ``include_self`` (with ``join``)
     - the type of the field read; with ``select = "list"``, an array of it
   * - ``sum``
     - a field
     - ``field``, ``over``
     - ``where``
     - a ``number`` (or an ``integer``, when the field read is one)
   * - ``count``
     - a field
     - ``over``
     - ``field``, ``where``
     - an ``integer``
   * - ``min``, ``max``
     - a field
     - ``field``, ``over``
     - ``where``; ``transitive``, ``include_self``
     - the type of the field read, which must be a number or a string with an ``enum``
   * - ``any``, ``all``
     - a field
     - ``over``, and exactly one of ``field`` (a boolean field) and ``test``
     - ``where``
     - a ``boolean``
   * - ``collect``
     - a field
     - ``field``, ``over``
     - ``where``
     - an array of the item type of the field read
   * - ``hash``
     - a field
     - ``fields``
     - (none)
     - a ``string``, computed after every other rule of the need
   * - ``fingerprint``
     - a field
     - (none)
     - ``exclude``
     - a ``string``, computed after every other rule of the need
   * - ``links``
     - a link type
     - ``where`` or ``join``
     - the other of the two; ``include_self``; ``include_parts`` (not with ``join``)
     - a link list
   * - ``content_links``
     - a link type
     - (none)
     - ``from``, ``where``
     - a link list
   * - ``union``
     - a link type
     - ``fields``
     - (none)
     - a link list: the links of the link types ``fields`` names (:ref:`needs_derive_union`)

Every kind that computes a value, but ``fingerprint``, also takes ``after = "derived"``,
which computes the field after every other rule of the need, as ``hash`` and ``fingerprint`` always are.

.. _`needs_derive_roles`:

The roles
---------

.. list-table::
   :header-rows: 1
   :widths: 16 22 62

   * - role
     - value
     - meaning
   * - ``field``
     - a field name
     - The field read on each candidate: a field (one of :ref:`needs_fields`, or a core field such as ``title``),
       a link type, or ``<link type>_back``.
       On ``copy`` with neither ``over`` nor ``from``, this need's own field.
   * - ``fields``
     - a list of field names
     - ``hash``: the need's own fields hashed, in the listed order (fields and link types; not a ``<link type>_back``).
       ``union``: the need's own link types whose links it holds, in the listed order, each named once
       (derived ones and other unions included; not ``parent_needs`` or a ``<link type>_back``).
   * - ``exclude``
     - a list of field names
     - ``fingerprint``: the names it leaves out, each a name it includes, once; an empty list leaves nothing out.
   * - ``over``
     - a link type
     - The candidates: the needs this need's ``<link type>`` names, in the order written, a need named twice counted twice;
       or, for ``<link type>_back``, the needs that link to this one, in need-id order, each once
       (need-id order compares the ids as strings, by code point: ``T_10``, ``T_2``, ``T_9``;
       ``needs.json`` sorts a link list naturally instead: ``T_2``, ``T_9``, ``T_10``).
       A link to a need part reads the part's need; a link to no need is skipped.
   * - ``from``
     - a need id
     - The one need whose ``field`` (``copy``) or content (``content_links``) is read.
   * - ``join``
     - ``{ field = …, equals = … }``
     - ``links``, ``copy``: the candidates are the needs whose ``field`` equals one of this need's ``equals`` values,
       each once, in need-id order. Both are text fields, a string split on ``,`` or an array of strings,
       compared value by value (see :ref:`needs_derive_join`).
   * - ``where``
     - a filter string
     - Narrows the candidates: each is kept when the :ref:`filter string <filter_string>` holds on it.
       On ``links``, the filter every need is tested with.
   * - ``test``
     - a filter string
     - ``any`` / ``all``: what is asserted of each remaining candidate.
       Over no candidates, ``all`` is ``true`` and ``any`` is ``false``.
   * - ``select``
     - ``"first"`` (default), ``"unique"``, ``"list"``
     - ``copy`` over several targets (with ``over`` or ``join``): the target with the lowest need id among those that set the field;
       the same, reported when several set it; or every value, as a list (the field must be an array).
   * - ``transitive``
     - ``true`` / ``false`` (default)
     - ``min`` / ``max``: read every need reachable through ``over``, each once, not only the needs one link away.
   * - ``include_self``
     - ``true`` / ``false`` (default)
     - ``min`` / ``max`` with ``transitive = true``: count this need's own ``field`` too.
       ``links``: this need (and its parts) may be linked.
       ``copy`` with ``join``: this need may be a candidate.
   * - ``include_parts``
     - ``true`` / ``false`` (default)
     - ``links`` without ``join``: the parts of every need are candidates too, a passing part linked as ``<need>.<part>``.
   * - ``after``
     - ``"derived"``
     - Compute the field after every other rule of the need.

A ``where`` or ``test`` reads the candidate only:
a filter naming ``needs``, ``current_need`` or a ``c.`` check (such as ``c.this_doc()``) cannot be declared,
so that a rule means the same in every tool that reads the configuration.

A ``join`` matches the needs whose field equals one of this need's values (:ref:`needs_derive_join`).
``types`` is not a role: a rule for some need types is declared under ``derive_by_type`` (:ref:`needs_derive_by_type`).
A rule on a core field (``status``, ``tags``, ``title`` and the other core fields, and the ``parent_needs`` link type),
or on a link type named after a core field (such as ``parts``), is not available in this release: it is reported, and ignored.

.. _`needs_derive_cost`:

What a rule costs
-----------------

A rule is computed once per step for every need holding it (a ``links`` rule's ``where`` is tested once,
on each candidate alone), so writing one costs little: what costs is what it **stores**.
Every need holding a ``links`` rule with a ``where`` (and no ``join``) is linked to the same needs (but itself),
and each of them gets a back link from every one (a ``join`` links each need to its own matches):
on every need of a project of 2 000, a rule whose ``where`` half the needs pass stores about 2 000 000 links
and as many back links, and ``needs.json`` grows from about 2.5 MB to about 58 MB;
at twice the needs it stores four times the links.
A rule that ten needs pass stores about ten links per need.

- Keep ``where`` selective, or declare the rule only for the need types that use it (:ref:`needs_derive_by_type`).
- To show a set of needs, use a :ref:`needtable` or :ref:`needlist` with that filter: it shows the set once,
  where a ``links`` rule copies it into every need.
- To know on one need how many needs (or which) point at it, link the other way and read the back links:
  ``{ kind = "count", over = "tests_back", where = "status == 'open'" }`` stores one number.
- :ref:`links_from_filter` written in every need stores what the ``links`` rule stores, and also tests its filter
  on every need once per call, so on many needs prefer the declared rule.

A link type whose computed links number more than :ref:`needs_derive_max_links_per_need` (``100``) per need of the project
is reported once, as the warning ``needs.derive_dense``,
naming the links, the needs holding the rule and the longest list.

.. _`needs_derive_join`:

Matching a field: the join role
-------------------------------

.. versionadded:: 9.1.0

``join = { field = "<field>", equals = "<own field>" }`` makes the candidates of a ``links`` or ``copy`` rule
the needs whose ``field`` equals one of this need's ``equals`` values,
such as the specifications a test names in its ``test_case`` field by their ``case_name``:

.. code-block:: toml

   [needs.fields.case_name]
   schema = { type = "string" }

   [needs.fields.test_case]
   schema = { type = "string" }

   [needs.fields.owner]
   schema = { type = "string" }

   [needs.links.covers]
   derive = { kind = "links", join = { field = "case_name", equals = "test_case" } }

   [needs.fields.owners]
   schema = { type = "array", items = { type = "string" } }
   derive = { kind = "copy", field = "owner", join = { field = "case_name", equals = "test_case" }, select = "list" }

.. code-block:: rst

   .. spec:: Login
      :id: SPEC_LOGIN
      :case_name: login
      :owner: alice

   .. spec:: Login, remembered
      :id: SPEC_REMEMBER
      :case_name: login, remember

   .. spec:: Logout
      :id: SPEC_LOGOUT
      :case_name: logout
      :owner: bob

   .. test:: Session test
      :id: TEST_SESSION
      :test_case: login, logout

``TEST_SESSION`` covers ``SPEC_LOGIN``, ``SPEC_LOGOUT`` and ``SPEC_REMEMBER`` (whose ``case_name`` holds ``login`` too),
and its ``owners`` are ``["alice", "bob"]``; a spec, which has no ``test_case``, covers nothing.

- **The match.** Both fields are read the same way:
  a string is split on ``,`` and each value stripped of whitespace, an array of strings is taken item by item
  (an item is not split again), and an empty value is dropped.
  A need matches when its ``field`` and this need's ``equals`` share a value, compared exactly (case-sensitive).
- **Candidates.** Each need that matches, once, however many values it shares,
  in need-id order (the ids compared as strings, by code point: ``T_10``, ``T_2``, ``T_9``;
  ``needs.json`` sorts a link list naturally instead).
  This need is left out unless ``include_self = true``.
  Needs only: a need part is never a candidate (a need with parts matches as itself),
  and ``include_parts`` cannot be given beside ``join``.
- **links and copy.** ``links`` links the candidates that pass its ``where``, if it has one:
  it requires ``where`` or ``join``, and takes both.
  ``copy`` reads the candidates as it reads the needs a link type names: ``select`` takes the lowest-id candidate
  that sets the field (``"first"``, the default), the same and a ``needs.derive_unique`` warning when several set it
  (``"unique"``), or every value (``"list"``); with no candidate it finds no value (``[]`` with ``"list"``).
  ``copy`` takes one of ``from``, ``over`` and ``join``, and no ``where``.
- **The fields.** ``field`` and ``equals`` each name a field holding a string (an ``enum`` included)
  or an array of strings: one of :ref:`needs_fields`, or a core field such as ``id``, ``title``, ``type``,
  ``status`` or ``tags``. A link type, a ``<link type>_back``, and a number or a boolean field
  are reported as ``needs.derive_invalid``.
- **The order.** A join reads ``equals`` on this need, and ``field`` (and ``copy``'s ``field``) on every need.
  A ``copy`` with ``join`` is computed after every need computing those fields in its step;
  a ``links`` with ``join`` is computed with the link fields, before any other field,
  so one whose fields a rule, a ``[[…]]`` or a variant computes is not run (``needs.derive_scope``, see :ref:`needs_derive_scope`).
  A ``copy`` whose ``equals`` is its own field, or reads it back through other rules, can be computed on no need,
  and is reported when the configuration is read;
  one whose ``field`` is its own field reads its own result on every need, a cycle (``needs.derive_cycle``).
  The needs are indexed by ``field`` once for the link fields and once for the other fields
  (and once more for the rules computed last), shared by every rule and call on it,
  however many needs hold the rule.

The inline spelling is :ref:`links_from_match`:
``[[links_from_match("case_name", "test_case")]]`` in a link field of ``TEST_SESSION`` links the same needs.
The nearest declared form of sphinx-test-reports' ``tr_link(test_option, target_option)`` is
``join = { field = "<target_option>", equals = "<test_option>" }`` with ``include_self = true``,
or inline ``[[links_from_match("<target_option>", "<test_option>", include_self=True)]]``:
the arguments come in the swapped order, the field read on every need first.
``tr_link`` links a need once per value that matches it, in the order the project holds the needs,
compares each need's ``target_option`` whole (so an array, a number or a comma-separated value never matches,
and an unstripped one only as written), and fails when this need's ``test_option`` is an array or a number;
``links_from_match`` reads both sides by value and fails the call on a number or boolean field.

.. _`needs_derive_by_type`:

Rules per need type
-------------------

Beside ``derive``, or instead of it, a ``derive_by_type`` table gives a rule per need type.
Its keys are need types, by their directive name (the value ``type`` holds, as a filter reads it: ``type == 'story'``),
and each value is a rule, as ``derive`` takes one.
A need uses the rule of its type, else ``derive``, else none.
A need type's own declaration of a derived field (:ref:`needs_types_fields`) narrows its description, schema and ``nullable``,
but gives it no default; a ``derive`` in it is the type's ``derive_by_type`` entry.

Effort written on tasks and rolled up through stories and epics takes two fields:
the one authors write, and a derived one, which copies it on a task and sums itself over the links of a story or an epic:

.. code-block:: toml

   [needs.fields.effort]
   schema = { type = "number" }

   [needs.fields.total_effort]
   schema = { type = "number" }
   nullable = false
   derive_by_type.task = { kind = "copy", field = "effort" }
   derive_by_type.story = { kind = "sum", field = "total_effort", over = "links" }
   derive_by_type.epic = { kind = "sum", field = "total_effort", over = "links" }

.. code-block:: rst

   .. task:: Write the parser
      :id: TASK_1
      :effort: 3

   .. task:: Write the tests
      :id: TASK_2
      :effort: 5

   .. task:: Write the docs
      :id: TASK_3
      :effort: 2

   .. story:: Parse the input
      :id: STORY_1
      :links: TASK_1, TASK_2

   .. epic:: Ship the reader
      :id: EPIC_1
      :links: STORY_1, TASK_3

Each task's ``total_effort`` is its ``effort`` (``3.0``, ``5.0``, ``2.0``),
``STORY_1``'s is ``8.0``, and ``EPIC_1``'s ``10.0``: a rule reading its own field over a link type
reads the value each linked need computes, through any depth.
Needs linking one another in a cycle cannot compute such a value, and are reported (``needs.derive_cycle``).
One field cannot do both: a derived field is closed on every need type, also where it has no rule.

A need of a type without a rule holds the same value on every need of the type:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - beside ``derive_by_type``
     - a need of a type without a rule holds
   * - a ``default``
     - the default, in the field's type (``default = 0`` is ``0.0`` in a ``number`` field);
       the field's ``schema`` checks it, as it checks any default
       (but a link type's ``default = []``, which is its "no links", as no default is)
   * - no ``default``, nullable (as the field is declared: a :ref:`needs_fields` entry is unless
       ``nullable = false``; a :ref:`needs_extra_options` entry without a ``schema`` is not)
     - ``None``
   * - no ``default``, ``nullable = false``
     - the field's empty value (``""``, ``0``, ``0.0``, ``False`` or ``[]``; no links for a link type),
       which the ``schema`` does not check

The ``default`` must be a literal value, and is given only with ``derive_by_type`` alone:
beside ``derive`` every need type has a rule, and a ``default`` is reported as ``needs.derive_invalid``, and ignored.
A ``default`` that is a ``[[…]]`` or a variant, and ``predicates``, are reported beside ``derive_by_type`` too, and ignored:
a value that varies per need is what a rule is for.

``derive_by_type`` is checked when the configuration is read, one ``needs.derive_invalid`` per entry:
a key naming no need type is ignored (a type's title is not its directive name, and the warning says which is meant);
an empty ``derive_by_type``, or one that is not a table, adds no rule: the field stays derived,
every need type using the ``derive`` beside it, or, without one, no rule;
an entry that cannot be read, as a ``derive`` that cannot be read, leaves the needs of its type at the empty value,
and the other types are unaffected.
Rules reading one another's own fields in a circle are looked for per need type, among the rules each type uses:
a ``derive`` closing such a circle on some types only is reported naming them, and applies on every other type.

Each need is computed in the step of its own rule, so one field may be computed after every other on one type
(``after = "derived"``) and not on another: a value that reads the field waits for the rule of the need it reads,
and only the needs whose rule comes later are reported (``needs.derive_scope``).

.. _`needs_derive_holds`:

What a derived field holds
--------------------------

A derived field (one with ``derive`` or ``derive_by_type``) is closed to authors, on every need type,
also on a type it has no rule for:
a value written for it in a need (a literal, or a ``[[…]]``, ``<<…>>`` or ``<{…}>``),
or set by a :ref:`needextend`, is ignored and reported as ``needs.derive_authored``, at the need or the ``needextend``.
It takes no ``default`` (but the value of the need types without a rule, see :ref:`needs_derive_by_type`)
and no ``predicates``.
A need from outside the project's sources, created by :ref:`needimport` or loaded from :ref:`needs_external_needs`,
keeps the values it carries, as data: no rule runs on it.
One lacking a derived field holds what a need of its type holds when no rule has computed it:
the value of a type without a rule, else the empty value.
In the schema of the :ref:`needs.json <needs_builder_format>`, a derived field or link type is marked ``"readOnly": true``,
so a project importing the file knows the value is computed, not authored;
the schema's ``default`` of a field, or of a link type derived by type alone, is the value of a need type without a rule.

A rule is checked when the configuration is read.
A rule that cannot be read is reported as ``needs.derive_invalid``, once per rule, naming the kind and the role:
an unknown kind, an unknown role, a role the kind does not take or requires,
a role holding the wrong type of value,
a kind computing a link list declared on a field, or one computing a value declared on a link type,
an ``over`` naming no link type, a ``field`` naming nothing a need has,
a result the field's ``schema`` cannot hold,
a ``min`` or ``max`` reading a field that has no order,
a ``hash`` naming a ``<link type>_back``,
a ``fingerprint`` whose ``exclude`` is not a list of names, names one twice,
or names what a fingerprint does not include (nothing a need has, or a name it never includes, such as ``docname``),
a ``where`` or ``test`` that does not parse or reads more than the candidate,
an empty ``where`` on ``links`` (it would link every need),
a ``join`` that is not a table of a ``field`` and an ``equals`` naming text fields, or is given beside ``include_parts``,
a ``union`` naming what is not a link type (a field, a ``<link type>_back``, a name declared nowhere), ``parent_needs``,
no link type, or one twice,
and rules reading one another's own fields in a circle (``copy`` without ``over`` or ``from``, ``hash``, and ``union``,
a union naming itself or two naming each other),
which no need could compute.
The field stays derived: it cannot be set, and it holds its empty value
(``None``, or for a field that is not nullable ``""``, ``0``, ``0.0``, ``False`` or ``[]``; no links for a link type).
The empty value a derived field holds is its "no value", as ``None`` is for a nullable field:
the field's ``schema`` does not check it, so an ``enum``, a ``minimum`` or a ``pattern`` that refuses it is no violation.
A ``default`` or ``predicates`` beside ``derive`` is reported as ``needs.derive_invalid`` too, and ignored;
the rule applies. So is an ``allow_dead_links`` beside a ``union``, whose dead links are its members'.
So is a link type declared with ``copy = true`` while ``links`` is derived:
nothing is copied into ``links``, which holds what its rule computes;
and ``copy = true`` on a derived link type, which is not available in this release: nothing is copied.

.. _`needs_derive_computed`:

How a rule is computed
----------------------

A rule is computed with the ``[[…]]`` of its step (see :ref:`needs_processing_order`):
``links``, ``content_links`` and ``union`` with the link fields, ``hash``, ``fingerprint`` and the rules with
``after = "derived"`` after every other field, every other kind with the other fields; each after every value it reads
(a ``union`` after the derived link types it names).

- **Candidates.** ``over = "<t>"``: the needs this need's ``<t>`` names, once the link fields are computed,
  in the order written; a need named twice is a candidate twice;
  a link to a :ref:`need part <need_part>` is its need, and a link to no need is skipped.
  ``over = "<t>_back"``: the needs that link to this need (or to one of its parts), in need-id order, each once
  (need-id order compares the ids as strings, by code point: ``T_10``, ``T_2``, ``T_9``, as a back link list is read;
  ``needs.json`` sorts a link list naturally instead: ``T_2``, ``T_9``, ``T_10``).
  ``where`` drops the candidates it does not hold on, then ``test`` is tested on the others.
  A ``where`` or ``test`` that cannot be evaluated on a candidate (a field the candidate lacks,
  as ``hours > 1`` on a need without ``hours``) does not hold on it, without a warning.
- **Unset values.** A field is unset when it is null: an empty value (``""``, ``[]``, a link type with no links)
  is set, so ``count`` with a ``field`` counts it, and ``copy`` and ``collect`` take it.
  A candidate whose ``field`` is unset is skipped by ``sum``, ``min``, ``max``, ``collect``,
  and ``count`` with a ``field`` (which so counts the candidates that set it);
  ``any`` and ``all`` read it as false.
  ``sum`` skips a value that is not a number.
- **No candidate.** ``sum`` and ``count`` are ``0`` (``0.0`` in a ``number`` field), ``any`` ``false``, ``all`` ``true``,
  ``collect`` and ``copy`` with ``select = "list"`` ``[]`` (a list, also when no candidate sets the field);
  ``min``, ``max`` and ``copy`` with ``select = "first"`` or ``"unique"`` find no value,
  over no candidate or over candidates none of which sets the field, and leave the field at its empty value.
  The values a rule computes over no candidate (and an empty link list) are checked against the field's ``schema``
  as any result is, so a ``count`` of ``0`` under ``minimum = 1`` is refused,
  while the empty value of a rule that found no value is not checked.
- **Values.** A result takes the type of the field holding it, as an authored value does,
  and as the result of a ``[[…]]`` or a variant does: an integer in an ``integer`` field, a float in a ``number`` field
  (a ``count``, or the ``sum`` of an ``integer`` field, is ``13.0`` there), in ``needs.json`` and in a ``hash``.
  ``sum`` adds in the order of the candidates.
  ``min`` and ``max`` order numbers by value, and a string by the order of its ``enum``.
  ``collect`` keeps each value once, in the order of the candidates, a list's items each.
  ``copy`` over several targets takes the one with the lowest need id among those that set the field
  (``select = "first"``), the same and a ``needs.derive_unique`` warning when several set it (``"unique"``),
  or every value in the order written (in need-id order over a ``join``), a list's items each (``"list"``).
- **transitive.** ``min`` and ``max`` read every need reachable through ``over``, each once:
  a need on a cycle reaches itself, so every member of a cycle has the same value;
  ``include_self`` adds the need's own ``field``.
  A rule whose ``field`` is its own field (a roll-up of one field per need type, see :ref:`needs_derive_by_type`)
  reads the value each reached need computes, so needs linking one another in a cycle are reported
  (``needs.derive_cycle``) rather than closed over.
  With ``include_self = true`` such a rule reads its own value on every need, which is a ``needs.derive_cycle``
  on each: an own-field roll-up leaves ``include_self`` off.
- **hash.** The lowercase hex SHA-256 of the UTF-8 text of one JSON array:
  the listed fields' values in the listed order, each as :ref:`needs.json <needs_builder_format>` holds it
  (an unset field ``null``),
  with no whitespace, non-ASCII characters not escaped, and numbers as Python writes them (``3.0``, ``1e+16``).
  A link list is written as the ids it links to, without their conditions, sorted and without duplicates,
  so a need linked with and without a condition is hashed once.
  For ``fields = ["title", "status"]`` on a need titled ``Größe`` with status ``open``,
  the text is ``["Größe","open"]``.
- **fingerprint.** The lowercase hex SHA-256 of the UTF-8 text of one JSON object holding the whole need,
  its keys sorted, written as for ``hash`` (no whitespace, non-ASCII characters not escaped, numbers as Python writes
  them, and a ``number`` field's value as a float).

  - It includes ``id``, ``type``, ``title``, ``status``, ``tags`` and ``content``
    (as ``needs.json`` holds it: a need nested in another's body is part of the parent's ``content``,
    so editing or moving the nested need changes its parent's fingerprint too),
    every field the project declares in :ref:`needs_fields` or :ref:`needs_extra_options`,
    and every link type, ``links`` among them; none of them derived.
  - It never includes a derived field or link type, one with ``derive`` or ``derive_by_type``, on any need type
    (so no ``hash`` and no other fingerprint),
    a back link list (``<link type>_back``), ``parent_needs``, ``parts`` (a part's text is in ``content``),
    ``constraints``, where the need is (``docname``, ``lineno``, ``sections``),
    how it is shown (``layout``, ``style``, ``collapse``, ``hide``, the templates),
    what sphinx-needs records about it (``is_external``, ``has_dead_links`` and the like),
    or a field an extension or a service registers, such as :ref:`needgantt`'s ``duration`` and ``completion``,
    unless the project declares it itself in :ref:`needs_fields` or :ref:`needs_extra_options`.
  - A name enters only where the need's value differs from the field's default, compared as JSON text:
    the field's ``default``, else ``null`` for a nullable field
    (a default that is a ``[[…]]`` or a variant is no literal default, and so counts as none),
    and for a field that is neither, nothing: it always enters.
    ``status`` and ``tags`` are compared against theirs (``null`` and ``[]`` unless configured),
    ``content`` against ``""``, and ``id``, ``type`` and ``title`` always enter.
    A link type, and ``tags``, without a literal default are compared against ``[]``.
    A ``number`` field's value and default are compared, and written, as floats: ``default = 1`` is ``1.0``.
    So a value written equal to its default is the same as leaving it unset,
    while ``""``, ``false``, ``0`` or ``[]`` differ from a ``null`` default, and ``-0.0`` from ``0.0``.
  - Declaring a new field or link type moves no fingerprint while the needs leave it unset,
    if its default is a literal or there is none.
    A default that is a ``[[…]]`` or a variant, and ``predicates``, give the needs a value,
    which enters as a written one would:
    adding ``owner`` with ``default = "[[copy('title')]]"`` moves the fingerprint of every need,
    and adding ``severity`` with ``predicates = [["type == 'spec'", "major"]]`` that of every ``spec``.
  - Changing a field's ``default`` moves the fingerprints of the needs that wrote the old or the new default out,
    and not of those that rely on it, although their value changes.
  - A link list is written as for ``hash``, and compared with its default the same way: the ids it links to,
    without their conditions, sorted and without duplicates.
    So a condition pinning another need's fingerprint never moves the fingerprint of the need holding it,
    while linking another need does.
  - ``exclude`` leaves names out, such as ``exclude = ["id"]``, under which two needs with the same contents
    have the same fingerprint.
  - It is computed after every other rule, from the need's final values
    (after every :ref:`needextend`, variant and ``[[…]]``), and reads no derived field,
    so two fingerprints with the same ``exclude`` hold the same value.
  - No later release changes which names a fingerprint includes, when a name enters, or how the text is written:
    a fingerprint written down stays current until the need, or the configuration of the fields it reads, changes.

  For a need ``REQ_1`` of type ``req``, titled ``Größe``, with status ``open`` and no other value set,
  the text is ``{"id":"REQ_1","status":"open","title":"Größe","type":"req"}``.
- **links.** Every need, and with ``include_parts`` every need's parts (after it, in part-id order),
  in need-id order (the ids compared as strings, by code point: ``T_10``, ``T_2``, ``T_9``);
  this need and its parts are left out unless ``include_self``.
  With ``join``, the needs that match (:ref:`needs_derive_join`), in the same order.
  ``needs.json`` writes the list sorted naturally, as every link list (``T_2``, ``T_9``, ``T_10``).
- **content_links.** The ``:need:`` references of this need's content (or of the content of the need ``from`` names),
  in document order, each once: a reference to a part is a part link, a reference to this need is kept,
  a reference to no need is kept (and reported as any dead link), a disabled one (``!ID``) and those inside a
  nested need are not. With ``where``, only the references to needs it holds on are kept (a part through its need).
- **union.** The links of each link type ``fields`` names, in that order, each in its own order,
  a link kept the first time it comes: see :ref:`needs_derive_union`.

.. _`needs_derive_union`:

A union of link types
---------------------

.. versionadded:: 9.1.0

A link type deriving ``union`` holds the links of other link types, its members, which ``fields`` names:

.. code-block:: toml

   [needs.links.blocks]

   [needs.links.tests]

   [needs.links.all_links]
   outgoing = "all links"
   incoming = "all links from"
   derive = { kind = "union", fields = ["links", "blocks", "tests"] }

A need whose ``links`` is ``REQ_1``, whose ``blocks`` is ``REQ_2`` and whose ``tests`` is ``REQ_1``
then holds ``REQ_1, REQ_2`` in ``all_links``, and ``REQ_1`` and ``REQ_2`` hold it in ``all_links_back``.
It is the declared spelling of "every outgoing link of these types", which ``copy = true`` gave by copying
into ``links`` (deprecated, see :ref:`needs_links`).

- **Members.** Any link type the need has: ``links``, one of :ref:`needs_links` or :ref:`needs_extra_links`,
  one need types declare alone, a derived link type, another union -- each computed before the union,
  whether its links are written, computed by a rule, a built-in function such as ``links_from_filter``, a variant,
  or added by a ``needextend``.
  Not a member filled by one of your own :ref:`functions <needs_functions>` (such as sphinx-test-reports' ``tr_link``),
  nor by a call whose filter cannot be read, such as a ``links_from_filter`` whose filter names ``needs``:
  those run after the other built-in functions of their step, a union's rule included
  (see :ref:`needs_processing_order`), so the union cannot read the member, which is one
  ``needs.derive_scope`` warning, the union holding no links. Keep ``copy`` for such a link type until a later
  release lets a union read it.
  ``parent_needs`` and the back links (``<link type>_back``, built after the link types) are not members,
  nor is a field, and a member is named once; the union itself, or two unions naming each other, can be computed
  on no need. Each is one ``needs.derive_invalid`` at load, and the union holds no links.
  On a need of a type that does not have a member, the member holds no links, and adds none.
- **The links.** Each member's links, in the order ``fields`` names the members, each member's in its own order;
  a link is kept the first time it comes, a link being its target, its part and its condition:
  ``REQ_1`` from two members is one link, while ``REQ_1``, ``REQ_1.p1`` and ``REQ_1[status == 'open']`` are three.
  Parts and conditions are carried as written. ``needs.json`` writes the list sorted, as every link list;
  the order above is what a rule or a ``[[…]]`` reading the union in the pass sees.
- **Dead links and conditions are the members'.** Where its rule computed it, a union reports no dead link and no
  failed link condition of its own:
  each is reported once, at the member, which decides with its own ``allow_dead_links`` whether a dead link is allowed.
  So a dead link of a member allowing dead links is kept in the union and makes no dead link forbidden
  (``has_forbidden_dead_links``; ``has_dead_links`` counts it, as every dead link), it is drawn in a need's layout as
  the member allows it, and an ``allow_dead_links`` on a link type all of whose rules are unions is refused
  (``needs.derive_invalid``) and ignored; beside a rule of another kind, for another need type, it is that rule's.
  ``target_types`` is refused on it, as on every derived link type: the members' own apply.
- **When.** In the link fields' step, after every :ref:`needextend`: a link a ``needextend`` adds to a member is in the union.
  The union itself is closed, as every derived field: links written in it, or by a ``needextend``, are reported
  (``needs.derive_authored``) and ignored.
- **Imported needs keep their data.** No rule runs on a need from :ref:`needimport` or :ref:`needs_external_needs`:
  it holds the union its needs.json carries, else no links, whatever its members hold.
  Those links are not its members', so they are checked as any link type's, under the union's own
  ``allow_dead_links``: a dead one is reported, under the union, and is a forbidden one.
- **Not counted as dense.** ``needs.derive_dense`` (:ref:`needs_derive_cost`) counts the links its members compute,
  not the union's list, which holds them again.
- It is left out of every ``fingerprint``, as every derived link type is, and it may be declared per need type
  (``derive_by_type``, or a need type's ``links`` entry, :ref:`needs_types_fields`).

**Reading it.** A union is read where ``links`` holding the copies was read, by its name:

- :ref:`needflow` (and :ref:`needsequence`, :ref:`needgantt`'s ``starts_after_links``): ``:link_types: all_links``.
  A needflow drawing every link type (or the members and the union) draws an edge of the union beside each member's,
  so name either the union, which draws one style, or its members, which keep theirs.
- :ref:`Filter strings <filter_string>`: ``"REQ_1" in all_links``; a rule's ``over = "all_links"``
  or ``over = "all_links_back"``.
- :ref:`needtable` columns: ``all_links`` and ``all_links_back`` (``OUTGOING`` and ``INCOMING`` stay ``links``).
- A need's layout shows it as one more row, as every link type with links; ``meta_links_all(exclude=[...])`` leaves it out.

Some readers read only ``links`` in this release, and take no link type yet: :ref:`check_linked_values <check_linked_values>`,
:ref:`calc_sum <calc_sum>` with ``links_only``, and the :ref:`need_outgoing <role_need_outgoing>` and :ref:`need_incoming <role_need_incoming>` roles written
in a need's content. While ``copy = true`` is in use they see the copies, as before.
A project that relies on them keeps ``copy = true`` until 10.0, and with it the ``needs.deprecated`` warning;
``suppress_warnings = ["needs.deprecated"]`` silences it, and every other deprecation with it.

A rule that cannot be computed on a need leaves the field at its empty value, and is reported:
a cycle of rules or calls reading one another (``needs.derive_cycle``, see :ref:`needs_derive_cycle`),
a read of a value its step cannot wait for (``needs.derive_scope``, see :ref:`needs_derive_scope`),
or a ``from`` naming no need, and a result the field's ``schema`` refuses, such as a value outside its ``enum`` or under its ``minimum``
(``needs.dynamic_function``); a result is checked even when it equals the empty value,
such as a ``count`` of ``0`` under ``minimum = 1``.
To silence a warning, add its type to Sphinx's ``suppress_warnings``:

.. code-block:: python

   suppress_warnings = ["needs.derive_invalid", "needs.derive_authored", "needs.derive_unique"]

.. _`needs_derive_changed`:

Detecting a changed need
------------------------

A ``fingerprint`` changes whenever its need does,
so a :ref:`link condition <need_conditional_links>` naming the fingerprint a need had when it was reviewed
reports the need once it changes:

.. code-block:: toml

   [needs.fields.fp]
   schema = { type = "string" }
   derive = { kind = "fingerprint" }

.. code-block:: rst

   .. spec:: Reviewed against REQ_1
      :id: SPEC_1
      :links: REQ_1[fp == "3f9a1c2b7d4e0a8c6f1e5d2b9a7c4e3f8d6b1a0c9e7f5d3b2a4c6e8f0a1b3c5d"]

While ``REQ_1`` is unchanged, the condition holds.
Once its title, content, status or any other value it includes changes, its fingerprint does,
and the build reports ``needs.link_condition_failed`` at ``SPEC_1``;
writing the new fingerprint into the condition accepts the change.
Writing only the start of the fingerprint is enough to tell a change apart:
``REQ_1[fp.startswith('3f9a1c2b7d4e')]``.

The executable half of :ref:`needs_derive` is a conformance corpus,
``packages/sphinx-needs/tests/fixtures/derive_conformance.toml`` in the sphinx-needs repository:
one project per rule, with the values its needs hold and the warnings it gives,
which sphinx-needs' test suite runs and ubCode vendors, and is held to.

.. _dynamic_functions_derived:

Rules and inline calls
----------------------

.. versionadded:: 9.0.0

A built-in call computes a value for the one need it is written in.
A :ref:`derived field <needs_derive>` declares the same computation once, in :ref:`needs_fields` or :ref:`needs_links`,
for every need of the project:

.. code-block:: toml

   [needs.fields.total_hours]
   schema = { type = "number" }
   derive = { kind = "sum", field = "hours", over = "links" }

is the declared form of ``:total_hours: [[calc_sum("hours", links_only=True)]]`` written in every need,
and both are computed in the same step (see :ref:`needs_processing_order`): a declared rule is the field's value,
as a call written in it would be, but an author cannot set the field.
The built-in functions are the per-need spellings of the kinds:

.. list-table::
   :header-rows: 1
   :widths: 46 54

   * - inline call
     - the kind it spells
   * - ``copy("x")``, ``copy("x", "ID")``
     - ``copy`` with ``field = "x"``, and ``from = "ID"``
   * - ``copy("x", filter=…)``
     - no declared form: the lowest-id need the filter keeps, read from every need
   * - ``calc_sum("x", links_only=True)``
     - ``sum`` with ``field = "x"`` and ``over = "links"``; its ``filter`` is the ``where``
   * - ``calc_sum("x")``, ``calc_sum("x", filter=…)``
     - no declared form: a sum over every need
   * - ``check_linked_values(result, "x", values, filter, one_hit)``
     - ``all`` over ``links`` (``any`` with ``one_hit``), with the ``test`` ``x in values`` and the ``where`` ``filter``,
       giving ``result``; with ``one_hit``, ``result`` even when no linked need matches, which ``any`` does not
   * - ``links_from_content()``, ``links_from_content("ID", filter=…)``
     - ``content_links``, with ``from = "ID"`` and the ``where`` ``filter``
   * - ``links_from_filter(filter, include_self, include_parts)``
     - ``links``, with the ``where`` ``filter`` and the same ``include_self`` and ``include_parts``
   * - ``links_from_match(field, equals, include_self, filter)``
     - ``links`` with ``join = { field = field, equals = equals }``, the same ``include_self``,
       and the ``where`` ``filter``

A ``where`` that cannot be evaluated on a candidate (one lacking a field it names) drops that candidate,
without a warning, in every kind and in ``links_from_filter``;
the ``filter`` of ``calc_sum``, ``check_linked_values`` and ``links_from_content`` keeps its own behaviour.

Written in many needs, ``links_from_filter``, ``links_from_content`` and ``links_from_match`` store a list on each,
counted as a rule's lists are: see :ref:`needs_derive_cost`.

The ``join`` role (:ref:`needs_derive_join`) spells such a correlated lookup, as sphinx-test-reports' ``tr_link`` does,
and :ref:`links_from_match` is its inline spelling.
A ``copy("x", filter=…)`` whose filter compares a need with ``current_need`` (``name == current_need['ref']``)
is such a lookup too, its filter tested on every need for each need it is in:
a ``copy`` with ``join`` is the declared form of such a lookup (it splits the values,
and finds no value rather than this need's own when nothing matches).
A rule for some need types is declared under ``derive_by_type`` (:ref:`needs_derive_by_type`), not with a role.
