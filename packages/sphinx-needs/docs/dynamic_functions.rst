========================
Delayed field evaluation
========================

Sphinx-needs offers the possibility to delay the evaluation of certain need field values until all needs have been collected, and thus can be based on this data.

There are two syntaxes provided to achieve this:

- Using double square brackets ``[[...]]`` to encapsulate a dynamic function call.
- Using double angled brackets ``<<...>>`` to encapsulate a variant definition.

.. _dynamic_functions:

Dynamic functions
=================

Dynamic functions provide a mechanism to specify need fields or content that are calculated at build time, based on other fields or needs.

We do this by giving an author the possibility to set a function call to a predefined function, which calculates the final value **after all needs have been collected**.

For instance, you can use the feature if the status of a requirement depends on linked test cases and their status.
Or if you will request specific data from an external server like JIRA.

To refer to a dynamic function, you can use the following syntax:

- In a need directive option, wrap the function call in double square brackets: ``[[function_name(arg)]]``
- In a need content, use the :ref:`ndf` role: ``:ndf:`function_name(arg)```

.. syntax-example:: Dynamic function example

   .. req:: my test requirement
      :id: df_1
      :status: open
      :tags: test;[[copy("status")]]

      This need has id :ndf:`copy("id")` and status :ndf:`copy("status")`.

The ``[[...]]`` syntax applies to directive **options** only; the following are supported:

- ``status``
- ``tags``
- ``style``
- ``layout``
- ``constraints``
- :ref:`extra fields <needs_fields>`
- :ref:`needs_links`

Inside a need's **content**, the :ref:`ndf` role is the way to call a dynamic function.

.. versionchanged:: 9.0.0

   The ``[[...]]`` syntax is no longer interpreted in a need's content, where it is now
   plain text as in any other Sphinx document; use the :ref:`ndf` role instead.

.. _dynamic_functions_need_arguments:

An argument can be a field of the need the call is in, written ``need.<field>``:
``:summary: [[copy("summary", need.parent)]]`` copies ``summary`` from the need whose id the need's ``parent`` holds.
Where such an argument selects what the call reads
(the need of :ref:`copy <copy>` or :ref:`links_from_content <links_content>`,
the field of ``copy``, :ref:`calc_sum <calc_sum>` or :ref:`check_linked_values <check_linked_values>`,
a ``filter``, or ``links_only``),
its field must be final before the call is computed (see :ref:`needs_processing_order`):
written in the need or by a ``needextend``, or a link field read from any field that is not one.
Otherwise the call is not run, its field holds what a field on a cycle holds
(:ref:`needs_derive_cycle`), and ``needs.derive_scope`` says so (:ref:`needs_derive_scope`).
If the field is unset or empty, the call fails (``needs.dynamic_function``):
``copy`` does not read the need it is in instead.
Any other argument (such as ``check_linked_values``' ``result`` or ``search_value``, or ``copy``'s ``upper``)
is a value: its field is read like any other, after it is computed, and is ``None`` when unset
(``""`` for an untyped extra option).

.. versionchanged:: 9.0.0

   ``need.<field>`` arguments are accepted in field and link values, a ``needextend``'s included;
   a need that used one in its own field was not created,
   and a ``needextend`` value that used one was dropped with a ``needs.needextend`` warning.

Built-in functions
-------------------

The following functions are available by default.

.. note::

   The parameters ``app``, ``need`` and ``needs`` of the following functions are set automatically.
   So is ``reads``, the keyword-only parameter of :ref:`copy <copy>`, :ref:`check_linked_values <check_linked_values>`
   and :ref:`calc_sum <calc_sum>` through which they report the reads that cannot be ordered
   (see :ref:`needs_derive_scope`). It is reserved: do not give it in a call (doing so fails the call).

test
~~~~
.. autofunction:: sphinx_needs.functions.common.test

.. _echo:

echo
~~~~
.. autofunction:: sphinx_needs.functions.common.echo

.. _copy:

copy
~~~~
.. autofunction:: sphinx_needs.functions.common.copy

.. _check_linked_values:

