Directives
==========

need/ req (or any other defined need type)
------------------------------------------

Example::

    .. req:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login
       :links: ID444; ID_555

       Our users needs to get logged in via our login forms on **/login.php**.

This creates a new requirement, with a title, content, given id, a status and several tags.

All options are optional, only the title as argument must be given.

However, if no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

**Tags** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

**links** can be used to create a link to one or several other needs, no matter what kind of type they are.
All you need is the related ID.

There is an additional option **:hide:**, if this is set (no value is needed), the need will not be printed in
documentation. But it will show up in need filters!

You can also use **:hide_status:** and **:hide_tags:** to hide the related information for this need.

.. note::

    By default the above example works also with `.. spec::`, `.. impl::`, `.. test::` and all other need types,
    which are configured via :ref:`need_types`.

.. _needfilter:

needfilter
----------

Example::

    .. needfilter::
       :status: open;in_progress
       :tags: user; login
       :types: req;Specification
       :filter: "my_tag" in tags and ("another_tag" in tags or "closed" in status)
       :show_status:
       :show_tags:
       :show_filters:
       :show_legend:
       :sort_by: id
       :layout: list

This prints a list with all found needs, which match the filters for status, tags and types.

For **:status:**, **:tags:** and **:types:** values are separated by "**;**".
**:filter:** gets evaluated.

The logic, if a need belongs to the needfilter result list, is as followed::

    status = (open OR in_progress) AND tags = (user OR login) AND types = (req OR spec) AND eval(filter) is True

For **:types:** the type itself and the human-readable type_title can be used as filter value.

If **:show_status:** / **:show_tags:** is given, the related information will be shown after the name of the need.

To show the used filters under a list, set **:show_filters:**

**:show_legend:** is supported only by **:layout:diagram**. It adds a legend with colors to the generated diagram.

The showed list is unsorted as long as the parameter **:sort_by:** is not used.
Valid options for **:sort_by:** are **id** and **status**.

.. _filter:

`:filter:`
~~~~~~~~~~

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
++++++

search(pattern, variable) is based on
`Pythons re.search() function <https://docs.python.org/3/library/re.html#re.search>`_

The first parameter must be a regular expression pattern.
The second parameter should be on of the above variables(status, id, content, ..)

Example::

    .. Returns True, if a email address is inside the need content.

    .. needfilter::
       :filter: search("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", content)

`:layout:`
~~~~~~~~~~
Three different types of layouts are available:

* list (default)
* table
* diagram

Only **list** supports each needfilter option.

**table** and **diagram** are supporting the filter options only (status, tags, types, filter) and their design is somehow fix.

diagram
+++++++

Diagrams are available only, if the sphinx extension
`sphinxcontrib-plantuml <https://pypi.python.org/pypi/sphinxcontrib-plantuml>`_ is installed, activated and has
a working configuration.

If the configured output is **svg**, the diagram elements are linked to the location of their definition.

.. _needimport:

needimport
----------
.. versionadded:: 0.1.33

Allows the import of needs from a json file.

The builder :ref:`needs_builder` should be used to generate a valid file.

The directive **.. needimport::** can be used in all rst-documents. Simply write::

   .. needimport:: needs.json
      :id_prefix: imp_
      :version: 1.0
      :tags: imported;external
      :hide:
      :filter: "test" in tags

The directive needs an absolute or relative path as argument.
If the path is relative, an absolute path gets calculated with the folder of the **conf.py** as basedir.

**:id_prefix:** can be used to add a prefix in front of all imported need ids.
This may be useful to avoid duplicated ids.

.. note:: when using **:id_prefix:** also all ids used for links and inside descriptions get replaced,
          if the id belongs to an imported need.

**:version:** allows to specify a specific version for the import. This version must exist inside the imported file.
If no version is given, the **current_version** attribute from the json file is used.
In most cases this should be the latest available version.

**:tags:** are attached to the already existing ones of imported needs. This may be useful to mark easily imported
needs and to create specialised filters for them.

**:filter** imports needs only, which pass the filter criteria. Please read the :ref:`filter` documentation of the
**needfilter** directive for more.

**:hide:** can be used to set the **:hide:** tag for all imported needs. So they do not show up but are available
in :ref:`needfilter`.

.. warning:: Imported needs may use different need types as the current project.
             The sphinx project owner is responsible for a correct configuration for internal and external needs.
             There is no automatic typ transformation during an import.


