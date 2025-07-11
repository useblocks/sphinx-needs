.. _filter:

Filtering needs
===============

The filtering of needs and need parts is supported consistently across numerous directives and roles,
either by using filter options or by using a filter string.

.. _filter_options:

Filter options
--------------

The following filter options are supported by directives:

 * :ref:`needlist`
 * :ref:`needtable`
 * :ref:`needflow`
 * :ref:`needpie`
 * :ref:`needextend`

Related to the used directive and its representation, the filter options create a list of needs, which match the
filters for status, tags, types and filter.

For **:status:**, **:tags:** and **:types:** values are separated by "**;**".
**:filter:** gets evaluated.

The logic, if a need belongs to the final result list, is as followed::

    status = (open OR in_progress) AND tags = (user OR login) AND types = (req OR spec) AND eval(filter) is True


.. _option_status:

status
~~~~~~
Use the **status** option to filter needs by their status.

You can easily filter for multiple statuses by separating them by ";". Example: *open; in progress; reopen*.

.. dropdown:: Show example

   .. need-example::

      .. needlist::
         :status: open
         :show_status:

.. _option_tags:

tags
~~~~

**tags** allows to filter needs by one or multiple tags.

To search for multiple tags, simply separate them by using ";".

.. dropdown:: Show example

   .. need-example::

      .. needlist::
         :tags: main_example
         :show_tags:

.. _option_types:

types
~~~~~
For **:types:** the type itself or the human-readable type-title can be used as filter value.

.. dropdown:: Show example

   .. need-example::

      .. needtable::
         :types: test

.. _option_sort_by:

sort_by
~~~~~~~
Sorts the result list. Allowed values are ``status`` or any alphanumerical property.

.. dropdown:: Show example

   .. need-example::

      .. needtable::
         :sort_by: id
         :status: open

.. _option_filter:

filter
~~~~~~

The filter option allows the definition of a complex query string, which gets evaluated via eval() in Python.
Please see :ref:`filter_string` for more details.

.. _filter_string:

Filter string
-------------

The usage of a filter string is supported/required by:

* :ref:`need_count`
* :ref:`needlist`
* :ref:`needtable`
* :ref:`needflow`
* :ref:`needpie`
* :ref:`needbar`
* :ref:`needuml` / :ref:`needarch`


The filter string must be a valid Python expression:

.. need-example::

   :need_count:`type=='spec' and status != 'open'`

A filter string gets evaluated on needs and need_parts!
A need_part inherits all options from its parent need, if the need_part has no own content for this option.
E.g. the need_part *content* is kept, but the *status* attribute is taken from its parent need.

.. note::

   The following attributes are kept inside a need_part: id, title, links_back

This allows to perform searches for need_parts, where search options are based on parent attributes.

The following filter will find all need_parts, which are part of a need, which has a tag called *important*.

.. need-example::

   :need_count:`is_part and 'car' in tags`

Inside a filter string all the fields of :py:class:`.NeedsInfoType` can be used, including.

Additional variables for :ref:`need_part`:

* **id_parent** as Python string, which contains the id of the parent need. (compare like ``id_parent == "ABC_01"``)
* **id_complete** as Python string. Contains the concatenated ids of parent need and need_part.
  (compare like ``id_complete != 'ABC_01.03'``)

.. note:: If extra options were specified using :ref:`needs_extra_options` then
          those will be available for use in filter expressions as well.

Finally, the following are available:

* :ref:`re_search`, as Python function for performing searches with a regular expression
* **needs** as :class:`.NeedsAndPartsListView` object, which contains all needs and need_parts.

If your expression is valid and it's True, the related need is added to the filter result list.
If it is invalid or returns False, the related need is not taken into account for the current filter.

