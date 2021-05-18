.. _dynamic_functions:

Dynamic functions
=================

Sphinx-Needs provides a mechanism to set dynamic data for need-options during generation.
This is realised by giving an author the possibility to set a function call to a predefined function, which calculates
the final result/value for the option.

This can be useful, if for instance the status of a requirement depends on linked test cases and their status.
Or if specific data shall be requested from an external server like JIRA.

**needtable**

The options :ref:`needtable_style_row` of :ref:`needtable` are also supporting
dynamic function execution. In this case the function will get executed with the found need for each row.

This allows to set row and column specific styles and e.g. set a row background to red, if a need-status is *failed*.

.. contents::
   :local:

Example
-------

.. code-block:: jinja

   .. req:: my test requirement
      :id: df_1
      :status: open

      This need has the id **[[copy("id")]]** and status **[[copy("status")]]**.

.. req:: my test requirement
   :id: df_1
   :status: open

   This need has id **[[copy("id")]]** and status **[[copy("status")]]**.

Built-in  functions
-------------------
The following functions are available in all sphinx-needs installations.

.. contents::
   :local:


.. note::

   The parameters ``app``, ``need`` and ``needs`` of the following functions are set automatically.

test
~~~~
.. autofunction:: sphinxcontrib.needs.functions.common.test

.. _echo:

echo
~~~~
.. autofunction:: sphinxcontrib.needs.functions.common.echo

.. _copy:

copy
~~~~
.. autofunction:: sphinxcontrib.needs.functions.common.copy

.. _check_linked_values:

check_linked_values
~~~~~~~~~~~~~~~~~~~
.. autofunction:: sphinxcontrib.needs.functions.common.check_linked_values


.. _calc_sum:

calc_sum
~~~~~~~~

.. autofunction:: sphinxcontrib.needs.functions.common.calc_sum

.. _links_content:

links_from_content
~~~~~~~~~~~~~~~~~~

.. autofunction:: sphinxcontrib.needs.functions.common.links_from_content


Develop own functions
---------------------

Registration
~~~~~~~~~~~~

Every dynamic function must be registered by using configuration parameter :ref:`needs_functions`
inside your ``conf.py`` file::

   def my_own_function(app, need, needs):
       return "Awesome"

   needs_functions = [my_own_function]

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

Such a defined function can be called via:

.. code-block:: jinja

   .. req:: test requirement
      :status: [[test()]]

The parameters ``app``, ``need`` and ``needs`` are set automatically. You are free to add other parameters, which
are allowed to be of type str, int, float and list.


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
      'hide_tags': bool: if tags shall be hidden,
      'hide_status': bool: true if status shall be hidden,
   }

Adding new keywords to need object will be treated as extra_option in need meta area.


Restrictions
~~~~~~~~~~~~

incoming_links
++++++++++++++
Incoming links are not available when dynamic functions get calculated.

That's because a dynamic function can change outgoing links, so that the incoming links of the target need needs
to be recalculated. This is automatically done, but not until all dynamic functions were resolved.




