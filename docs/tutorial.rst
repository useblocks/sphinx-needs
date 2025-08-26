.. _tutorial:

Tutorial
========

In this tutorial, we will demonstrate the use of sphinx-needs to build up a simplified engineering plan for a car.
We will create need items, link them together, visualize the relationships between them, and generate traceability reports.

.. needflow:: Engineering plan to develop a car
    :alt: Engineering plan to develop a car
    :root_id: T_CAR
    :config: tutorial
    :show_link_names:
    :border_color:
        [status == 'open']:FF0000, 
        [status == 'in progress']:0000FF, 
        [status == 'closed']:00FF00

.. admonition:: Prerequisites

    This tutorial assumes that you have already :ref:`installed sphinx-needs <installation>`,
    and that you have a basic understanding of how to use :external+sphinx:doc:`Sphinx <index>` and :external+sphinx:ref:`reStructuredText <rst-primer>`.

Need Lifecycle
--------------

Within a sphinx build, a primary role of sphinx-needs is to manage the lifecycle of need items:

1. **Collect**: During the read phase, need items are collected from the source files and configured external sources.
2. **Resolve**: After the read phase, the need items are post-processed to resolve dynamic fields and links, etc, then frozen.
3. **Analyse**: During the write phase, various directives/roles are available to reference, query, and output analysis of the needs.
4. **Render**: During the write phase, the need items are rendered into the output format, such as HTML or PDF.
5. **Validate**: During the final phase, the need items can be validated against configured checks.

Creating need items
-------------------

The first core component of sphinx-needs are need items,
which you can think of as nodes in a graph.

Each item must have at least:

- a type (which corresponds to a directive),
- a unique identifier (that can be auto-generated)
- a title, and
- a description.

A need item is a generic object which can become anything you you require for your project: a requirement, a test case, a user story, a bug, an employee, a product...

sphinx-needs comes with some default types: ``req``, ``spec``, ``impl``, and ``test``, which can be used as directives:

.. need-example:: A basic need item

    .. req:: Basic need example
        :id: basic_example

        A basic example of a need item.

For our car though, we want to use custom types, to describe aspects of the process.
This can be created in the ``conf.py`` file, using the :ref:`needs_types` configuration option:

.. code-block:: python

    needs_types = [
        {
            "directive": "tutorial-project",
            "title": "Project",
            "prefix": "P_",  # prefix for auto-generated IDs
            "style": "rectangle", # style for the type in diagrams
            "color": "#BFD8D2", # color for the type in diagrams
        }
    ]

There are also some optional directive fields 
that can be used to add additional data to the item or further style its representation:

.. need-example:: A custom need item

    .. tutorial-project:: Our new car
        :id: T_CAR
        :tags: tutorial
        :layout: clean_l
        :image: _images/car.png
        :collapse: true

        Presenting the “TeenTrek,” an autonomous driving car tailored for teenagers without a driving license.
        Equipped with advanced AI navigation and safety protocols, it ensures effortless and secure transportation. 
        The interior boasts entertainment systems, study areas, and social hubs, catering to teen preferences. 
        The TeenTrek fosters independence while prioritizing safety and convenience for young passengers.

.. seealso::
    
    For full options see the reference sections for :ref:`needs_types configuration <needs_types>` and :ref:`need items directive <need>`.

    To add additional fields to the directive,
    see :ref:`needs_extra_options`,
    and to set default values see :ref:`needs_global_options`.

Enforcing valid need items
..........................

To enforce the usage of specifically defined need ID formats, you can configure :ref:`needs_id_required` and :ref:`needs_id_regex`.

To enforce specific values for need item options,
you can configure :ref:`needs_statuses`, :ref:`needs_tags` or :ref:`needs_warnings` to check for disallowed values.

These will emit warnings when building the documentation if the values are not as expected.


Referring to a need item
------------------------

We can refer to the needs we create in the text using the :ref:`need role <role_need>`.
By default this will display the title and ID of the need item, but we can also different fields to display,
by using an explicit title and using ``[[field]]`` syntax:


