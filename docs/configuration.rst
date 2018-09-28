.. _config:

Configuration
=============

All configurations take place in your project's conf.py file.


.. contents::


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
                   dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node"),
                   # Kept for backwards compatibility
                   dict(directive="need", title="Need", prefix="N_", color="#9856a5", style="node")
               ]

needs_types must be a list of dictionaries, where each dictionary **must** contain the following items:

* **directive**: Name of the directive. For instance "req", which can be used via `.. req::` in documents
* **title**: Title, which is used as human readable name in lists
* **prefix**: A prefix for generated IDs, to easily identify that an ID belongs to a specific type. Can also be ""
* **color**: A color as hex value. Used in diagrams and some days maybe in other representations as well.
* **style**: A plantuml node type, like node, artifact, frame, storage or database. See `plantuml documentation <http://plantuml.com/deployment-diagram>`_ for more.


.. _needs_extra_options:

needs_extra_options
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.2

The option allows the addition of extra options that can be specified on
needs.

It can be specified as a dict inside ``conf.py`` as follows::

  from docutils.parsers.rst import directives

   needs_extra_options = {
    "introduced": directives.unchanged,
    "updated": directives.unchanged,
    "impacts": directives.unchanged
   }

And used like:

.. code-block:: rst

   .. req:: My Requirement
      :status: open
      :introduced: Yes
      :updated: 2018/03/26
      :tags: important;complex;
      :impacts: really everything

Default value = ``{'hidden': directives.unchanged}``

The ``hidden`` option is a globally available option, which is always hidden and
can be used to easily execute :ref:`dynamic_functions`.

The key of the dict represents the option/attribute name that can be associated
with the need, and the value represents the `option conversion function <http://docutils.sourceforge.net/docs/howto/rst-directives.html#option-conversion-functions>`_
to apply to the associated value.

In order to make the options appear in the rendered content you will need to
override the the default templates used (see needs_template_ and
needs_template_collapse_ for more information).

.. note:: To filter on these options in `needlist`, `needtable`, etc. you
          must use the :ref:`filter` option.


.. container:: toggle

   .. container:: header

      **Show example**

   **conf.py**

   .. code-block:: python
      :linenos:

      from docutils.parsers.rst import directives

      needs_extra_options = {
         "my_extra_option": directives.unchanged,
         "another_option": directives.unchanged,
         }

      # Lines 33 and 34 were added to show extra options
      EXTRA_CONTENT_TEMPLATE_COLLAPSE = """
      {% raw %}
      .. _{{id}}:

      {% if hide == false -%}
      .. role:: needs_tag
      .. role:: needs_status
      .. role:: needs_type
      .. role:: needs_id
      .. role:: needs_title

      .. rst-class:: need
      .. rst-class:: need_{{type_name}}

      .. container:: need

          .. container:: toggle

              .. container:: header

                  :needs_type:`{{type_name}}`: :needs_title:`{{title}}` :needs_id:`{{id}}`

      {% if status and  status|upper != "NONE" and not hide_status %}        | status: :needs_status:`{{status}}`{% endif %}
      {% if tags and not hide_tags %}        | tags: :needs_tag:`{{tags|join("` :needs_tag:`")}}`{% endif %}
      {% if my_extra_option != "" %}        | my_extra_option: {{ my_extra_option }}{% endif %}
      {% if another_option != "" %}        | another_option: {{ another_option }}{% endif %}
              | links incoming: :need_incoming:`{{id}}`
              | links outgoing: :need_outgoing:`{{id}}`

          {{content|indent(4) }}

      {% endif -%}
      {% endraw %}
      """

      needs_template_collapse = EXTRA_CONTENT_TEMPLATE_COLLAPSE


   **index.rst**

   .. code-block:: rst

      .. req:: My requirement with custom options
         :id: xyz_123
         :status: open
         :my_extra_option: A new option
         :another_option: filter_me

         Some content

      .. needfilter::
         :filter: "filter_me" in another_option

   **Result**

   .. req:: My requirement with custom options
      :id: xyz_123
      :status: open
      :my_extra_option: A new option
      :another_option: filter_me

      Some content

   .. needfilter::
      :filter: "filter_me" in another_option


.. _needs_global_options:

needs_global_options
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.0