.. dropdown:: Show example

   .. need-example:: ``filter`` option

      needs:

      .. req:: Requirement A
         :tags: A; filter_example
         :status: open
         :hide:

      .. req:: Requirement B
         :tags: B; filter_example
         :status: closed
         :hide:

      .. spec:: Specification A
         :tags: A; filter_example
         :status: closed
         :hide:

      .. spec:: Specification B
         :tags: B; filter_example
         :status: open
         :hide:

      .. test:: Test 1
         :tags: filter_example
         :hide:

      .. needlist::
         :filter: "filter_example" in tags and (("B" in tags or ("spec" == type and "closed" == status)) or "test" == type)

.. _filter_current_page:

Filtering for needs on the current page
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 5.0.0

Additionally, to common :ref:`filter_string` variables,
the ``c.this_doc()`` function is for most directives,
to filter for needs only in the same document as the directive.

.. need-example::

   .. needtable::
      :filter: c.this_doc()
      :style: datatables

.. _re_search:

search
~~~~~~

search(pattern, variable) is based on
`Pythons re.search() function <https://docs.python.org/3/library/re.html#re.search>`_

The first parameter must be a regular expression pattern.
The second parameter should be one of the above variables(status, id, content, ..)

.. dropdown:: Show example

   This example uses a regular expressions to find all needs with an e-mail address in title.

   .. need-example::

      .. req:: Set admin e-mail to admin@mycompany.com

      .. needlist::
         :filter: search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", title)

.. _filter_string_performance:

Filter string performance
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 4.0.0

The filter string is evaluated by default for each need and need part
and, therefore, can be become a performance bottleneck for projects with large numbers of needs.

To improve performance, certain common patterns are identified and optimized by the filter engine, and so using such patterns is recommended:

- ``is_external`` / ``is_external == True`` / ``is_external == False``
- ``id == 'value'`` / ``id == "value"`` / ``'value' == id`` / ``"value" == id``
- ``id in ['value1', 'value2', ...]`` / ``id in ("value1", "value2", ...)``
- ``type == 'value'`` / ``type == "value"`` / ``'value' == type`` / ``"value" == type``
- ``type in ['value1', 'value2', ...]`` / ``type in ("value1", "value2", ...)``
- ``status == 'value'`` / ``status == "value"`` / ``'value' == status`` / ``"value" == status``
- ``status in ['value1', 'value2', ...]`` / ``status in ("value1", "value2", ...)``
- ``'value' in tags`` / ``"value" in tags``

Also filters containing ``and`` will be split into multiple filters and evaluated separately for the above patterns.
For example, ``type == 'spec' and other == 'value'`` will first be filtered performantly by ``type == 'spec'`` and then the remaining needs will be filtered by ``other == 'value'``.

To guard against long running filters, the :ref:`needs_filter_max_time` configuration option can be used to set a maximum time limit for filter evaluation.
Also see :ref:`needs_uml_process_max_time`, to guard against long running ``needuml`` / ``needarch`` processes containing :ref:`filters <needuml_jinja_filter>`.

To debug which filters are being used across your project and their run times, you can enable the :ref:`needs_debug_filters` configuration option.

.. _export_id:
.. deprecated:: 4.0.0

   The directive option ``export_id`` was previously used to export filter information in the ``needs.json`` file.
   This is deprecated and will be removed in a future version.
   Instead use the above :ref:`needs_debug_filters` configuration option.

.. _filter_code:

Filter code
-----------

.. versionadded:: 0.5.3

The content of a :ref:`needlist`, :ref:`needtable` or :ref:`needflow` can be used to define own filters
with the help of Python.

The used code must define a variable ``results``, which must be a list and contains the filtered needs.

The code also has access to a variable called ``needs``, which is a :class:`.NeedsAndPartsListView` instance.

.. need-example::

   .. needtable::
      :columns: id, title, type, links, links_back
      :style: table

      # Collect all requirements and specs,
      # which are linked to each other.

      results = []
      
      for need in needs.filter_types(["req"]):
         for links_id in need['links']:
            linked_need = needs.get_need(links_id)
            if linked_need and linked_need['type'] == 'spec':
               results.append(need)
               results.append(linked_need)

This mechanism can also be a good alternative for complex filter strings to save performance.
For example if a filter string is using list comprehensions to get access to linked needs.

