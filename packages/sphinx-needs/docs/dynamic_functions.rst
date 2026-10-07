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
Otherwise the call is not run, its field is left empty, and ``needs.derive_scope`` says so (:ref:`needs_derive_scope`).

.. versionchanged:: 9.0.0

   ``need.<field>`` arguments are accepted in field and link values, a ``needextend``'s included;
   a need that used one was not created.

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
   which is then computed like one written in the need; until it is, the field holds its empty value.
2. The ``[[…]]``, ``<<…>>`` and ``<{…}>`` of the :ref:`link fields <needs_links>` are computed,
   each after the link fields it reads, and those that call your own :ref:`functions <needs_functions>` last.
3. The back links are built from the links of steps 1 and 2, each back link list in need-id order.
4. Every other ``[[…]]``, ``<<…>>`` and ``<{…}>`` is computed, each after every value it reads
   (a field of its own need or of another need, a field of a linked need, a back link),
   and those that call your own functions last.
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
``copy("x", filter=…)``                ``x`` of the match with the lowest id
``calc_sum("x")``                      ``x`` of every need, its own included
``calc_sum("x", filter=…)``            ``x`` of every need the filter keeps
``calc_sum("x", links_only=True)``     its own ``links``, and ``x`` (and the filter's fields) of each linked need
``check_linked_values(…, "x", …)``     its own ``links``, and ``x`` (and the filter's fields) of every linked need
``links_from_content()``               the need's content
``<<[cond]:a, b>>``                    the fields of its own need that any of its conditions names, evaluated or not
=====================================  ==============================================================================

A ``filter`` that names only values nothing computes is evaluated before step 4, so its matches are known;
one that names a computed field makes every need a candidate, and the call is computed after
that field and ``x`` on every need.
The needs of a set are read in need-id order, comparing ids as strings (``REQ_10`` comes before ``REQ_9``):
the candidates of a ``calc_sum`` or a ``filter``, and a back link list.
A link list is read in the order it is written, followed by the links a ``needextend`` added;
a link written twice is read twice, so a ``calc_sum`` with ``links_only`` adds its value twice.
The link lists are sorted, and a link written twice kept once, only in step 5.

Your own functions run after every built-in function of their step, in need-id order, then by field.
They read the values the built-in functions computed; a built-in function that reads a field your own function computes
reads it before it is computed, which is reported (:ref:`needs_derive_scope`).
A function of your own in a link field, such as sphinx-test-reports' ``tr_link``, runs at the end of step 2,
so its links are in the back links of step 3.
A later release is to let a function declare what it reads, which will order it like a built-in one.
A ``filter`` that names ``needs``, or reads ``current_need`` by a key that is not written out,
cannot be ordered either: its call runs with your own functions.

.. _needs_derive_cycle:

Cycles
++++++

A value that reads itself, directly or through other computed values, cannot be computed.
Each field on such a cycle is left at its empty value (``None``, or for a field that is not nullable ``""``, ``0``, ``False`` or ``[]``)
and reported as ``needs.derive_cycle``, once at each need on the cycle, naming the needs:

.. code-block:: text

   index.rst:4: WARNING: dynamic function 'copy' for option 'summary' is on a cycle:
   'summary' on 2 needs (CYC_A, CYC_B); the field is left empty [needs.derive_cycle]

A value computed from a field on a cycle is computed from its empty value, and is not reported.
A sum over every need includes the need that holds it, so ``:hours: [[calc_sum("hours")]]`` reads its own value and is a cycle;
sum into another field, or give a ``filter`` that excludes the need.
A ``filter`` that names a computed field makes every need a candidate,
so it can make a cycle that the filter itself would have excluded; the message then names the filter.
Filter on a value that is not computed, or break the cycle.
A variant whose condition reads the field it sets, such as ``:status: <<[status == "open"]:open, closed>>``,
is a cycle too.

.. _needs_derive_scope:

Reads that cannot be ordered
++++++++++++++++++++++++++++

These reads are reported as ``needs.derive_scope``:

- a ``[[…]]`` of a link field that reads another computed field, or a back link,
  reads it before it is computed (step 2 comes before the back links and the other fields);
- a ``need.<field>`` :ref:`argument <dynamic_functions_need_arguments>` that selects what the call reads,
  while the field is computed in the same step: the call is not run, and its field is left empty;
- a ``needextend`` filter that names a field a ``[[…]]``, ``<<…>>`` or ``<{…}>`` computes:
  the filter sees the value from before it is computed, once for each ``needextend`` carrying it;
- a built-in function that reads a field your own function computes, before it is computed.

Move the read to a value that is final earlier,
or write "set X when computed Y says so" as a ``[[…]]`` on X instead of as a ``needextend``.
A ``predicates`` entry of :ref:`needs_fields` that names a computed field is not reported yet.
To silence either warning, add its type to Sphinx's ``suppress_warnings``:

.. code-block:: python

   suppress_warnings = ["needs.derive_cycle", "needs.derive_scope"]

``needs.derive_unresolved``, which an unreleased version reported for such reads, is no longer emitted,
and an entry naming it in ``suppress_warnings`` has no effect.

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