.. need-example:: Referring to a need item

    The project is described in more detail in :need:`T_CAR`.

    The project is described in more detail in :need:`[[title]] <T_CAR>`.

We shall also see later how to create tables and other visualizations of multiple items.

Linking need items
------------------

Now that we know how to create individual need items,
the next thing we may want to do is to link them together.

We can define custom link types in the ``conf.py`` file, using the :ref:`needs_extra_links` configuration option:

.. code-block:: python

    needs_extra_links = [
      {
        "option": "tutorial_required_by",
        "incoming": "requires",  # text to describe incoming links
        "outgoing": "required by",  # text to describe outgoing links
        "style": "#00AA00",  # color for the link in diagrams
      },
    ]

We can now uses these links when specifying need items, notice how "back links" are automatically generated when displaying the item:

.. need-example:: Need items with links

   .. tutorial-req:: Safety Features
      :id: T_SAFE
      :tags: tutorial
      :tutorial_required_by: T_CAR

      The car must include advanced safety features such as automatic braking, collision avoidance systems, and adaptive cruise control to ensure the safety of teenage drivers.

   .. tutorial-req:: Connectivity and Entertainment
      :id: T_CONNECT
      :tags: tutorial
      :tutorial_required_by: T_CAR
      
      The car should be equipped with built-in Wi-Fi, Bluetooth connectivity, and compatibility with smartphone integration systems to enable seamless communication and entertainment for teenagers on the go.

Lets also add some more need items to our plan:

.. dropdown:: Add Specification items

   .. need-example:: More need items with links

      .. tutorial-spec:: Implement RADAR system
         :id: T_RADAR
         :tags: tutorial
         :tutorial_specifies: T_SAFE

         The RADAR sensor software for the car must accurately detect and track surrounding objects 
         within a specified range. It should employ signal processing algorithms to filter out noise 
         nd interference, ensuring reliable object detection in various weather and road conditions. 
         The software should integrate seamlessly with the car's control system, providing real-time 
         data on detected objects to enable collision avoidance and adaptive cruise control functionalities. 
         Additionally, it should adhere to industry standards for safety and reliability, with robust 
         error handling mechanisms in place.


      .. tutorial-spec:: Implement distant detection
         :id: T_DIST
         :tags: tutorial
         :tutorial_specifies: T_SAFE

         Software Specification for Distance Detection Algorithm.

.. seealso::
    
    For full options see the reference sections for :ref:`need_extra_links configuration <need_extra_links>` and :ref:`need items directive <need>`.

Importing need items
--------------------

Need items can also be imported from external sources, using the :ref:`needimport` directive,
or generated from external services, using the :ref:`needservice` directive.

Lets import some test cases, we add an additional tag to each, to make them easier to select later on:

.. need-example:: Importing need items

    .. needimport:: _static/tutorial_needs.json
        :tags: tutorial,tutorial_tests
        :collapse: true

.. seealso::
    
    For full options see the reference sections for :ref:`needimport directive <needimport>` and :ref:`needservice directive <needservice>`.

Modifying need items
--------------------

In the section above, we imported some test case needs, but they are currently not linked to any other need items.

We can extend the imported need items using the :ref:`needextend directive <needextend>`,
to add additional fields to them, such as links.

The ``needextend`` directive expects a :ref:`filter <filter>` argument, which is used to select the need items to extend.
Here we filter by the tag we set on the imported items above:

.. need-example:: Extending need items

    .. needextend:: "tutorial_tests" in tags
        :+tutorial_tests: T_RADAR
        :status: open

    .. needextend:: T_001
        :status: closed

    .. needextend:: T_002
        :status: in progress

.. note:: 

    The ``needextend`` does not have any visible output,
    but it you look at the items, they will now have the additional link and status fields.

.. seealso:: 
    
    For full options see the reference sections for :ref:`needextend directive <needextend>`.

Summarising needs
-----------------

Now we have learnt about how to introduce need items into our project,
it is natural to want to be able to summarise all or a sub-set of needs.

There are three directives that can be used to do this, with different output formats:

