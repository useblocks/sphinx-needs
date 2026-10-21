.. _v_model:

Sphinx-Needs across the V-model
===============================

Engineering along the V-model runs in five steps:
**define** what the system must do, **implement** it, **verify** it, **iterate** when something changes,
and **prove** at a release that every requirement is implemented, verified and traced.
This page maps each step to what Sphinx-Needs and its sibling extensions offer,
and links the pages that describe it.

.. mermaid::
   :alt: define, then implement, then verify, then prove; a change sends the work back through iterate to define

   flowchart LR
     define["Define<br/>need types, links, schemas"]
     implement["Implement<br/>Sphinx-CodeLinks"]
     verify["Verify<br/>Sphinx-Test-Reports, warnings"]
     prove["Prove<br/>tables, charts, needs.json"]
     iterate["Iterate<br/>back links, filters, needextend"]
     define --> implement --> verify --> prove
     verify -.->|a change| iterate -.-> define

.. _v_model_define:

Define
------

Requirements, specifications and test cases become typed needs, linked along the V-model.

- The :ref:`need` directive writes a need in your documentation;
  the :ref:`tutorial` builds a small linked model step by step.
- :ref:`needs_types` declares your need types,
  and :ref:`need_types_howto` shows how to give each type its own fields and links.
- :ref:`needs_links` declares link types, such as a specification that implements a requirement.
- :ref:`schema_validation` states the rules your needs and their links must follow:
  the type of each field, which fields a type requires, and which needs a link may point to.

.. _v_model_implement:

Implement
---------

The code that realises a requirement, traced back to it.

- `Sphinx-CodeLinks <https://codelinks.useblocks.com>`__ reads one-line markers from your source code comments:
  a marker either defines a new need, or names an existing need's ID to trace the code to it.

.. _v_model_verify:

Verify
------

Test results traced to the needs they verify, and a build that fails when a rule is broken.

- `Sphinx-Test-Reports <https://sphinx-test-reports.readthedocs.io/en/latest/>`__ turns JUnit XML and JSON test results
  into needs, which you can link to the specifications they test, filter and report on.
- A broken schema rule is reported in the build log, as a warning or an error by its :ref:`severity <severity_levels>`;
  build with ``-W`` to make the build fail on it (:ref:`config-warnings`).

.. _v_model_iterate:

Iterate
-------

A change to one need, and the needs it touches.

- Every link type has back links, named ``<link>_back``:
  a need's card shows the needs that link to it, and a :ref:`needtable` can list them as a column.
- A :ref:`filter string <filter_string>` selects the needs a question is about,
  such as every test linked to one requirement.
- :ref:`needextend` changes existing needs in bulk, for example the status of every need a filter selects.
- The :ref:`needs builder <needs_builder>` can store each documentation version's needs
  side by side in one ``needs.json``,
  and :ref:`needimport` imports the needs of a ``needs.json``, such as another project's.

Sphinx-Needs has no impact analysis of its own;
`ubCode <https://ubcode.useblocks.com/features/diff/index.html>`__ adds it with ``ubc diff``.

.. _v_model_prove:

Prove
-----

The evidence for a release, built from the same sources as the documentation.

- :ref:`needtable`, :ref:`needflow` and :ref:`needpie` render traceability tables, diagrams and charts from a filter,
  and :ref:`needextract` renders copies of the needs a filter selects in another document.
- A Sphinx builder, such as HTML, publishes the result;
  the :ref:`needs builder <needs_builder>`, or :ref:`needs_build_json` beside another builder,
  exports every need to ``needs.json`` for other tools to read.
