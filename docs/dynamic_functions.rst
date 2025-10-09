========================
Delayed field evaluation
========================

Sphinx-needs offers the possibility to delay the evaluation of certain need field values until all needs have been collected, and thus can be based on this data.

There are two syntaxes provided to achieve this:

- Using double square brackets ``[[...]]`` to encapsulate a dynamic function call.
- Using double angled brackets ``<<...>>`` to encapsulate a variant function call.

.. _dynamic_functions:

Dynamic functions
=================

Dynamic functions provide a mechanism to specify need fields or content that are calculated at build time, based on other fields or needs.

We do this by giving an author the possibility to set a function call to a predefined function, which calculates the final value **after all needs have been collected**.

For instance, you can use the feature if the status of a requirement depends on linked test cases and their status.
Or if you will request specific data from an external server like JIRA.

To refer to a dynamic function, you can use the following syntax:

- In a need directive option, wrap the function call in double square brackets: ``function_name(arg)``
- In a need content, use the :ref:`ndf` role: ``:ndf:`function_name(arg)```

.. need-example:: Dynamic function example

   .. req:: my test requirement
      :id: df_1
      :status: open
      :tags: test;[[copy("status")]]

      This need has id :ndf:`copy("id")` and status :ndf:`copy("status")`.

Dynamic functions can be used for the following directive options:

- ``status``
- ``tags``
- ``style``
- ``layout``
- ``constraints``
- :ref:`needs_extra_options`
- :ref:`needs_extra_links`
- :ref:`needs_global_options`

.. deprecated:: 3.1.0

   The :ref:`ndf` role replaces the use of the ``[[...]]`` syntax in need content.

Built-in functions
-------------------

The following functions are available by default.

.. note::

   The parameters ``app``, ``need`` and ``needs`` of the following functions are set automatically.

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

Restrictions
~~~~~~~~~~~~

incoming_links
++++++++++++++
Incoming links are not available when dynamic functions gets calculated.

That's because a dynamic function can change outgoing links, so that the incoming links of the target need will
be recalculated. This is automatically done but not until all dynamic functions are resolved.

.. _needs_variant_support:

Variant functions
=================

.. versionadded:: 1.0.2

Needs variants add support for variants handling on need options. |br|
The support for variants options introduce new ideologies on how to set values for *need options*.

To implement variants options, you can set a *need option* to a variant definition or multiple variant definitions.
A variant definition can look like ``var_a:open`` or ``['name' in tags]:assigned``.

A variant definition has two parts: the **rule or key** and the **value**. |br|
For example, if we specify a variant definition as ``var_a:open``, then ``var_a`` is the key and ``open`` is the value.
On the other hand, if we specify a variant definition as ``['name' in tags]:assigned``, then ``['name' in tags]`` is the rule
and ``assigned`` is the value.

Rules for specifying variant definitions
----------------------------------------

* Variants must be wrapped in ``<<`` and ``>>`` symbols, like ``<<var_a:open>>``.
* Variants gets checked from left to right.
* When evaluating a variant definition, we use data from the current need object,
  `Sphinx-Tags <https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-t>`_,
  and :ref:`needs_filter_data` as the context for filtering.
  Sphinx tags are injected under the name ``build_tags`` as a set of strings.
* You can set a *need option* to multiple variant definitions by separating each definition with either
  the ``,`` symbol, like ``var_a:open, ['name' in tags]:assigned``.|br|
  With multiple variant definitions, we set the first matching variant as the *need option's* value.
* When you set a *need option* to multiple variant definitions, you can specify the last definition as
  a default "variant-free" option which we can use if no variant definition matches. |br|
  Example; In this multi-variant definitions, ``[status in tags]:added, var_a:changed, unknown``,
  *unknown* will be used if none of the other variant definitions are True.
* If you prefer your variant definitions to use rules instead of keys, then you should put your filter string
  inside square brackets like this: ``['name' in tags]:assigned``.
* For multi-variant definitions, you can mix both rule and variant-named options like this:
  ``[author["test"][0:4] == 'me']:Me, var_a:Variant A, Unknown``

To implement variants options, you must configure the following in your ``conf.py`` file:

* :ref:`needs_variants`
* :ref:`needs_variant_options`

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

.. need-example::

   .. req:: Variant options
      :id: VA_004
      :status: <<['variants' in tags and not collapse]:enabled, disabled>>
      :tags: variants;support
      :collapse:

      Variants for need options in action