Global options are set on global level for all needs, so that all needs get the same value for the configured option.

.. code-block:: python

   needs_global_options = {
      'global_option': 'Fix value'
   }

Default value = ``{}``

Combined with :ref:`dynamic_functions` this can be a powerful method to automate data handling::

   needs_global_options = {
         'global_option': '[[copy("id")]]'
   }


.. _needs_hide_options:

needs_hide_options
~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.0

Can be used to hide specific options from general output in rendered document::

   needs_hide_options = ['tags', 'global_option']

Works with local set options, extra options and global options.

Default value: ``['hidden']``

The ``hidden`` option is a globally available option, which is always hidden and
can be used to easily execute :ref:`dynamic_functions`.

Combined with :ref:`dynamic_functions` and :ref:`needs_global_options` this configuration can be used to perform
complex calculations in the background and hide any output.


.. _needs_template:

needs_template
~~~~~~~~~~~~~~

.. deprecated:: 0.3.0

The layout of needs can be fully customized by using `jinja <http://jinja.pocoo.org/>`_.

If nothing is set, the following default template is used:

.. code-block:: jinja

   {% raw -%}

   .. _{{id}}:

   {% if hide == false -%}
   .. role:: needs_tag
   .. role:: needs_status
   .. role:: needs_type
   .. role:: needs_id
   .. role:: needs_title

   .. rst-class:: need
   .. rst-class:: need_{{type_name}}

   .. container:: need

       :needs_type:`{{type_name}}`: :needs_title:`{{title}}` :needs_id:`{{id}}`
           {%- if status and  status|upper != "NONE" and not hide_status %}
           | status: :needs_status:`{{status}}`
           {%- endif -%}
           {%- if tags and not hide_tags %}
           | tags: :needs_tag:`{{tags|join("` :needs_tag:`")}}`
           {%- endif %}
           | links incoming: :need_incoming:`{{id}}`
           | links outgoing: :need_outgoing:`{{id}}`

           {{content|indent(8) }}

   {% endif -%}

   {% endraw %}

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

   You must add a reference like `.. _{{ '{{id}}' }}:` to the template. Otherwise linking will not work!

.. _needs_template_collapse:

needs_template_collapse
~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 0.3.0

Defines a template, which is used for need with active option **collapse**.

Default value:

.. code-block:: jinja

    {% raw -%}

    .. _{{id}}:

    {% if hide == false -%}
   .. role:: needs_tag
   .. role:: needs_status
   .. role:: needs_type
   .. role:: needs_id
   .. role:: needs_title
   .. rst-class:: need
   .. rst-class:: need_{{type_name}}

   .. container:: need

       .. container:: toggle

           .. container:: header

               :needs_type:`{{type_name}}`: :needs_title:`{{title}}` :needs_id:`{{id}}`
               :needs_type:`{{type_name}}`: :needs_title:`{{title}}` :needs_id:`{{id}}`
           {%- if status and  status|upper != "NONE" and not hide_status %}
           | status: :needs_status:`{{status}}`
           {%- endif -%}
           {%- if tags and not hide_tags %}
           | tags: :needs_tag:`{{tags|join("` :needs_tag:`")}}`
           {%- endif %}
           | links incoming: :need_incoming:`{{id}}`
           | links outgoing: :need_outgoing:`{{id}}`

       {{content|indent(4) }}

   {% endif -%}
   {% endraw %}

For more details please see :ref:`needs_template`.


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

    {% raw -%}
    <size:12>{{type_name}}</size>\\n**{{title}}**\\n<size:10>{{id}}</size>
    {% endraw %}

.. _needs_id_required:

needs_id_required
~~~~~~~~~~~~~~~~~

.. versionadded:: 0.1.19

Forces the user to set an ID for each need, which gets defined.

So no ID is autogenerated anymore, if this option is set to True::

    needs_id_required = True

By default this option is set to **False**.

If an ID is missing sphinx throws the exception "NeedsNoIdException" and stops the build.

**Example**::

    # With needs_id_required = True

    .. req:: Working Requirement
       :id: R_001

    .. req:: *Not* working, because :id: is not set.


    # With needs_id_required = False

    .. req:: This works now!


.. _needs_title_optional:

needs_title_optional
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.3

