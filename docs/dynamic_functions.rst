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

