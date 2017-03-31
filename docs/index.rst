Requirements, Bugs, Test cases, ... Management inside Sphinx
============================================================

This package contains the needs Sphinx extension.

It allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via configuration (for instance to support bugs or user stories).

.. contents::

Example
-------

.. code-block:: rst

    **Some needs**
    .. req:: My first requirement
       :status: open
       :tags: requirement; test; awesome

       This is my **first** requirement!!
       .. note:: You can use any rst code inside it :)

    .. spec:: Specification of a requirement
       :id: OWN_ID_123
       :links: R_F4722

    .. impl:: Implementation for specification
       :id: impl_01
       :links: OWN_ID_123

    .. test:: Test for XY
       :status: implemented
       :tags: test; user_interface; python27
       :links: OWN_ID_123; impl_01

       This test checks the implementation of :ref:`impl_01` for spec :ref:`OWN_ID_123` inside a
       Python 2.7 environment.

    **Filter result as list**
    .. needfilter::
       :tags: test
       :show_filters:

    **Filter result as table**
    .. needfilter::
       :tags: test
       :status: implemented; open
       :show_filters:
       :layout: table

    **Filter result as diagram**
    .. needfilter::
       :layout: diagram

This will be rendered to:

----

**Some needs**

.. req:: My first requirement
   :status: open
   :tags: requirement; test; awesome

   This is my **first** requirement!!

   .. note:: You can use any rst code inside it :)

.. spec:: Specification of a requirement
   :id: OWN_ID_123
   :links: R_F4722

.. impl:: Implementation for specification
   :id: impl_01
   :links: OWN_ID_123

.. test:: Test for XY
   :status: implemented
   :tags: test; user_interface; python27
   :links: OWN_ID_123; impl_01

   This test checks the implementation of :ref:`impl_01` for spec :ref:`OWN_ID_123` inside a
   Python 2.7 environment.

**Filter result as list**

.. needfilter::
   :tags: test
   :show_filters:

**Filter result as table**

.. needfilter::
   :tags: test
   :status: implemented; open
   :show_filters:
   :layout: table

**Filter result as diagram**

.. needfilter::
   :layout: diagram

----

What is a need?
---------------

A need is a generic object, which can become everything you want for your sphinx documentation:
A requirement, a test case, a user story, a bug, an employee, a product or anything else.

But whatever you chose it shall be and how many of them you need, each need is handled the same way.

Each need can contain:

* a **title** (required)
* an **unique id** (optional. Gets calculated based on title if not given)
* a **description**, which supports fully rst and sphinx extensions (optional)
* a **status** (optional)
* several **tags** (optional)
* several **links** to other needs (optional)

You can create filterable overviews of defined needs by using the needfilter directive::

    .. needfiler::
       :status: open;in_progress
       :tags: tests; test; test_case;
       :layout: table



Installation
============

Using pip
---------
::

    pip install sphinxcontrib-needs

Using sources
-------------
::

    git clone https://github.com/useblocks/sphinxcontrib-needs
    python setup.py install

For final activation, please add `sphinxcontrib.needs` to your project's extension list::

   extensions = ["sphinxcontrib.needs",]

For the full configruation, please read :ref:`config`.

Directives
==========

req (or any other defined need type)
------------------------------------

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
    which are configured via **needs_types**.

needfilter
----------

Example::

    .. needfilter::
       :status: open;in_progress
       :tags: user; login
       :types: req;Specification
       :show_status:
       :show_tags:
       :show_filters:
       :show_legend:
       :sort_by: id
       :layout: list

This prints a list with all found needs, which match the filters for status and tags.

For **:status:**, **:tags:** and **:types:** values are separated by "**;**". The logic is as followed::

    status = (open OR in_progress) AND tags = (user OR login) AND types = (req OR spec)

For **:types:** the type itself and the human-readable type_name can be used as filter value.

If **:show_status:** / **:show_tags:** is given, the related information will be shown after the name of the need.

To show the used filters under a list, set **:show_filters:**

