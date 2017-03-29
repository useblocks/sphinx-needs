This package contains the needs Sphinx extension.

It allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via configuration (for instance to support bugs or user stories).

.. code-block:: rst

    .. req:: My first requirement
       :status: open
       :tags: requirement; test; awesome

       This is my **first** requirement!!
       .. note:: It's awesome :)

    .. spec:: Specification of a requirement
       :id: OWN_ID_123

    .. impl:: Implementation for specification
       :id: impl_01
       :links: OWN_ID_123

    .. test:: Test for XY
       :status: implemented
       :tags: test; user_interface; python27
       :links: OWN_ID_123; impl_01

       This test checks the implementation of :ref:`impl_01` for spec :ref:`OWN_ID_123` inside a
       Python 2.7 environment.

Each need can contain:

* a title (required)
* an unique id (optional. Gets calculated based on title if not given)
* a description, which supports fully rst and sphinx extensions (optional)
* a status (optional)
* several tags (optional)
* several links to other needs (optional)

You can create filterable overviews of defined needs by using the needlist directive::

    .. needlist::
       :status: open;in_progress
       :tags: tests; test; test_case;

.. contents::

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

conf.py
=======

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

needs_types
~~~~~~~~~~~

The option allows the setup of own need types like bugs, user_stories and more.

By default it is set to::

    needs_types = [dict(directive="req", title="Requirement", prefix="R_"),
               dict(directive="spec", title="Specification", prefix="S_"),
               dict(directive="impl", title="Implementation", prefix="I_"),
               dict(directive="test", title="Test Case", prefix="T_"),
               ]

needs_types must be a list of dictionaries, where each dictionary **must** contain the following items:

* **directive**: Name of the directive. For instance "req", which can be used via `.. req::` in documents
* **title** Title, which is used as human readable name in lists
* **prefix** A prefix for generated IDs, to easily identify that an ID belongs to a specific type. Can Also be ""

needs_template
~~~~~~~~~~~~~~

The layout of needs can be fully customized by using `jinja <http://jinja.pocoo.org/>`_.

If nothing is set, the following default template is used::

    .. _{{id}}:

    {{type_name}}: **{{title}}** ({{id}})

       {{content|indent(4) }}

       {% if status -%}
       **status**: {{status}}
       {% endif %}

       {% if tags -%}
       **tags**: {{"; ".join(tags)}}
       {% endif %}

       {% if links -%}
       **links**:
       {% for link in links -%}
           :ref:`{{link}} <{{link}}>` {%if loop.index < links|length -%}; {% endif -%}
       {% endfor -%}
       {% endif %}

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





Directives
==========

need
----

Example::

    .. need:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login

       Our users needs to get logged in via our login forms on **/login.php**.

This creates a new admonition, with a title, content, given id, a status and several tags.

All options are optional, only the title as argument must be given.

However, if no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

**Tags** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

There is an additional option **:hide:**, if this is set (no value is needed), the need will not be printed in
documentation. But it will show up in need lists!

You can also use **:hide_status:** and **:hide_tags:** ti hide the related information for this need.

needlist
--------

Example::

    .. needlist::
       :status: open;in_progress
       :tags: user; login
       :show_status:
       :show_tags:
       :show_filters:
       :sort_by: id

This prints a list with all found needs, which match the filters for status and tags.

For **:status:** and **:tags:** values are separated by "**;**". The logic is as followed::

    status = (open OR in_progress) AND tags = (user OR login)

If **:show_status:** / **:show_tags:** is given, the related information will be shown after the name of the need.

To show the used filters under a list, set **:show_filters:**

The showed list is unsorted as long as the parameter **:sort_by::** is not used.
Valid options for **:sort_by:** are **id** and **status**.

spec
----

Example::

    .. spec:: Use flask-security for user handling
       :id: SPEC001
       :status: done
       :tags: user;login;flask
       :needs: ID123; NEED567
       :show_needlist:

       We implement flask-security to get a secured way of handling user related functions like logins.

This creates a new admonition, with a title, content, given id, a status, several tags and linked need IDs.

All options are optional, only the title as argument must be given.

However, if no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

**tags** and **needs** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

You can use **:hide:**, to hide the complete output of the specification. But it will still show up inside lists
generated by the **speclist::** directive.

**:hide_tags:**, **:hide_status:** and **:hide_needs:** will hide the related information.

Use **:show_needlist:** if you like to get a table of linked needs, which includes their IDs and titles.

speclist
--------

Example::

    .. speclist::
       :status: open;in_progress
       :tags: user; login
       :needs: ID123; MyID12
       :show_status:
       :show_tags:
       :show_filters:
       :sort_by: id

This prints a list with all found specifications, which match the filters for status, tags and needs.

For **:status:**, **:tags:** and **:needs:** values are separated by "**;**". The logic is as followed::

    status = (open OR in_progress) AND tags = (user OR login) AND needs (ID123 OR MyID12)

If **:show_status:** / **:show_tags:** is given, the related information will be shown after the name of the need.

To show the used filters under a list, set **:show_filters:**

The showed list is unsorted as long as the parameter **:sort_by::** is not used.
Valid options for **:sort_by:** are **id** and **status**.