Normally a title is required to follow the need directive as follows::

    .. req:: This is the required title
        :id: R_9999

By default this option is set to **False**.

When this option is set to **True**, a title does not need to be provided, but
either some content or an `:id:` element will be required.  If a title is not
provided and no ID is provided, then an ID will be generated based on the
content of the requirement.

It is important to note in these scenarios that titles will not be available
in other directives such as needtable, needlist, needflow.

A title can be auto-generated for a requirement by either setting
needs_title_from_content_ to **True** or providing the flag
`:title_from_content:` as follows::

    .. req::
        :title_from_content:

        This will be my title.  Anything after the first sentence will not be
        part of the title.

The resulting requirement would have the title derived from the first
sentence of the requirement.

.. req::
    :title_from_content:

    This will be my title.  Anything after the first sentence will not be
    part of the title.


.. _needs_title_from_content:

needs_title_from_content
~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.3

This setting defaults to **False**.  When set to **True** and a need does
not provide a title, then a title will be generated using the first sentence
of the requirement.  The length of the title will adhere to the needs_max_title_length_
setting (which is not limited by default).

When using this setting be sure to exercise caution that special formatting
that you would not want in the title (bulleted lists, nested directives, etc.)
do not appear in the first sentence.

If a title is specified for an individual requirement, then that title
will be used over the generated title.

Example::

    .. req::

        The tool must have error logging.  All critical errors must be
        written to the console.


This will be rendered the first sentence as the title

.. req::

    The tool must have error logging.  All critical errors must be
    written to the console.


.. _needs_max_title_length:

needs_max_title_length
~~~~~~~~~~~~~~~~~~~~~~~

This option is used in conjunction with auto-generated titles as controlled by
needs_title_from_content_ and :ref:`title_from_content`.  By default there is no
limit to the length of a title.

If a maximum length is provided and the generated title would exceed that limit,
then an elided version of the title will be used.

When generating a requirement ID from the title, the full generated title will
still be used.

Example:

.. req::
    :title_from_content:

    This is a requirement with a very long title that will need to be
    shortened to prevent our titles from being too long.
    Additional content can be provided in the requirement and not be part
    of the title.

.. _needs_show_link_type:

needs_show_link_type
~~~~~~~~~~~~~~~~~~~~
.. versionadded:: 0.1.27

This option mostly effects the roles :ref:`role_need_outgoing` and :ref:`role_need_incoming` by showing
the *type* beside the ID the linked need.

Can be combined with **needs_show_link_title**.

Activate it by setting it on True in your conf.py::

    needs_show_link_type = True


.. _needs_show_link_title:

needs_show_link_title
~~~~~~~~~~~~~~~~~~~~~
.. versionadded:: 0.1.27

This option mostly effects the roles :ref:`role_need_outgoing` and :ref:`role_need_incoming` by showing
the *title* beside the ID the linked need.

Can be combined with **needs_show_link_type**.

Activate it by setting it on True in your conf.py::

    needs_show_link_title = True

.. _needs_file:

needs_file
~~~~~~~~~~
.. versionadded:: 0.1.30

Defines the location of a json file, which is used by the builder :ref:`needs_builder` as input source.
Default value: *needs.json*.

.. _needs_statuses:

needs_statuses
~~~~~~~~~~~~~~

.. versionadded:: 0.1.41

Defines a set of valid statuses, which are allowed to be used inside documentation.
If a not defined status is detected, an error is thrown and the build stops.
The checks are case sensitive.

Activate it by setting it like this::

    needs_statuses = [
        dict(name="open", description="Nothing done yet"),
        dict(name="in progress", description="Someone is working on it"),
        dict(name="implemented", description="Work is done and implemented"),
    ]

If parameter is not set or set to *False*, no checks will be performed.

Default value: *False*.

.. _needs_tags:

needs_tags
~~~~~~~~~~

.. versionadded:: 0.1.41

Defines a set of valid tags, which are allowed to be used inside documentation.
If a not defined tag is detected, an error is thrown and the build stops.
The checks are case sensitive.

Activate it by setting it like this::

    needs_tags = [
        dict(name="new", description="new needs"),
        dict(name="security", description="tag for security needs"),
    ]

If parameter is not set or set to *False*, no checks will be performed.

Default value: *False*.


.. _needs_css:

