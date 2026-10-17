.. _`need_types_howto`:

Modeling need types
===================

A need type's entry in :ref:`needs_types` can declare the fields and link types of its needs:
which fields the type has, which values they take, their defaults, and which link types the type uses.
This page walks through the common tasks with one example project;
the rules themselves are in the reference, :ref:`needs_types_fields`.

The examples use the table shape of ``needs_types`` in a :ref:`needs_from_toml` file, ``[needs.types.<directive>]``.
In :file:`conf.py` the same entries are dictionaries, see :ref:`needs_types`.

The project is
`doc_need_types <https://github.com/useblocks/sphinx-needs/tree/master/packages/sphinx-needs/tests/doc_test/doc_need_types>`__
in the test suite, which checks the warnings quoted on this page:

.. dropdown:: ubproject.toml

   .. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
      :language: toml

.. dropdown:: index.rst

   .. literalinclude:: ../tests/doc_test/doc_need_types/index.rst
      :language: rst

It has three need types; a ``safety_req`` is a kind of ``req``:

.. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
   :language: toml
   :start-after: # [types]
   :end-before: # [/types]

How it works
------------

A need type reads every field and link type as the project declares it for all types
(:ref:`needs_fields`, :ref:`needs_links`, and the core fields such as ``status``),
unless its own entry, or the entry of a type it inherits from, declares it anew.
Such a declaration narrows the field for the needs of that type and of every type that inherits from it:
fewer allowed values, a value required, a default of its own -- never more than the field allows.
A name that nothing else declares is a field, or a link type, of the types that declare it alone:
on the needs of every other type it is ``None`` (a link type holds no links),
and a value set there is ignored with a warning.

In this project, where the ``status``, ``hazard`` and ``verdict`` of each type's needs come from:

.. mermaid::
   :alt: status narrowed by req and inherited by safety_req, narrowed differently by test; hazard declared by safety_req alone and verdict by test alone; what a need of each type holds

   flowchart LR
     status["status, a core field<br/>any string, or None<br/>no default"]
     req["req declares status:<br/>enum draft, approved<br/>default draft"]
     safety["safety_req inherits req:<br/>status as req declares it"]
     hazard["safety_req declares hazard:<br/>a string, not nullable, no default<br/>no needs_fields entry declares it"]
     test_type["test declares status:<br/>enum open, done<br/>default open"]
     verdict["test declares verdict:<br/>enum passed, failed<br/>no needs_fields entry declares it"]
     req_need(["a req need<br/>status: draft unless it says<br/>another value is reported, the need kept<br/>hazard, verdict: None, a value set is ignored"])
     safety_need(["a safety_req need<br/>status: draft unless it says<br/>another value is reported, the need kept<br/>hazard: required, else the need is not created<br/>verdict: None, a value set is ignored"])
     test_need(["a test need<br/>status: open unless it says<br/>another value is reported, the need kept<br/>verdict: None unless it says<br/>hazard: None, a value set is ignored"])
     status -->|narrowed by| req -->|inherited by| safety
     status -->|narrowed by| test_type
     req --> req_need
     safety --> safety_need
     hazard --> safety_need
     test_type --> test_need
     verdict --> test_need

A field or link type that need types declare alone, such as ``hazard`` and ``verifies`` here,
reaches the type that declares it and the types inheriting from it, never the types above it or beside it:

.. mermaid::
   :alt: hazard declared by safety_req alone and verifies by test alone; safety_req inherits req; what a need of each type holds

   flowchart LR
     req["req"]
     safety["safety_req<br/>inherits req"]
     test_type["test"]
     hazard["hazard<br/>declared by safety_req alone"]
     verifies["verifies, a link type<br/>declared by test alone"]
     req_need(["a req need<br/>hazard: None, verifies: []<br/>a value set is ignored, needs.undeclared_for_type"])
     safety_need(["a safety_req need<br/>hazard: as safety_req declares it<br/>verifies: [], a value set is ignored"])
     test_need(["a test need<br/>verifies: its links<br/>hazard: None, a value set is ignored"])
     req -->|inherited by| safety
     hazard --> safety
     verifies --> test_type
     req --> req_need
     safety --> safety_need
     test_type --> test_need

