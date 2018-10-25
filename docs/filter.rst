.. _filter:

Filtering needs
===============

These options are supported by directives:

 * :ref:`needlist`
 * :ref:`needtable`
 * :ref:`needflow`
 * :ref:`needfilter` (deprecated!)


Related to the used directive and its representation, the filter options create a list of needs, which match the filters for status, tags, types and filter.

For **:status:**, **:tags:** and **:types:** values are separated by "**;**".
**:filter:** gets evaluated.

The logic, if a need belongs to the final result list, is as followed::

    status = (open OR in_progress) AND tags = (user OR login) AND types = (req OR spec) AND eval(filter) is True


.. _option_status:

status
------
Use the **status** option to filter needs by their status.

You can easily filter for multiple statuses by separating them by ";". Example: *open; in progress; reopen*.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needlist::
         :status: open
         :show_status:

   .. needlist::
         :status: open
         :show_status:

.. _option_tags:

tags
----

**tags** allows to filter needs by one or multiple tags.

To search for multiple tags, simply separate them by using ";".

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needlist::
         :tags: main_example
         :show_tags:

   .. needlist::
         :tags: main_example
         :show_tags:


.. _option_types:

types
-----
For **:types:** the type itself or the human-readable type-title can be used as filter value.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needtable::
         :types: test

   .. needtable::
      :types: test
      :style: table


.. _option_sort_by:

sort_by
-------

Sorts the result list. Allowed values are ``id`` and ``status``

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needtable::
         :sort_by: id
         :status: open


   .. needtable::
      :sort_by: id
      :status: open
      :style: table



.. _option_filter:

filter
------

The filter option allows the definition of a complex query string, which gets evaluated via eval() in Python.
So each valid Python expression is supported. The following variables/functions are available:

* tags, as Python list (compare like ``"B" in tags``)
* type, as Python string (compare like ``"story" == type``)
* status, as Python string (compare like ``"opened" != status``)
* sections, as Python list with the hierarchy of sections with lowest-level
  section first.  (compare like ``"Section Header" in sections``)
* id, as Python string (compare like ``"MY_ID_" in id``)
* title, as Python string (compare like ``len(title.split(" ")) > 5``)
* links, as Python list (compare like ``"ID_123" not in links``)
* content, as Python string (compare like ``len(content) == 0``)
* :ref:`re_search`, as Python function for performing searches with a regular expression

.. note:: If extra options were specified using :ref:`needs_extra_options` then
          those will be available for use in filter expressions as well.

If your expression is valid and it's True, the related need is added to the filter result list.
If it is invalid or returns False, the related need is not taken into account for the current filter.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

       .. req:: Requirement A
          :tags: A; filter_example
          :status: open

       .. req:: Requirement B
          :tags: B; filter_example
          :status: closed

       .. spec:: Specification A
          :tags: A; filter_example
          :status: closed

       .. spec:: Specification B
          :tags: B; filter_example
          :status: open

       .. test:: Test 1
          :tags: filter_example

       .. needtable::
          :filter: "filter_example" in tags and ("B" in tags or ("spec" == type and "closed" == status)) or "test" == type

   This will have the following result:

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

   .. needfilter::
      :filter: "filter_example" in tags and (("B" in tags or ("spec" == type and "closed" == status)) or "test" == type)

.. _re_search:

search
~~~~~~

search(pattern, variable) is based on
`Pythons re.search() function <https://docs.python.org/3/library/re.html#re.search>`_

The first parameter must be a regular expression pattern.
The second parameter should be on of the above variables(status, id, content, ..)

.. container:: toggle

   .. container::  header

      **Show example**

   This example uses a regular expressions to find all needs with an e-mail address in title.

   .. code-block:: rst

      .. req:: Set admin e-mail to admin@mycompany.com

      .. needlist::
         :filter: search("([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", title)

   .. req:: Set admin e-mail to admin@mycompany.com

   .. needlist::
      :filter: search("([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", title)