check_linked_values
~~~~~~~~~~~~~~~~~~~
.. autofunction:: sphinx_needs.functions.common.check_linked_values


.. _calc_sum:

calc_sum
~~~~~~~~

.. autofunction:: sphinx_needs.functions.common.calc_sum

.. _links_content:

links_from_content
~~~~~~~~~~~~~~~~~~

.. autofunction:: sphinx_needs.functions.common.links_from_content

.. _links_from_filter:

links_from_filter
~~~~~~~~~~~~~~~~~

.. autofunction:: sphinx_needs.functions.common.links_from_filter


.. _dynamic_functions_derived:

Derived fields: the declared form
---------------------------------

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

The ``join`` role, which will spell sphinx-test-reports' ``tr_link``, is reserved for a later release:
a rule naming it is reported as ``needs.derive_invalid``.

Develop own functions
---------------------

Registration
~~~~~~~~~~~~

You must register every dynamic function by using the :ref:`needs_functions` configuration parameter,
inside your **conf.py** file, to add a :py:class:`.DynamicFunction`:

.. code-block:: python

   def my_own_function(app, need, needs):
       return "Awesome"

   needs_functions = [my_own_function]

A function is registered, and called in a need, by its ``__name__``.
An entry that is not callable, or has no ``__name__`` (such as a ``functools.partial``),
is ignored with a ``needs.config`` warning;
register a callable without a ``__name__`` with :py:func:`~sphinx_needs.api.configuration.add_dynamic_function`,
giving its ``name``.

.. warning::

   Assigning a function to a Sphinx option will deactivate the incremental build feature of Sphinx.
   Please use the :ref:`Sphinx-Needs API <api_configuration>` and read :ref:`inc_build` for details.

   **Recommended:** You can use the following approach we used in our **conf.py** file to register dynamic functions:

   .. code-block:: python

         from sphinx_needs.api import add_dynamic_function

            def my_function(app, need, needs, *args, **kwargs):
                # Do magic here
                return "some data"

            def setup(app):
                  add_dynamic_function(app, my_function)

.. _needs_processing_order:

Processing order
~~~~~~~~~~~~~~~~

.. versionchanged:: 9.0.0

   The ``[[…]]``, ``<<…>>`` and ``<{…}>`` are computed in dependency order,
   instead of need by need in the order the needs were read.

Once every document has been read, and before any page is written, the needs are post-processed in this fixed order:

1. The :ref:`needextend` directives are applied, sorted by :ref:`extend priority <needextend_extend_priority>` (lower first),
   then by document name and then by line.
   Each filter sees the needs as written, before any extend is applied (:ref:`needextend_as_written`),
   so it never sees the change of another extend, nor the value of a ``[[…]]``, ``<<…>>`` or ``<{…}>``;
   a filter that names a field such a value is computed for is reported (:ref:`needs_derive_scope`).
   A ``needextend`` may itself set a field it can modify to a ``[[…]]`` or ``<<…>>``,
   which is then computed like one written in the need; until it is, the field holds what is written in it
   besides calls: an array the items written before a call was appended to them, any other field its empty value.
2. The ``[[…]]``, ``<<…>>`` and ``<{…}>`` of the :ref:`link fields <needs_links>` are computed,
   with the rules of the :ref:`derived link types <needs_derive>` (``links``, ``content_links``),
   each after the link fields it reads, and those that call your own :ref:`functions <needs_functions>` last.
3. The back links are built from the links of steps 1 and 2, each back link list in need-id order.
4. Every other ``[[…]]``, ``<<…>>`` and ``<{…}>`` is computed, with the rules of the
   :ref:`derived fields <needs_derive>`, each after every value it reads
   (a field of its own need or of another need, a field of a linked need, a back link),
   and those that call your own functions last.
   Then the rules of the kind ``hash``, and those with ``after = "derived"``, are computed, each after the
   values it reads; a ``[[…]]`` of step 4 that reads one of their fields is not run (:ref:`needs_derive_scope`).
5. Link conditions are checked, against the computed values and the complete back links,
   and links to unknown needs are reported.
   Then the link lists are sorted for the output, and constraints are checked (:ref:`needs_constraints`).
   Then the needs are frozen, and :ref:`schema validation <schema_validation>`, every page,
   and the :ref:`needs_warnings` checks at the end of the build see their final values.