Every type that declares such a name agrees on its shape,
which the first declaration of a type without a declaring ancestor sets,
in the order the types are resolved (a parent before its children):
for a field, the first that gives a ``schema`` ``type`` sets that type and whether the field is derived;
for a link type, the first, an empty one too, sets whether it is derived,
its labels, its styles, ``copy`` and whether dead links are allowed.
Another declaration that disagrees with the shape is ignored, as a ``needs.type_conflict`` warning.
The rules in full are in :ref:`needs_types_fields`.

A field only one type has
-------------------------

A ``fields`` entry can name a field that nothing else declares --
no :ref:`needs_fields` entry, no core field, no link type, and no field a service or an extension registers.
The field then exists on the needs of the types that declare it, and only there.
Give it a ``schema`` ``type``: without one, the entry is refused (see :ref:`need_types_misspelt`):

.. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
   :language: toml
   :start-after: # [verdict]
   :end-before: # [/verdict]

Only a ``test`` has a ``verdict``; on the needs of the other types it is ``None``.
A ``verdict`` set on a ``req`` is ignored, and the need is kept without it:

.. code-block:: text

   index.rst:8: WARNING: Field 'verdict' is not declared on need type 'req' and cannot be set in need 'R_002'; the value 'passed' is ignored [needs.undeclared_for_type]

This documentation's own configuration declares four such fields, ``hours``, ``amount``, ``value`` and ``unit``,
on the types whose needs use them:

.. dropdown:: The need types of this documentation's ubproject.toml

   .. literalinclude:: ubproject.toml
      :language: toml
      :start-at: # The need types
      :end-before: [needs.links.blocks]

Status values per type
----------------------

``status`` is a core field, and a type may narrow it like any other:
give it an ``enum``, and a ``default`` inside it.
This takes the place of :ref:`needs_statuses`, which is deprecated and gives one list for every type:

.. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
   :language: toml
   :start-after: # [status]
   :end-before: # [/status]

A ``req`` that sets no status is ``draft``, a ``test`` ``open``.
A value outside the list is reported by the :ref:`schema validation <schema_validation>`, and the need is kept:

.. code-block:: text

   ERROR: Need 'R_003' has schema violations:
     Severity:       violation
     Field:          status
     Need path:      R_003
     Schema path:    fields > schema > properties > status > enum
     Schema message: "done" is not one of "draft" or "approved" [sn_schema_violation.field_fail]

Tags per type
-------------

``tags`` is a list, so its allowed values are an ``enum`` of its ``items``.
This takes the place of :ref:`needs_tags`, which is deprecated:

.. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
   :language: toml
   :start-after: # [tags]
   :end-before: # [/tags]

.. code-block:: text

   ERROR: Need 'R_004' has schema violations:
     Severity:       violation
     Field:          tags.0
     Need path:      R_004
     Schema path:    fields > schema > properties > tags > items > enum
     Schema message: "security" is not one of "functional", "performance" or "safety" [sn_schema_violation.field_fail]

A subtype with inherits
-----------------------

``inherits = "req"`` makes a ``safety_req`` start from the declarations of a ``req``:
it takes the same status values and tags, ``draft`` when it sets no status,
and the per-type defaults of a ``req`` (below).
Its own entries add to them, and may only narrow them:
a declaration that would widen its parent's is ignored, with a ``needs.type_widening`` warning
(see :ref:`needs_types_fields`).

A field required on one type
----------------------------

A field declared ``nullable = false`` with no default is required on the needs of the type:

.. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
   :language: toml
   :start-after: # [hazard]
   :end-before: # [/hazard]

.. warning::

   A need without a required field is **not created**:
   it is not rendered and not in the :ref:`needs.json <needs_builder>`, and every link to it becomes a dead link.

   .. code-block:: text

      index.rst:25: WARNING: Need could not be created: Field 'hazard' is not nullable, but no value or default was given. [needs.create_need]

   To report a need without the field and keep it, use a schema rule's ``required`` instead:
   see :ref:`schema_per_type_or_rules`.

A link type only one type may use
---------------------------------

A ``links`` entry can name a link type that nothing else declares;
it is then a link type of that type's needs alone, with its labels.
A ``minItems`` or ``maxItems`` sets how many links a need of the type has:

.. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
   :language: toml
   :start-after: # [verifies]
   :end-before: # [/verifies]

A ``test`` without ``verifies`` links is reported:

.. code-block:: text

   ERROR: Need 'T_002' has schema violations:
     Severity:       violation
     Field:          verifies
     Need path:      T_002
     Schema path:    links > schema > properties > verifies > minItems
     Schema message: [] has less than 1 item [sn_schema_violation.link_fail]