needs_css
~~~~~~~~~

.. versionadded:: 0.1.42

Defines the location of a css file, which will be added during documentation build.

If path is relative, sphinx-needs will search for related file in its own css-folder only!
Currently supported css files:

* **blank.css** : css file with empty styles
* **modern.css**: modern styles for a need (default)
* **dark.css**: styles for dark page backgrounds

Use it like this::

    needs_css = "blank.css"


To provide your own css file, the path must be absolute. Example::

    import os

    conf_py_folder = os.path.dirname(__file__)
    needs_css =  os.path.join(conf_py_folder, "my_styles.css")

See :ref:`styles_css` for available css selectors and more.


.. _needs_role_need_template:

needs_role_need_template
~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.1.48

Provides a way of changing the text representation of a referenced need.

If the role :ref:`role_need` is used, sphinx-needs will create a text representation of the referenced need.
By default a referenced need is described by the following string::

    {title} ({id})

By using ``needs_role_need_template`` this representation can be easily adjusted to own requirements.

Here are some ideas, how it could be used inside the **conf.py** file::

    needs_role_need_template = "[{id}]: {title}"
    needs_role_need_template = "-{id}-"
    needs_role_need_template = "{type}: {title} ({status})"
    needs_role_need_template = "{title} ({tags})"
    needs_role_need_template = "{title:*^20s} - {content:.30}"
    needs_role_need_template = "[{id}] {title} ({status}) {type_name}/{type} - {tags} - {links} - {links_back} - {content}"

``needs_role_need_template`` must be a string, which supports the following placeholders:

* id
* type (short version)
* type_name (long, human readable version)
* title
* status
* tags, joined by ";"
* links, joined by ";"
* links_back, joined by ";"
* content

All options of Python's `.format() <https://docs.python.org/3.4/library/functions.html#format>`_ function are supported.
Please see https://pyformat.info/ for more information.

RST-attributes like ``**bold**`` are **not** supported.

.. _needs_table_style:

needs_table_style
~~~~~~~~~~~~~~~~~
.. versionadded:: 0.2.0

Defines the default style for each table. Can be overridden for specific tables by setting parameter
:ref:`needtable_style` of directive :ref:`needtable`.

.. code-block:: python

    # conf.py
    needs_table_style = "datatables"

Default value: datatables

Supported values:

* **table**: Default sphinx table
* **datatables**: Table with activated DataTables functions (Sort, search, export, ...).


.. _needs_table_columns:

needs_table_columns
~~~~~~~~~~~~~~~~~~~
.. versionadded:: 0.2.0

Defines the default columns for each table. Can be overridden for specific tables by setting parameter
:ref:`needtable_columns` of directive :ref:`needtable`.

.. code-block:: python

    # conf.py
    needs_table_columns = "title;status;tags"

Default value: id;title;status;type;outgoing;tags

Supported values:

* id
* title
* status
* type
* tags
* incoming
* outgoing


.. _needs_collapse_details:

needs_collapse_details
~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.0

If true, need details like status, tags or links are collapsed and shown only after a click on the need title.

.. code-block:: python

    # conf.py
    needs_collapse_details = False

Default value: True

Can be overwritten for each single need by setting :ref:`need_collapse`.

.. _needs_id_regex:

needs_id_regex
~~~~~~~~~~~~~~

.. versionadded:: 0.2.0

Defines a regular expression, which is used to validate all manual set IDs and to generate valid IDs for needs
without a given ID.

Default value: ``^[A-Z0-9_]{3,}``

By default an ID is allowed to contain upper characters, numbers and underscore only.
The ID length must be at least 3 characters.

.. warning::

   An automatically generated ID of needs without an manually given ID does match
   the default value of needs_id_regex only.

   If you change the regular expression you should also set :ref:`needs_id_required`
   so that authors are forced to set an valid ID.


.. _needs_functions:

needs_functions
~~~~~~~~~~~~~~~

.. versionadded:: 0.3.0

Used to register own dynamic functions.

Must be a list of python functions.

Default value: ``[]``

Inside your ``conf.py`` file ue it like this:

.. code-block:: python

   needs_functions == [my_own_function]

   def my_own_function(app, need, needs):
       return "Awesome"]

See :ref:`dynamic_functions` for ore information.