So the value of a field does not depend on the order of the documents, on the documents an incremental build re-read,
on ``-j``, on the order of the options in a directive, or on the order the fields are declared in.
A chain gives the chained value:

.. code-block:: rst

   .. req:: A
      :id: REQ_A
      :status: [[copy("status", "REQ_B")]]

   .. req:: B
      :id: REQ_B
      :status: [[copy("status", "REQ_C")]]

   .. req:: C
      :id: REQ_C
      :status: done

``REQ_A`` and ``REQ_B`` are ``done`` in every build.

What each built-in function reads, and so is computed after:

=====================================  ==============================================================================
call                                   reads
=====================================  ==============================================================================
``copy("x")``                          ``x`` of its own need (a back link too, such as ``links_back``)
``copy("x", "ID")``                    ``x`` of the need ``ID``
``copy("x", filter=…)``                ``x`` of the match with the lowest id; ``current_need`` is its own need
``copy("x", "ID", filter=…)``          ``x`` of the lowest-id match, else of ``ID``; ``current_need`` is ``ID``
``calc_sum("x")``                      ``x`` of every need, its own included
``calc_sum("x", filter=…)``            ``x`` of every need the filter keeps
``calc_sum("x", links_only=True)``     its own ``links``, and ``x`` (and the filter's fields) of each linked need
``check_linked_values(…, "x", …)``     its own ``links``, and ``x`` (and the filter's fields) of every linked need
``links_from_content()``               the need's content
``links_from_content(filter=…)``       the filter's fields of each need the content references
``links_from_filter(filter)``          the filter's fields of every need; ``current_need`` is its own need
``<<[cond]:a, b>>``                    the fields of its own need that any of its conditions names, evaluated or not
=====================================  ==============================================================================

And what each :ref:`derive rule <needs_derive>` reads:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - rule
     - reads
   * - ``copy``, ``field = "x"``
     - ``x`` of its own need
   * - ``copy``, ``field = "x"``, ``from = "ID"``
     - ``x`` of the need ``ID``
   * - ``copy``, ``sum``, ``count``, ``min``, ``max``, ``any``, ``all`` or ``collect``, ``over = "<t>"``
     - its own ``<t>`` (or ``<t>_back``), and ``field`` and the names of ``where`` and ``test``
       on each need it names
   * - ``min`` or ``max`` with ``transitive = true``
     - ``field`` and the names of ``where`` on every need ``over`` reaches (and on its own, with ``include_self``)
   * - ``hash``, ``fields = [...]``
     - the listed fields of its own need, after every other rule
   * - ``links``, ``where = …``
     - the names of ``where`` on every need (and part)
   * - ``content_links``
     - the need's content (or that of the need ``from`` names), and the names of ``where`` on each need it references

A ``filter`` that names only values final before its step is evaluated before the step, so its matches are known:
values nothing computes, and, in step 4, the link fields and back links of steps 2 and 3.
One that names a value computed in the same step makes every need a candidate, and the call is computed after
that field and ``x`` on every need.
A filter reads the needs themselves, so only these rules order what it reads:
the check at run time (:ref:`needs_derive_scope`) does not see a filter's reads.
The needs of a set are read in need-id order, comparing ids as strings (``REQ_10`` comes before ``REQ_9``):
the candidates of a ``calc_sum`` or a ``filter``, and a back link list.
A link list is read in the order it is written, followed by the links a ``needextend`` added;
a link written twice is read twice, so a ``calc_sum`` with ``links_only`` adds its value twice.
The link lists are sorted, and a link written twice kept once, only in step 5.

A ``check_linked_values``, or a ``calc_sum`` with ``links_only``, in a link field
of a need whose ``links`` are computed too (``:links: REQ_1, [[copy("links", "REQ_2")]]``)
cannot know in step 2 which needs those links will name,
the written ones included,
so it reads ``x`` and the filter's fields as on every need, not only on the linked ones:
it is computed after each link field of step 2 that computes one of them, on any need;
it is not run when one is a back link, a dead-link flag, or a field computed in step 4 on any need
(:ref:`needs_derive_scope`);
and a field no need computes is read as written.

Your own functions run after every built-in function of their step, in need-id order, then by field.
They read the values the built-in functions computed
(but for a call whose filter cannot be read, which runs among them, see below);
a built-in function that reads a field your own function computes
reads it before it is computed, which is reported (:ref:`needs_derive_scope`).
A function of your own in a link field, such as sphinx-test-reports' ``tr_link``, runs at the end of step 2,
so its links are in the back links of step 3.
A later release is to let a function declare what it reads, which will order it like a built-in one.
A ``filter`` that names ``needs``, or reads ``current_need`` by a key that is not written out,
cannot be ordered either: its call runs with your own functions.
``calc_sum``'s filter may name ``needs`` (every need, as in the filter of a view),
but such a filter is evaluated on every need for every need it is tested on,
and only Sphinx-Needs evaluates it: rather declare a flag on each need and filter on the flag
(a derived ``any`` over the links the filter would search, see :ref:`needs_derive`).

.. _needs_derive_cycle:

Cycles
++++++

A value that reads itself, directly or through other computed values, cannot be computed.
No field on such a cycle is computed.
A link or array field keeps the items written in it and loses the computed ones
(``:links: LIT_1, [[copy("links")]]`` keeps ``LIT_1``);
any other field, and a list with nothing written, is left empty
(``None``, or for a field that is not nullable ``""``, ``0``, ``False`` or ``[]``).
Each field on the cycle is reported as ``needs.derive_cycle``, once per field, naming the needs:

.. code-block:: text

   index.rst:4: WARNING: dynamic function 'copy' for option 'summary' is on a cycle:
   'summary' on 2 needs (CYC_A, CYC_B); the field is left empty [needs.derive_cycle]

A value computed from a field on a cycle is computed from the value it holds, and is not reported.
A field whose call fails, or returns a result the field cannot hold, holds the same as a field on a cycle
(``LIT_1, [[copy("hours")]]`` in a link field keeps ``LIT_1``), and the call is reported as ``needs.dynamic_function``.
A sum over every need includes the need that holds it,
so ``:hours: [[calc_sum("hours")]]`` reads its own value and is a cycle;
sum into another field, or give a ``filter`` that excludes the need.
A ``filter`` that names a computed field makes every need a candidate,
so it can make a cycle that the filter itself would have excluded; the message then names the filter.
So do a need's own computed links, for a ``check_linked_values`` or ``links_only`` sum in a link field
(see :ref:`needs_processing_order`); the message then names the links.
Filter on a value that is not computed, or break the cycle.
A filter on values that are not computed but keeps the need itself, such as ``type == 'req'`` in a ``req``,
is a cycle too, and its message names the filter.
A variant whose condition reads the field it sets, such as ``:status: <<[status == "open"]:open, closed>>``,
is a cycle too.

.. _needs_derive_scope:

Reads that cannot be ordered
++++++++++++++++++++++++++++

These reads are reported as ``needs.derive_scope``:

- a ``[[…]]`` or ``<<…>>`` of a link field that reads a computed field that is not a link field, a back link,
  or ``has_dead_links`` or ``has_forbidden_dead_links``,
  all of which are final only after step 2 (they are computed, or set with the back links, after it):
  the call is not run (a variant's condition is not evaluated),
  and the field keeps only the links written in it
  (a ``check_linked_values`` or ``links_only`` sum whose need computes its ``links`` too
  reads such a field on any need, see :ref:`needs_processing_order`);
- a ``need.<field>`` :ref:`argument <dynamic_functions_need_arguments>` that selects what the call reads,
  while the field is computed in the same step: the call is not run,
  and its field keeps the items written in it (a link or array field) or is left empty;
- a ``needextend`` filter that names a field a ``[[…]]``, ``<<…>>`` or ``<{…}>`` computes:
  the filter sees the value from before it is computed, once for each ``needextend`` carrying it;
- a built-in function that reads a field your own function computes, before it is computed.

A field whose call is not run reads nothing, so it is on no cycle; a value computed from it reads what it holds.
The last case is found as the call runs: the built-in functions note each field they read,
and a read of a value not computed yet is reported with its cause.
Should the cause be neither your own function nor a call whose filter cannot be read,
the order itself missed the read, and the message asks you to report it.
A filter's reads are not noted (see :ref:`needs_processing_order`).

Move the read to a value that is final earlier,
or write "set X when computed Y says so" as a ``[[…]]`` on X instead of as a ``needextend``.
A ``predicates`` entry of :ref:`needs_fields` that names a computed field is not reported yet.
To silence either warning, add its type to Sphinx's ``suppress_warnings``:

.. code-block:: python

   suppress_warnings = ["needs.derive_cycle", "needs.derive_scope"]

.. _needs_variant_support:

Variant functions
=================

.. versionadded:: 1.0.2

Needs variants add support for variants handling on need options. |br|
The support for variants options introduce new ideologies on how to set values for need fields.

To implement variants options, you can set a need field to a variant definition or multiple variant definitions.
A variant definition can look like ``var_a:open`` or ``['name' in tags]:assigned``.

.. important::

   To use variants options, you must enable the feature for a need field by setting the
   :ref:`needs_fields` or :ref:`needs_links` configuration parameter's ``parse_variants`` option to ``True`` for the specific field.

A variant definition has two parts: the **rule or key** and the **value**.
For example, if we specify a variant definition as ``var_a:open``, then ``var_a`` is the key and ``open`` is the value.
On the other hand, if we specify a variant definition as ``['name' in tags]:assigned``, then ``['name' in tags]`` is the rule
and ``assigned`` is the value.

Rules for specifying variant definitions
----------------------------------------

* Variants must be wrapped in ``<<`` and ``>>`` symbols, like ``<<var_a:open>>``.
* Variants gets checked from left to right.
* When evaluating a variant definition, we use data from the current need object,
  `Sphinx-Tags <https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-t>`_,
  and :ref:`needs_variant_data` as the context for filtering.
  Sphinx tags are injected under the name ``build_tags`` as a set of strings.
* You can set a *need option* to multiple variant definitions by separating each definition with either
  the ``,`` symbol, like ``var_a:open, ['name' in tags]:assigned``.|br|
  With multiple variant definitions, we set the first matching variant as the *need option's* value.
* When you set a *need option* to multiple variant definitions, you can specify the last definition as
  a default "variant-free" option which we can use if no variant definition matches.
  Example; In this multi-variant definitions, ``[status in tags]:added, var_a:changed, unknown``,
  *unknown* will be used if none of the other variant definitions are True.
* If you prefer your variant definitions to use rules instead of keys, then you should put your filter string
  inside square brackets like this: ``['name' in tags]:assigned``.
* For multi-variant definitions, you can mix both rule and variant-named options like this:
  ``[author["test"][0:4] == 'me']:Me, var_a:Variant A, Unknown``

To implement variants options, you must configure the following in your ``conf.py`` file:

* :ref:`needs_fields` and/or :ref:`needs_links` with the ``parse_variants`` option set to ``True`` for the specific field.
* :ref:`needs_variants`

Use Cases
---------

There are various use cases for variants options support.

Use Case 1
~~~~~~~~~~

In this example, you set the :ref:`needs_variants` configuration that comprises pre-defined variants assigned to
"filter strings".
You can then use the keys in your ``needs_variants`` as references when defining variants for a *need option*.

For example, in your ``conf.py``:

.. code-block:: python

   needs_fields = {
       "status": {
           "parse_variants": True,
       },
   }

   needs_variants = {
     "var_a": "'var_a' in build_tags"  # filter_string, check for Sphinx tags
     "var_b": "assignee == 'me'"
   }

In your ``.rst`` file:

.. code-block:: rst

   .. req:: Example
      :id: VA_001
      :status: <<var_a:open, var_b:closed, unknown>>

From the above example, if a *need option* has variants defined, then we get the filter string
from the ``needs_variants`` configuration and evaluate it.
If a variant definition is true, then we set the *need option* to the value of the variant definition.

Use Case 2
~~~~~~~~~~

In this example, you can use the filter string directly in the *need option's* variant definition.

For example, in your ``.rst`` file:

.. code-block:: rst

   .. req:: Example
      :id: VA_002
      :status: <<['var_a' in tags]:open, [assignee == 'me']:closed, unknown>>

From the above example, we evaluate the filter string in our variant definition without referring to :ref:`needs_variants`.
If a variant definition is true, then we set the *need option* to the value of the variant definition.

Use Case 3
~~~~~~~~~~

In this example, you can use defined tags (via the `-t <https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-t>`_
command-line option or within conf.py, see `here <https://www.sphinx-doc.org/en/master/usage/configuration.html#conf-tags>`_)
in the *need option's* variant definition.

First of all, define your Sphinx-Tags using either the ``-t`` command-line ``sphinx-build`` option:

.. code-block:: bash

   sphinx-build -b html -t tag_a . _build

or using the special object named ``tags`` which is available in your Sphinx config file (``conf.py`` file):

.. code-block:: python

   tags.add("tag_b")   # Add "tag_b" which is set to True

In your ``.rst`` file:

.. code-block:: rst

   .. req:: Example
      :id: VA_003
      :status: <<['tag_a' in build_tags and 'tag_b' in build_tags]:open, closed>>

From the above example, if a tag is defined, the plugin can access it in the filter context when handling variants.
If a variant definition is true, then we set the *need option* to the value of the variant definition.

.. note:: Undefined tags are false and defined tags are true.

Below is an implementation of variants for need options:

.. syntax-example::

   .. req:: Variant options
      :id: VA_004
      :status: <<['variants' in tags and not collapse]:enabled, disabled>>
      :tags: variants;support
      :collapse:

      Variants for need options in action

.. _needs_variant_data_references:

Variant data references
=======================

.. versionadded:: 8.2.0

In addition to :ref:`variant functions <needs_variant_support>` (``<<...>>``),
you can inject values directly from :ref:`needs_variant_data` into a need field
using the ``<{ ... }>`` syntax.
The referenced value is looked up and substituted into the field value.

.. important::

   This feature uses the same enablement as variant functions:
   you must set the :ref:`needs_fields` or :ref:`needs_links` configuration
   parameter's ``parse_variants`` option to ``True`` for the specific field.

Rules for variant data references
---------------------------------

* References must be wrapped in ``<{`` and ``}>`` symbols, like ``<{ var.cpu }>``.
* The reference must be a dotted path rooted at the ``var`` namespace, which
  exposes the :ref:`needs_variant_data`,
  via key lookup via dot notation (``var.build.optimization``).
* Accessing a missing key, or a path that does not resolve to a leaf value will emit a warning.
* The resolved value is type-validated against the schema of the field
  (or, for array fields, against the schema of the array items).
  A warning is emitted if the type does not match.
* References can be used for scalar, string, array, and link fields.
* For string fields, a reference can be embedded within surrounding text, and the
  parts are joined with spaces.
  For non-string scalar fields, the reference must make up the entire value, so
  that the resolved value keeps its native type (e.g. an integer).

Use Cases
---------

In your ``conf.py``, enable ``parse_variants`` for the fields you want to use
references in, and define the :ref:`needs_variant_data`:

.. code-block:: python

   needs_variant_data = {
       "platform": "arm",
       "build": {"opt_level": 2},
   }

   needs_fields = {
       "arch": {
           "schema": {"type": "string"},
           "parse_variants": True,
       },
       "opt": {
           "schema": {"type": "integer"},
           "parse_variants": True,
       },
   }

In your ``.rst`` file, reference the variant data within field values:

.. code-block:: rst

   .. req:: Example
      :id: VD_001
      :arch: <{ var.platform }>
      :opt: <{ var.build.opt_level }>

In the example above, ``arch`` resolves to the string ``"arm"`` and ``opt``
resolves to the integer ``2``.

A reference can also be embedded within a larger string value:

.. code-block:: rst

   .. req:: Example
      :id: VD_002
      :arch: platform is <{ var.platform }>

Here ``arch`` resolves to ``"platform is arm"``.