``verifies`` set on a need of another type is ignored with a ``needs.undeclared_for_type`` warning, as for a field.
Which types a ``test`` may link to is a rule about the linked needs: that takes a schema rule,
see :ref:`schema_per_type_still_rules`.

Defaults per type
-----------------

A type's ``default`` for a core field sets how its needs look:
their :ref:`layout <need_layout>`, :ref:`style <need_style>`, and whether they are collapsed.

.. literalinclude:: ../tests/doc_test/doc_need_types/ubproject.toml
   :language: toml
   :start-after: # [defaults]
   :end-before: # [/defaults]

A ``req`` and a ``safety_req`` have the style ``green_bar``; a ``test`` has the layout ``clean_l`` and is collapsed.
A need that sets the field itself keeps its own value.
``template``, ``pre_template``, ``post_template`` and ``constraints`` take a default per type the same way:

.. code-block:: toml

   [needs.types.test.fields.template]
   default = "test_case"

   [needs.types.test.fields.constraints]
   default = ["test_passed"]

gives every ``test`` the :ref:`template <need_template>` ``test_case``
and the :ref:`constraint <needs_constraints>` ``test_passed``, which :ref:`needs_constraints` defines.

From needs_global_options to a type's defaults
----------------------------------------------

:ref:`needs_global_options` is deprecated (a build that sets it warns ``needs.deprecated``).
A predicate of it that tests the type,

.. code-block:: python

   needs_global_options = {
       "layout": {"predicates": [("type == 'test'", "clean_l")]},
   }

becomes a default in the type's entry, as ``[needs.types.test.fields.layout]`` above.
The two are not quite the same:

- a type's default also applies to the types that inherit from it, where ``type == 'req'`` matches a ``req`` alone:
  the ``green_bar`` default of a ``req`` above is the style of a ``safety_req`` too;
- a predicate of the field still wins over a type's default.
  Remove the predicate when you move it into a type's entry,
  or give the type ``predicates = []``, which replaces the field's predicates on the type's needs.

Filters over a field some types lack
------------------------------------

A field of some types alone is ``None`` on the needs of the others,
so a :ref:`filter string <filter_string>` that calls a method on it raises on those needs.
Test the type, or the value, first:

.. literalinclude:: ../tests/doc_test/doc_need_types/index.rst
   :language: rst
   :start-after: .. good-filter-start
   :end-before: .. good-filter-end

Without it, the filter is reported once, and leaves out every need it raised on:

.. code-block:: rst

   .. needtable::
      :filter: hazard.startswith("loss")

.. code-block:: text

   index.rst:51: WARNING: Filter 'hazard.startswith("loss")' not valid. Error: 'NoneType' object has no attribute 'startswith'. [needs.filter]

.. note::

   A name that a :ref:`service <services>` or an extension registers is not a field of one type alone,
   even when no ``needs_fields`` entry names it:
   a configured GitHub service's ``url`` and ``user``, :ref:`needgantt`'s ``duration``,
   or the fields an extension such as sphinx-test-reports adds.
   A type's entry on such a name narrows that field on the type,
   and the needs of the other types still set it without a warning.
   The :ref:`needs.json <needs_builder>` tells the two apart:
   a field of some types alone has the description ``Declared by need types ...``,
   a registered one keeps its own, such as ``Added by service github-issues``.

.. _`need_types_misspelt`:

A misspelt field name
---------------------

.. warning::

   A ``fields`` entry naming no field declared elsewhere declares a new one.
   So a misspelt name with a ``schema`` ``type``, such as ``[needs.types.safety_req.fields.hazrd]``,
   gives no warning: it declares a field ``hazrd`` of the ``safety_req`` needs,
   and the misspelt declaration constrains nothing.
   The :ref:`needs.json <needs_builder>` lists it, with the description ``Declared by need types 'safety_req'``.
   A misspelt name without a ``schema`` ``type`` is refused, as a ``needs.type_conflict`` warning::

      needs_types['safety_req'].fields['hazzard'] declares 'hazzard', which no needs_fields entry declares, and no need type without an ancestor declaring it gives it a 'schema' 'type'; the entry is ignored

When to use schema rules
------------------------

A type's entry says what a need of the type may hold.
Rules about the needs it links to, incoming links, conditions between fields
and the other cases of :ref:`schema_per_type_still_rules` take :ref:`schema rules <schema_validation>`;
:ref:`schema_per_type_or_rules` compares the two, and how each reports.