**:show_legend:** is supported only by **:layout:diagram**. It adds a legend with colors to the generated diagram.

The showed list is unsorted as long as the parameter **:sort_by:** is not used.
Valid options for **:sort_by:** are **id** and **status**.

`:layout:`
~~~~~~~~~~
Three different types of layouts are available:

* list (default)
* table
* diagram

Only **list** supports each needfilter option.

**table** and **diagram** are supporting the filter options only (status, tags, types) and their design is somehow fix.

diagram
+++++++

Diagrams are available only, if the sphinx extension
`sphinxcontrib-plantuml <https://pypi.python.org/pypi/sphinxcontrib-plantuml>`_ is installed, activated and has
a working configuration.

If the configured output is **svg**, the diagram elements are linked to the location of their definition.

.. _config:

Configuration
=============

All configurations take place in your project's conf.py file.

Activation
----------

Add **sphinxcontrib.needs** to your extensions::

    extensions = ["sphinxcontrib.needs",]

Options
-------

All options starts with the prefix **needs_** for this extension.

needs_include_needs
~~~~~~~~~~~~~~~~~~~
Set this option on False, if no needs should be documented inside the generated documentation.

Default: **True**::

    needs_include_needs = False

needs_id_length
~~~~~~~~~~~~~~~
This option defines the length of an automated generated ID (the length of the prefix does not count).

Default: **5**::

    needs_id_length = 3

.. _need_types:

needs_types
~~~~~~~~~~~

The option allows the setup of own need types like bugs, user_stories and more.

By default it is set to::

    needs_types = [dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
                   dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
                   dict(directive="impl", title="Implementation", prefix="I_", color="#DF744A", style="node"),
                   dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node")
               ]

needs_types must be a list of dictionaries, where each dictionary **must** contain the following items:

* **directive**: Name of the directive. For instance "req", which can be used via `.. req::` in documents
* **title**: Title, which is used as human readable name in lists
* **prefix**: A prefix for generated IDs, to easily identify that an ID belongs to a specific type. Can also be ""
* **color**: A color as hex value. Used in diagrams and some days maybe in other representations as well.
* **style**: A plantuml node type, like node, artifact, frame, storage or database. See `plantuml documentation <http://plantuml.com/deployment-diagram>`_ for more.

needs_template
~~~~~~~~~~~~~~

The layout of needs can be fully customized by using `jinja <http://jinja.pocoo.org/>`_.

If nothing is set, the following default template is used:

.. code-block:: jinja

    .. _{{id}}:

    {% if hide == false -%}
    {{type_name}}: **{{title}}** ({{id}})

        {{content|indent(4) }}

        {% if status and not hide_status -%}
        **status**: {{status}}
        {% endif %}

        {% if tags and not hide_tags -%}
        **tags**: {{"; ".join(tags)}}
        {% endif %}

        {% if links -%}
        **links**:
        {% for link in links -%}
            :ref:`{{link}} <{{link}}>` {%if loop.index < links|length -%}; {% endif -%}
        {% endfor -%}
        {% endif -%}
    {% endif -%}

Available jinja variables are:

* type
* type_name
* type_prefix
* status
* tags
* id
* links
* title
* content
* hide
* hide_tags
* hide_status

.. warning::

   You must add a reference like `.. _{{id}}:` to the template. Otherwise linking will not work!

needs_diagram_template
~~~~~~~~~~~~~~~~~~~~~~

This option allows to control the content of diagram elements, which get automatically generated by using
`.. needfilter::` and `:layout: diagram.`

This function is based on `plantuml <http://plantuml.com>`_, so that each
`supported style <http://plantuml.com/creole>`_ can be used.

The rendered template is used inside the following plantuml syntax and must care about leaving the final string
valid:

.. code-block:: python

    'node "YOUR_TEMPLATE" as need_id [[need_link]]'

By default the following template is used:

.. code-block:: jinja

    <size:12>{{type_name}}</size>\\n**{{title}}**\\n<size:10>{{id}}</size>

