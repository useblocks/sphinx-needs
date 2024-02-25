.. _dynamic_functions:

Dynamic functions
=================

**Sphinx-Needs** provides a mechanism to set dynamic data for need-options during generation.
We do this by giving an author the possibility to set a function call to a predefined function, which calculates
the final result/value for the option.

For instance, you can use the feature if the status of a requirement depends on linked test cases and their status.
Or if you will request specific data from an external server like JIRA.

**needtable**

The options :ref:`needtable_style_row` of :ref:`needtable` also support
dynamic function execution. In this case, the function gets executed with the found need for each row.

This allows you to set row and column specific styles such as, set a row background to red, if a need-status is *failed*.


Example
-------

.. code-block:: rst

   .. req:: my test requirement
      :id: df_1
      :status: open

      This need has the id **[[copy("id")]]** and status **[[copy("status")]]**.

.. req:: my test requirement
   :id: df_1
   :status: open

   This need has id **[[copy("id")]]** and status **[[copy("status")]]**.

Built-in functions
-------------------
The following functions are available in all **Sphinx-Needs** installations.

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

You must register every dynamic function by using the :ref:`needs_functions` configuration parameter
inside your **conf.py** file:

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

Reference function
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def test(app, need, needs, *args, **kwargs):
       """
       :param app: sphinx app
       :param need: current need
       :param needs: dictionary of all needs. Key is the need id
       :return: str,int,float or list of elements of type str,int,float
       """
       # where the magic happens
       return "awesome"

You can call the defined function via:

.. code-block:: rst

   .. req:: test requirement
      :status: [[test()]]

The parameters ``app``, ``need`` and ``needs`` are set automatically. You are free to add other parameters, which
must be of type str, int, float and list.


need structure
~~~~~~~~~~~~~~

.. code-block:: text

   need = {
      'docname': str: document name,
      'lineno': int: linenumber,
      'links_back': list: list of incoming links (see restrictions),
      'target_node': node: sphinx target node for internal references,
      'type': str: short name of type,
      'type_name': str: long name of type,
      'type_prefix': str: name of type prefix,
      'type_color': str: type color,
      'type_style': str: type style,
      'status': str: status,
      'tags': list: list of tags,
      'id': str: id,
      'links': list: list of outgoing links,
      'title': str: trimmed title of need,
      'full_title': str: full title of string,
      'content': str: unparsed need content,
      'collapse': bool: true if meta data shall be collapsed,
      'hide': bool: true if complete need shall be hidden,
   }

Adding new keywords to need object will be treated as extra_option in need meta area.


Restrictions
~~~~~~~~~~~~

incoming_links
++++++++++++++
Incoming links are not available when dynamic functions gets calculated.

That's because a dynamic function can change outgoing links, so that the incoming links of the target need will
be recalculated. This is automatically done but not until all dynamic functions are resolved.