- :ref:`needlist <needlist>` - to display a list of need items
- :ref:`needtable <needtable>` - to display a table of need items
- :ref:`needflow <needflow>` - to display a flow diagram of need items

All of these use a common :ref:`filter logic <filter>`, to select a sub-set of need items to display,
either by simple options, or by using a more complex expression.

In the following example we will display a list of all need items with the tag "tutorial",
sorted by ID, and showing the status of each item:

.. need-example:: Simple list

    .. needlist::
        :tags: tutorial
        :sort_by: id
        :show_status:

Similarly, we can display the same items in a table format:

.. need-example:: Simple table

    .. needtable::
        :tags: tutorial
        :sort: id
        :columns: id,type,title,status
        :style: table

There are currently two styles for the table; a simple HTML ``table``, or the default ``datatables`` style to add dynamic pagination, filtering and sorting,
using the `DataTables <https://datatables.net/>`__ JS package:

.. need-example:: Table with dynamic features

    .. needtable::
        :tags: tutorial
        :sort: id
        :columns: id,type,title,status
        :style: datatable

Finally, we can display a :ref:`flow diagram <needflow>` of the need items, to also show the relationships between them:
 
.. need-example:: Flow diagram

    .. needflow:: Engineering plan to develop a car
        :alt: Engineering plan to develop a car
        :root_id: T_CAR
        :config: lefttoright,tutorial
        :show_link_names:
        :border_color: 
            [status == 'open']:FF0000, 
            [status == 'in progress']:0000FF, 
            [status == 'closed']:00FF00

.. dropdown:: Aternative use of Graphviz engine

    You can also use the Graphviz engine to render the flow diagram, by setting the ``engine`` option to ``graphviz``:

    .. need-example:: Flow diagram with Graphviz

        .. needflow:: Engineering plan to develop a car
            :engine: graphviz
            :alt: Engineering plan to develop a car
            :root_id: T_CAR
            :config: lefttoright,tutorial
            :show_link_names:
            :border_color: 
                [status == 'open']:FF0000, 
                [status == 'in progress']:0000FF, 
                [status == 'closed']:00FF00

Analysing Metrics
-----------------

As well as summarising needs, sphinx-needs provides some built-in roles and directives to analyse metrics of need items, such as the number of items in a certain status:

- :ref:`need_count role <need_count>` - to display the count of need items
- :ref:`needpie directive <needpie>` - to display a pie chart of need items
- :ref:`needbar directive <needbar>` - to display a bar chart of need items

In the following examples we will display metrics of the test cases we imported earlier, grouped by status:

.. need-example:: Count of need items

    - Open: :need_count:`'tutorial_tests' in tags and status == 'open'`
    - In Progress: :need_count:`'tutorial_tests' in tags and status == 'in progress'`
    - Closed: :need_count:`'tutorial_tests' in tags and status == 'closed'`

.. need-example:: Pie chart of metric

   .. needpie:: Test Status
      :labels: Open, In progress, Closed
      :legend:

      'tutorial_tests' in tags and status == 'open'
      'tutorial_tests' in tags and status == 'in progress'
      'tutorial_tests' in tags and status == 'closed'

.. need-example:: Bar chart of metric

   .. needbar:: Test Status
      :horizontal:
      :xlabels: FROM_DATA
      :ylabels: FROM_DATA
      :legend:

      Status,      Tests
      Open,        'tutorial_tests' in tags and status == 'open'
      In Progress, 'tutorial_tests' in tags and status == 'in progress'
      Closed,      'tutorial_tests' in tags and status == 'closed'

Next Steps
----------

Now that you have seen how to create need items, link them together, and analyse metrics,
you can explore the full range of options available in sphinx-needs by reading the rest of the documentation.

For a more complex project example, check out the `sphinx-needs-demo <https://sphinx-needs-demo.readthedocs.io>`_ site.

Also, see :ref:`other extensions <other-extensions>` offered by `useblocks <https://useblocks.com>`_ which integrate with sphinx-needs to provide additional functionality.

.. todo::

    - Tracking progress
        - mainly to introduce needgantt

    - finally link to the new "core" useblocks site and
      the "enterprise tools" like ubtrace etc
