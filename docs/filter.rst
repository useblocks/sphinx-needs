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


   .. needlist::
         :status: open

.. _option_tags:

tags
----

.. _option_types:

types
-----
For **:types:** the type itself and the human-readable type_title can be used as filter value.


.. _option_filter:

filter
------

The filter option allows the definition of a complex query string, which gets evaluated via eval() in Python.
So each valid Python expression is supported. The following variables/functions are available:

* tags, as Python list (compare like ``"B" in tags``)
* type, as Python string (compare like ``"story" == type``)
* status, as Python string (compare like ``"opened" != status``)
* id, as Python string (compare like ``"MY_ID_" in id``)
* title, as Python string (compare like ``len(title.split(" ")) > 5``)
* links, as Python list (compare like ``"ID_123" not in links``)
* content, as Python string (compare like ``len(content) == 0``)
* :ref:`re_search`, as Python function for performing searches with a regular expression

If your expression is valid and it's True, the related need is added to the filter result list.
If it is invalid or returns False, the related need is not taken into account for the current filter.

**Examples**::

    .. req:: Requirement A
       :tags: A;
       :status: open

    .. req:: Requirement B
       :tags: B;
       :status: closed

    .. spec:: Specification A
       :tags: A;
       :status: closed

    .. spec:: Specification B
       :tags: B;
       :status: open

    .. test:: Test 1

    .. needfilter::
       :filter: ("B" in tags or ("spec" == type and "closed" == status)) or "test" == type


This will have the following result:

.. req:: Requirement A
   :tags: A; filter
   :status: open
   :hide:

.. req:: Requirement B
   :tags: B; filter
   :status: closed
   :hide:

.. spec:: Specification A
   :tags: A; filter
   :status: closed
   :hide:

.. spec:: Specification B
   :tags: B; filter
   :status: open
   :hide:

.. test:: Test 1
   :tags: awesome; filter
   :hide:

.. needfilter::
       :filter: ("B" in tags or ("spec" == type and "closed" == status)) or ("test" == type and "awesome" in tags)

.. _re_search:

search
~~~~~~

search(pattern, variable) is based on
`Pythons re.search() function <https://docs.python.org/3/library/re.html#re.search>`_

The first parameter must be a regular expression pattern.
The second parameter should be on of the above variables(status, id, content, ..)

Example::

    .. Returns True, if a email address is inside the need content.

    .. needfilter::
       :filter: search("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", content)