If ``filter code`` is used, all other filter related options (like ``status`` or ``filters``) are ignored.

.. warning::

   This feature executes every given Python code.
   So be sure to trust the input/writers.


.. _filter_func:

Filter function
---------------

.. versionadded:: 0.7.3

Nearly same behavior as :ref:`filter_code`, but the code gets read from an external python file and a function must be
referenced.

:option name: filter-func
:default: None

Usage inside a rst file:

.. code-block:: rst

    .. needtable:: Filter function example
       :filter-func: filter_file.own_filter_code

The code of the referenced file ``filter_file.py`` with function ``own_filter_code``:

.. code-block:: python

   def own_filter_code(needs, results, **kwargs):
       for need in needs:
           if need["type"] == "test":
               results.append(need)

The function gets executed by **Sphinx-Needs** and it must provide two keyword arguments: ``needs`` and ``results``.

Also the given package/module must be importable by the used Python environment.
So it must be part of the Python Path variable. To update this, add
``sys.path.insert(0, os.path.abspath("folder/to/filter_files"))`` to your **conf.py** file.

Arguments
~~~~~~~~~
.. versionadded:: 0.7.6

Filter function are supporting arguments: ``filter_file.own_filter_code(value_1,value_2)``.

Please note, that the part between ``(...)`` is just a comma separated list and each element will be given as string
to the function.

The functions get the values as part of ``**kwargs`` with the name is ``arg<pos>``, starting from ``1``.

Example:

.. code-block:: rst

    .. needtable:: Filter function example
       :filter-func: filter_file.own_filter_code(1,2.5,open)


.. code-block::

   def own_filter_code(needs, results, **kwargs):
       for need in needs:
           if int(need["price"]) > int(kwargs["arg1"]) or need["status"] == kwargs["arg3"]:
               results.append(need)

The function developer is responsible to perform any needed typecast.

Needpie
~~~~~~~
:ref:`needpie` also supports filter-code.
But instead of needs, a list of resulting numbers must be returned.

Example:

.. code-block:: rst

   .. needpie:: Filter code func pie
      :labels: new,done
      :filter-func: filter_code_func.my_pie_filter_code_args(new,done)


.. code-block:: python

   def my_pie_filter_code_args(needs, results, **kwargs):
       cnt_x = 0
       cnt_y = 0
       for need in needs:
           if need["status"] == kwargs['arg1']:
               cnt_x += 1
           if need["status"] == kwargs['arg2']:
               cnt_y += 1

      results.append(cnt_x)
      results.append(cnt_y)

Filter matches nothing
----------------------

Depending on the directive used a filter that matches no needs may add text to inform that no needs are found.

The default text "No needs passed the filter".

If this is not intended, add the option

.. _option_filter_warning:

filter_warning
~~~~~~~~~~~~~~

Add specific text with this option or add no text to display nothing. The default text will not be shown.

The specified output could be styled with the css class ``needs_filter_warning``

More Examples
-------------

.. dropdown:: Setup

   .. need-example::

      .. req:: My first requirement
         :status: open
         :tags: requirement; test; awesome

         This is my **first** requirement!!

         .. note:: You can use any rst code inside it :)

      .. spec:: Specification of a requirement
         :id: OWN_ID_123
         :links: R_F4722

         Outgoing links of this spec: :need_outgoing:`OWN_ID_123`.

      .. impl:: Implementation for specification
         :id: IMPL_01
         :links: OWN_ID_123

         Incoming links of this spec: :need_incoming:`IMPL_01`.

      .. test:: Test for XY
         :status: implemented
         :tags: test; user_interface; python27
         :links: OWN_ID_123; IMPL_01

         This test checks :need:`IMPL_01` for :need:`OWN_ID_123` inside a
         Python 2.7 environment.


.. need-example:: Filter result as table

   .. needtable::
      :tags: test
      :status: implemented; open

.. need-example:: Filter result as diagram

   .. needflow::
      :filter: "More Examples" == section_name
