.. _config:

Configuration
=============

All root configurations take place in your project's :external+sphinx:ref:`conf.py file <build-config>`.

Activation
----------

Add **sphinx_needs** to your extensions.

.. code-block:: python

   extensions = ["sphinx_needs",]

Available sphinx-needs options are then listed below, that can be added to your **conf.py** file.

.. versionadded:: 4.1.0

   Configuration can also be specified via a `toml file <https://toml.io>`__.
   See :ref:`needs_from_toml` for more details.

.. _config-warnings:

Build Warnings
--------------

sphinx-needs is designed to be durable and only except when absolutely necessary.
Any non-fatal issues during the build are logged as Sphinx warnings.

If you wish to "fail-fast" during a build, see the `--fail-on-warning <https://www.sphinx-doc.org/en/master/man/sphinx-build.html#cmdoption-sphinx-build-W>`__ command-line option
(in sphinx 8.1 ``--exception-on-warning``).

You can also use this in conjunction with the `suppress_warnings <https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-suppress_warnings>`__ configuration option,
to suppress specific warnings.

Find below a list of all warnings, which can be suppressed:

.. need-warnings::

.. _`inc_build`:

Incremental build support
-------------------------

Sphinx does not use its incremental build feature, if you assign functions directly to Sphinx options.
To avoid this, please use the :ref:`Sphinx-Needs API <api_configuration>` to register functions directly.

This would allow Sphinx to perform incremental builds which are much faster as compared to full builds.

**Example configuration**

.. code-block:: python

   # conf.py

   # Defining one or more functions in conf.py is fine
   def my_custom_warning(need, log):
       # some checks
       return False

   def my_dynamic_function(app, need, needs):
       return "some text"

   # This assignment will deactivate incremental build support inside Sphinx
   needs_warnings = {
      'my_warning_no_inc_build': my_custom_warning
   }

   # Better, register the function via Sphinx-Needs API
   from sphinx_needs.api.configuration import add_warning, add_dynamic_function
   def setup(app):
      add_warning(app, 'my_warning', my_custom_warning)
      add_dynamic_function(app, my_dynamic_function)

.. hint::

   You are free to use e.g. ``needs_warnings`` and ``add_warning()`` together in a **conf.py** file.
   **Sphinx-Needs** creates internally a final list of elements defined by config-var and api-call.

   However, you should not use the same ``id`` in a config-var and the related api-call, as this would create
   the related element twice.

Options
-------

All configuration options starts with the prefix ``needs_`` for **Sphinx-Needs**.

.. _`needs_from_toml`:

needs_from_toml
~~~~~~~~~~~~~~~

.. versionadded:: 4.1.0

This configuration takes the (relative) path to a `toml file <https://toml.io>`__ which contains some or all of the needs configuration (configuration in the toml will override that in the :file:`conf.py`).

.. code-block:: python

   needs_from_toml = "ubproject.toml"

Configuration in the toml can contain any of the options below, under a ``[needs]`` section,
but with the ``needs_`` prefix removed.
For example:

.. code-block:: toml

   [needs]
   id_required = true
   id_length = 3
   types = [
      {directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"},
      {directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"},
   ]

To specify a different `root table path <https://toml.io/en/v1.0.0#table>`__ to read from in the toml file, use the ``needs_from_toml_table`` option.
For example to read from a ``[tool.needs]`` table:

.. code-block:: python

   needs_from_toml_table = ["tool"]

.. caution:: Any configuration specifying relative paths in the toml file will be resolved relative to the directory containing the :file:`conf.py` file.

needs_include_needs
~~~~~~~~~~~~~~~~~~~

Set this option to False, if no needs should be documented inside the generated documentation.

Default: **True**

.. code-block:: python

   needs_include_needs = False

.. _`needs_id_length`:

needs_id_length
~~~~~~~~~~~~~~~

This option defines the length of an automated generated ID (the length of the prefix does not count).

Default: **5**

.. code-block:: python

   needs_id_length = 3

.. _`needs_types`:

needs_types
~~~~~~~~~~~

The option allows the setup of own need types like bugs, user_stories and more.

By default it is set to:

.. code-block:: python

   needs_types = [dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
                  dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
                  dict(directive="impl", title="Implementation", prefix="I_", color="#DF744A", style="node"),
                  dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node"),
                  # Kept for backwards compatibility
                  dict(directive="need", title="Need", prefix="N_", color="#9856a5", style="node")
              ]

``needs_types`` must be a list of dictionaries where each dictionary must contain the following items:

* **directive**: Name of the directive. For instance, you can use "req" via `.. req::` in documents
* **title**: Title, used as human readable name in lists
* **prefix**: A prefix for generated IDs, to easily identify that an ID belongs to a specific type. Can also be ""
* **color**: A color as hex value. Used in diagrams and some days maybe in other representations as well. Can also be ""
* **style**: A plantuml node type, like node, artifact, frame, storage or database. See `plantuml documentation <http://plantuml.com/deployment-diagram>`__ for more.

.. note::

   `color` can also be an empty string. This makes sense, if the PlantUMl configuration is mostly provided by using
   :ref:`needs_flow_configs` and the used colors shall not get overwritten by type specific values.

.. warning::

   If a need type shall contain :ref:`need_part` and later be printed via :ref:`needflow`,
   the chosen ``PlantUML`` node type must support nested elements for
   this type.

   Types who support nested elements are for instance: ``node``, ``package``, ``frame``.
   **Not supporting** elements are for instance ``usecase``, ``actor``.

   Please take a look into the  `PlantUML Manual <https://plantuml.com/>`_ for more details.

.. _`needs_extra_options`:

needs_extra_options
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.2

The option allows the addition of extra options that you can specify on
needs.

You can set ``needs_extra_options`` as a list inside **conf.py** as follows:

.. code-block:: python

   needs_extra_options = ['introduced', 'updated', 'impacts']

And use it like:

.. code-block:: rst

   .. req:: My Requirement
      :status: open
      :introduced: Yes
      :updated: 2018/03/26
      :tags: important;complex;
      :impacts: really everything

.. note::

   To filter on these options in `needlist`, `needtable`, etc. you
   must use the :ref:`filter` option.

.. dropdown:: Show example

   **conf.py**

   .. code-block:: python

      needs_extra_options = ["my_extra_option",  "another_option"]

   **index.rst**

   .. code-block:: rst

      .. req:: My requirement with custom options
         :id: xyz_123
         :status: open
         :my_extra_option: A new option
         :another_option: filter_me

         Some content

      .. needlist::
         :filter: "filter_me" in another_option

   **Result**

   .. req:: My requirement with custom options
      :id: xyz_123
      :status: open
      :my_extra_option: A new option
      :another_option: filter_me

      Some content

   .. needlist::
      :filter: "filter_me" in another_option

.. versionadded:: 4.1.0

   Values in the list can also be dictionaries, with keys:

   * ``name``: The name of the option (required).
   * ``description``: A description of the option (optional).
       This will be output in the schema of the :ref:`needs.json <needs_builder_format>`,
       and can be used by other tools.

   For example:

   .. code-block:: python

      needs_extra_options = [
          "my_extra_option",
          {"name": "my_other_option", "description": "This is a description of the option"}
      ]

.. versionadded:: 6.0.0

   The ``needs_extra_options`` can now contain schema information for each option:

   .. code-block:: python

      needs_extra_options = [
          {
              "name": "efforts",
              "description": "Efforts in days",
              "schema": {
                  "type": "integer",
                  "mininum": 0,
              },
          }
      ]
   
   The same fields for the :ref:`supported_data_types` as in the :ref:`schema_validation`
   are accepted. If ``schema`` is given, ``type`` is required. All the other keys can also
   be defined via :ref:`needs_schema_definitions` or in the file passed via
   :ref:`needs_schema_definitions_from_json`. If specified via ``needs_extra_options``,
   the constraints are applied to *all* usages of the option.

.. _`needs_global_options`:
.. _`global_option_filters`:

needs_global_options
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.0

.. versionchanged:: 5.1.0

   The format of the global options was change to be more explicit.

   Unknown keys are also no longer accepted,
   these should also be set in the :ref:`needs_extra_options` list.

   .. dropdown:: Comparison to old format

      .. code-block:: python
         :caption: Old format

         needs_global_options = {
             "field1": "a",
             "field2": ("a", 'status == "done"'),
             "field3": ("a", 'status == "done"', "b"),
             "field4": [
                 ("a", 'status == "done"'),
                 ("b", 'status == "ongoing"'),
                 ("c", 'status == "other"', "d"),
             ],
         }

      .. code-block:: python
         :caption: New format

         needs_global_options = {
             "field1": {"default": "a"},
             "field2": {"predicates": [('status == "done"', "a")]},
             "field3": {
                 "predicates": [('status == "done"', "a")],
                 "default": "b",
             },
             "field4": {
                 "predicates": [
                     ('status == "done"', "a"),
                     ('status == "ongoing"', "b"),
                     ('status == "other"', "c"),
                 ],
                 "default": "d",
             },
         }

This configuration allows for global defaults to be set for all needs,
for any of the following fields:

- any ``needs_extra_options`` field
- any ``needs_extra_links`` field
- ``status``
- ``layout``
- ``style``
- ``tags``
- ``constraints``

Defaults will be used if the field is not set specifically by the user and thus has a "empty" value.

.. code-block:: python

   needs_extra_options = ["option1"]
   needs_global_options = {
      "tags": {"default": ["tag1", "tag2"]},
      "option1": {"default": "new value"},
   }

To set a default based on a one or more predicates, use the ``predicates`` key.
These predicates are a list of ``(match expression, value)``, evaluated in order, with the first match set as the default value.

A match expression is a string, using Python syntax, that will be evaluated against data from each need (before the resolution of defaults or dynamic functions etc):

- `id` (`str`)
- `type` (`str`)
- `title` (`str`)
- `tags` (`tuple[str, ...]`)
- `status` (`str | None`)
- `docname` (`str | None`)
- `is_external` (`bool`)
- `is_import` (`bool`)
- :ref:`needs_extra_options` (`str`)
- :ref:`needs_extra_links` (`tuple[str, ...]`)
- :ref:`needs_filter_data`

If no predicates match, the ``default`` value is used (if present).

.. code-block:: python

   needs_extra_options = ["option1"]
   needs_global_options = {
      "option1": {
      # if field is unset:
         "predicates": [
            # if status is "done", set to "value1"
            ("status == 'done'", "value1"),
            # else if status is "ongoing", set to "value2"
            ("status == 'ongoing'", "value2"),
         ]
         # else, set to "value3"
         "default": "value3",
      }
   }

.. tip::

   You can combine global options with :ref:`dynamic_functions` to automate data handling.

   .. code-block:: python

      needs_extra_options = ["option1"]
      needs_global_options = {
              "option1": {"default": '[[copy("id")]]'}
      }

.. _`needs_report_dead_links`:

needs_report_dead_links
~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 2.1.0

   Instead add ``needs.link_outgoing`` to the `suppress_warnings <https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-suppress_warnings>`__ list::

     suppress_warnings = ["needs.link_outgoing"]

Deactivate/activate log messages of disallowed outgoing dead links. If set to ``False``, then deactivate.

Default value is ``True``.

Configuration example:

.. code-block:: python

   needs_report_dead_links = False

.. _`needs_extra_links`:

needs_extra_links
~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

Allows the definition of additional link types.

Each configured link should define:

* **option**: The name of the option. Example "blocks".
* **incoming**: Incoming text, to use for incoming links. E.g. "is blocked by".
* **outgoing**: Outgoing text, to use for outgoing links. E.g. "blocks".
* **copy** (optional): True/False. If True, the links will be copied also to the common link-list (link type ``links``).
  Default: True
* **allow_dead_links** (optional): True/False. If True, dead links are allowed and do not throw a warning.
  See :ref:`allow_dead_links` for details. Default: False.
* **style** (optional): A plantuml style description, e.g. "#FFCC00". Used for :ref:`needflow`. See :ref:`links_style`.
* **style_part** (optional): Same as **style**, but get used if link is connected to a :ref:`need_part`.
  See :ref:`links_style`.

Configuration example:

.. code-block:: python

   needs_extra_links = [
      {
         "option": "checks",
         "incoming": "is checked by",
         "outgoing": "checks",
      },
      {
         "option": "triggers",
         "incoming": "is triggered by",
         "outgoing": "triggers",
         "copy": False,
         "allow_dead_links": True,
         "style": "#00AA00",
         "style_part": "#00AA00",
         "style_start": "-",
         "style_end": "--o",
      }
   ]

The above example configuration allows the following usage:

.. need-example::

   .. req:: My requirement
      :id: EXTRA_REQ_001

   .. test:: Test of requirements
      :id: EXTRA_TEST_001
      :checks: EXTRA_REQ_001, DEAD_LINK_NOT_ALLOWED
      :triggers: DEAD_LINK

.. attention:: The used option name can not be reused in the configuration of :ref:`needs_global_options`.

Link types with option-name **links** and **parent_needs** are added by default.
You are free to overwrite the default config by defining your own type with option name **links** or **parent_needs**.
This type will be used as default configuration for all links.

.. _`allow_dead_links`:

allow_dead_links
++++++++++++++++

.. versionadded:: 0.6.3

By setting ``allow_dead_links`` to ``True``, referenced, but not found needs do not throw a warning.
Instead the same text gets printed as log message on level ``INFO``.

Filtering
^^^^^^^^^

Need objects have the two attributes ``has_dead_links`` and ``has_forbidden_dead_links``.
``has_dead_links`` gets set to ``True``, if any dead link was found in the need.
And ``has_forbidden_dead_links`` is set to ``True`` only, if dead links were not allowed
(so ``allow_dead_links`` was set to ``False`` for at least one link type with dead links).

HTML style
^^^^^^^^^^

Also dead links get specific CSS attributes on the HTML output:
``needs_dead_link`` for all found dead links and an additional ``forbidden`` for link_types
with ``allow_dead_links`` not set or set to ``False``.

By default not allowed dead links will be shown in red , allowed ones in gray (see above example).

.. _`links_style`:

style / style_part
++++++++++++++++++

The style string can contain the following comma separated information:

* **color**: #ffcc00 or red
* **line style**: dotted, dashed, bold

Valid configuration examples are:

* ``#ffcc00``
* ``dashed``
* ``dotted,#red``

An empty string uses the default plantuml settings.

.. _`needflow_style_start`:

style_start / style_end
+++++++++++++++++++++++

These two options can define the arrow type, line type and line length.

See `Plantuml documentation page <https://plantuml.com/en/component-diagram>`_ for details about supported formats.

Here are some examples:

.. list-table::
   :header-rows: 1

   - * description
     * style_start
     * style_end
   - * default
     * ``-``
     * ``->``
   - * reverse
     * ``<-``
     * ``-``
   - * Both sides, dotted line
     * ``<.``
     * ``.>``
   - * Deeper level / longer line
     * ``--``
     * ``->``

Use ``style_start`` and ``style_end`` like this:

.. code-block:: python

   needs_extra_links = [
      {
         "option": "tests",
         "incoming": "is tested by",
         "outgoing": "tests",
         "copy": False,
         "style_start": "<-",
         "style_end": "down-->",
         "style": "#00AA00",
         "style_part": "dotted,#00AA00",
      }
   ]

.. note::

   Some plantuml diagrams have restrictions in the order of color (`style`)
   and orientation (`left`, `rigth`, `up` and `down`). We suggest to set the orientation
   in `style_end` like in the example above, as this is more often supported.

.. _`needs_filter_data`:

needs_filter_data
~~~~~~~~~~~~~~~~~

This option allows to use custom data inside a :ref:`filter_string`.

Configuration example:

.. code-block:: python

   def custom_defined_func():
       return "my_tag"

   needs_filter_data = {
       "current_variant": "project_x",
       "sphinx_tag": custom_defined_func(),
   }

The defined ``needs_filter_data`` must be a dictionary. Its values can be a string variable or a custom defined
function. The function get executed during config loading and must return a string.

The value of ``needs_filter_data`` will be available as data inside :ref:`filter_string` and can be very powerful
together with internal needs information to filter needs.

The defined extra filter data can be used like this:

.. code-block:: rst

   .. needextend:: type == "req" and sphinx_tag in tags
      :+tags: my_external_tag

or if project has :ref:`needs_extra_options` defined like:

.. code-block:: python

   needs_extra_options = ['variant']

The defined extra filter data can also be used like:

.. code-block:: rst

   .. needlist::
      :filter: variant != current_variant

   .. needextract::
      :filter: type == "story" and variant == current_variant
      :layout: clean
      :style: green_border

.. _`needs_allow_unsafe_filters`:

needs_allow_unsafe_filters
~~~~~~~~~~~~~~~~~~~~~~~~~~

Allow unsafe filter for :ref:`filter_func`. Default is ``False``.

If set to True, the filtered results will keep all fields as they are returned by the dynamic functions.
Fields can be added or existing fields can even be manipulated.

.. note:: Keep in mind this only affects the filter results, original needs as displayed somewhere else are not modified.

If set to False, the filter results contains the original need fields and any manipulations of need fields are lost.

.. code-block:: python

   needs_allow_unsafe_filters = True

.. _`needs_filter_max_time`:

needs_filter_max_time
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 4.0.0

If set, warn if any :ref:`filter processing <filter>` call takes longer than the given time in seconds.

.. _`needs_uml_process_max_time`:

needs_uml_process_max_time
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 4.0.0

If set, warn if any :ref:`needuml` or :ref:`needarch` jinja content rendering takes longer than the given time in seconds.

.. _`needs_flow_engine`:

needs_flow_engine
~~~~~~~~~~~~~~~~~

.. versionadded:: 2.2.0

Select between the rendering engines for :ref:`needflow` diagrams,

* ``plantuml``: Use `PlantUML <https://plantuml.com/>`__ to render the diagrams (default).
* ``graphviz``: Use `Graphviz <https://graphviz.org>`__ to render the diagrams.

.. _`needs_flow_show_links`:

needs_flow_show_links
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

Used to de/activate the output of link type names beside the connection in the :ref:`needflow` directive:

.. code-block:: python

   needs_flow_show_links = True

Default value: ``False``

Can be configured also for each :ref:`needflow` directive via :ref:`needflow_show_link_names`.

.. _`needs_flow_link_types`:

needs_flow_link_types
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

Defines the link_types to show in a :ref:`needflow` diagram:

.. code-block:: python

   needs_flow_link_types = ['links', 'blocks', 'tests']

You can define this setting on each specific ``needflow`` by using the :ref:`needflow` directive option :ref:`needflow_link_types`.
See also :ref:`needflow_link_types` for more details.

Default value: ``['links']``

.. _`needs_flow_configs`:

needs_flow_configs
~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.5.2

``needs_flow_configs`` must be a dictionary which can store multiple `PlantUML configurations <https://plantuml.com/>`_.
These configs can then be selected when using :ref:`needflow`.

.. code-block:: python

   needs_flow_configs = {
      'my_config': """
          skinparam monochrome true
          skinparam componentStyle uml2
      """,
      'another_config': """
          skinparam class {
              BackgroundColor PaleGreen
              ArrowColor SeaGreen
              BorderColor SpringGreen
          }
      """
   }

This configurations can then be used like this:

.. need-example::

   .. needflow::
      :tags: flow_example
      :types: spec
      :config: lefttoright,my_config

Multiple configurations can be used by separating them with a comma,
these will be applied in the order they are defined.

See :ref:`needflow config option <needflow_config>` for more details and already available configurations.

.. _`needs_graphviz_styles`:

needs_graphviz_styles
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2.2.0

This must be a dictionary which can store multiple `Graphviz configurations <https://graphviz.org>`__.
These configs can then be selected when using :ref:`needflow` and the engine is set to ``graphviz``.

.. code-block:: python

   needs_graphviz_styles = {
       "my_config": {
           "graph": {
               "rankdir": "LR",
               "bgcolor": "transparent",
           },
           "node": {
               "fontname": "sans-serif",
               "fontsize": 12,
           },
           "edge": {
               "color": "#57ACDC",
               "fontsize": 10,
           },
       }
   }

This configurations can then be used like this:

.. code-block:: restructuredtext

   .. needflow::
       :engine: graphviz
       :config: lefttoright,my_config

Multiple configurations can be used by separating them with a comma,
these will be merged in the order they are defined.
For example ``my_config1,my_config2`` would be the same as ``my_config3``:

.. code-block:: python

   needs_graphviz_styles = {
       "my_config1": {
           "graph": {
               "rankdir": "LR",
           }
       },
       "my_config2": {
           "graph": {
               "bgcolor": "transparent",
           }
       }
       "my_config3": {
           "graph": {
               "rankdir": "LR",
               "bgcolor": "transparent",
           }
       }
   }

.. _`needs_report_template`:

needs_report_template
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.0.1

You can customize the layout of :ref:`needreport` using `Jinja <http://jinja.pocoo.org/>`__.

Set the value of ``needs_report_template`` to the path of the template you want to use.

.. note::

   The path must be an absolute path based on the **conf.py** directory.
   Example: ``needs_report_template = '/needs_templates/report_template.need'``

   The template file should be a plain file with any of the following file extensions: ``.rst``, ``.need``, or ``.txt``.

If you do not set ``needs_report_template``, the default template used is:

.. code-block:: jinja

   {# Output for needs_types #}
   {% if types|length != 0 %}
   .. dropdown:: Need Types
      :class: needs_report_table

      .. list-table::
        :widths: 40 20 20 20
        :header-rows: 1

        * - TITLE
          - DIRECTIVE
          - PREFIX
          - STYLE
        {% for type in types %}
        * - {{ type.title }}
          - {{ type.directive }}
          - `{{ type.prefix }}`
          - {{ type.style }}
        {% endfor %}
   {% endif %}
   {# Output for needs_types #}

   {# Output for needs_extra_links #}
   {% if links|length != 0 %}
   .. dropdown:: Need Extra Links
      :class: needs_report_table

      .. list-table::
        :widths: 10 30 30 5 20
        :header-rows: 1

        * - OPTION
          - INCOMING
          - OUTGOING
          - COPY
          - ALLOW DEAD LINKS
        {% for link in links %}
        * - {{ link.option | capitalize }}
          - {{ link.incoming | capitalize }}
          - {{ link.outgoing | capitalize }}
          - {{ link.get('copy', None) | capitalize }}
          - {{ link.get('allow_dead_links', False) | capitalize }}
        {% endfor %}
   {% endif %}
   {# Output for needs_extra_links #}

   {# Output for needs_options #}
   {% if options|length != 0 %}
   .. dropdown:: Need Extra Options
      :class: needs_report_table

      {% for option in options %}
      * {{ option }}
      {% endfor %}
   {% endif %}
   {# Output for needs_options #}

   {# Output for needs metrics #}
   {% if usage|length != 0 %}
   .. dropdown:: Need Metrics

      .. list-table::
         :widths: 40 40
         :header-rows: 1

         * - NEEDS TYPES
           - NEEDS PER TYPE
         {% for k, v in usage["needs_types"].items() %}
         * - {{ k | capitalize }}
           - {{ v }}
         {% endfor %}
         * - **Total Needs Amount**
           - {{ usage.get("needs_amount") }}
   {% endif %}
   {# Output for needs metrics #}

The plugin provides the following variables which you can use in your custom Jinja template:

* types - list of :ref:`need types <needs_types>`
* links - list of :ref:`extra need links <needs_extra_links>`
* options - list of :ref:`extra need options <needs_extra_options>`
* usage - a dictionary object containing information about the following:
    + needs_amount -> total amount of need objects in the project
    + needs_types -> number of need objects per needs type

needs_diagram_template
~~~~~~~~~~~~~~~~~~~~~~

This option allows to control the content of diagram elements which get automatically generated by using
`.. needflow::` / :ref:`needflow` (when using the ``plantuml`` engine).

This function is based on `plantuml <http://plantuml.com>`__, so that each
`supported style <http://plantuml.com/creole>`_ can be used.

The rendered template is used inside the following plantuml syntax and must care about leaving the final string
valid:

.. code-block:: python

   'node "YOUR_TEMPLATE" as need_id [[need_link]]'

By default the following template is used:

.. code-block:: jinja

   {%- if is_need -%}
   <size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>
   {%- else -%}
   <size:12>{{type_name}} (part)</size>\\n**{{content|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id_parent}}.**{{id}}**</size>
   {%- endif -%}

.. _`needs_id_required`:

needs_id_required
~~~~~~~~~~~~~~~~~

.. versionadded:: 0.1.19

Forces the user to set an ID for each need, which gets defined.

So no ID is autogenerated any more, if this option is set to True:

.. code-block:: python

   needs_id_required = True

By default this option is set to **False**.

**Example**:

.. code-block:: rst

   .. With needs_id_required = True

   .. req:: Working Requirement
      :id: R_001

   .. req:: **Not working**, because :id: is not set.


   .. With needs_id_required = False

   .. req:: This works now!

.. _`needs_id_from_title`:

needs_id_from_title
~~~~~~~~~~~~~~~~~~~

Generates needs ID from title. By default, this setting is set to **False**.

When no need ID is given by the user, and `needs_id_from_title` is set to **True**, then a need ID
will be calculated based on the current need directive prefix, title, and a hashed value from title.

.. need-example::

   .. req:: Group big short

The calculated need ID will be: `R_GROUP_BIG_SHORT_{hashed value}`, if the need ID length doesn't
exceed the setting from :ref:`needs_id_length`.

.. note::

   The user needs to ensure the uniqueness of the given title, and also match the settings of
   :ref:`needs_id_length` and :ref:`needs_id_regex`.

.. _`needs_title_optional`:

needs_title_optional
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.3

Normally a title is required to follow the need directive as follows:

.. code-block:: rst

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
:ref:`needs_title_from_content` to **True** or providing the flag
`:title_from_content:` as follows:

The resulting requirement would have the title derived from the first
sentence of the requirement.

.. need-example::

   .. req::
      :title_from_content:

      This will be my title.  Anything after the first sentence will not be
      part of the title.

.. _`needs_title_from_content`:

needs_title_from_content
~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.3

This setting defaults to **False**. When set to **True** and a need does
not provide a title, then a title will be generated using the first sentence
in the content of the requirement.  The length of the title will adhere to the needs_max_title_length_
setting (which is not limited by default).

.. note::

   When using this setting be sure to exercise caution that special formatting
   that you would not want in the title (bulleted lists, nested directives, etc.)
   do not appear in the first sentence.

If a title is specified for an individual requirement, then that title
will be used over the generated title.

.. need-example::

   .. req::

      The tool must have error logging.
      All critical errors must be written to the console.

.. _`needs_max_title_length`:

needs_max_title_length
~~~~~~~~~~~~~~~~~~~~~~

This option is used in conjunction with auto-generated titles as controlled by
needs_title_from_content_ and :ref:`title_from_content`. By default, there is no
limit to the length of a title.

If you provide a maximum length and the generated title exceeds that limit,
then we use an elided version of the title.

When generating a requirement ID from the title, the full generated title will
still be used.

Example:

.. req::
   :title_from_content:

   This is a requirement with a very long title that will need to be
   shortened to prevent our titles from being too long.
   Additional content can be provided in the requirement and not be part
   of the title.

.. _`needs_show_link_type`:

needs_show_link_type
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.1.27

This option mostly affects the roles :ref:`role_need_outgoing` and :ref:`role_need_incoming` by showing
the *type* beside the ID of the linked need.

Can be combined with **needs_show_link_title**.

Activate it by setting it on True in your **conf.py**:

.. code-block:: python

   needs_show_link_type = True

.. _`needs_show_link_title`:

needs_show_link_title
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.1.27

This option mostly affects the roles :ref:`role_need_outgoing` and :ref:`role_need_incoming` by showing
the *title* beside the ID of the linked need.

Can be combined with **needs_show_link_type**.

Activate it by setting it on True in your **conf.py**:

.. code-block:: python

   needs_show_link_title = True

.. _`needs_show_link_id`:

needs_show_link_id
~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.0.3

This option mostly affects the roles :ref:`role_need_outgoing` and :ref:`role_need_incoming` by showing
the *ID*  of the linked need.

Can be combined with :ref:`needs_show_link_type` and :ref:`needs_show_link_title`.

.. code-block:: python

   needs_show_link_id = True

.. _`needs_file`:

needs_file
~~~~~~~~~~

.. versionadded:: 0.1.30

Defines the location of a JSON file, which is used by the builder :ref:`needs_builder` as input source.
Default value: *needs.json*.

.. _`needs_statuses`:

needs_statuses
~~~~~~~~~~~~~~

.. versionadded:: 0.1.41

Defines a set of valid statuses, which are allowed to be used inside documentation.
If we detect a status not defined, an error is thrown and the build stops.
The checks are case sensitive.

Activate it by setting it like this:

.. code-block:: python

   needs_statuses = [
       dict(name="open", description="Nothing done yet"),
       dict(name="in progress", description="Someone is working on it"),
       dict(name="implemented", description="Work is done and implemented"),
   ]

If parameter is not set or set to *False*, no checks will be performed.

Default value: *[]*.

.. _`needs_tags`:

needs_tags
~~~~~~~~~~

.. versionadded:: 0.1.41

Defines a set of valid tags, which are allowed to be used inside documentation.
If we detect a tag not defined, an error is thrown and the build stops.
The checks are case sensitive.

Activate it by setting it like this:

.. code-block:: python

   needs_tags = [
       dict(name="new", description="new needs"),
       dict(name="security", description="tag for security needs"),
   ]

If parameter is not set or set to *[]*, no checks will be performed.

Default value: *[]*.

.. _`needs_css`:

needs_css
~~~~~~~~~

.. versionadded:: 0.1.42

Defines the location of a CSS file, which will be added during documentation build.

If path is relative, **Sphinx-Needs** will search for related file in its own CSS-folder only!
Currently supported CSS files:

* **blank.css** : CSS file with empty styles
* **modern.css**: modern styles for a need (default)
* **dark.css**: styles for dark page backgrounds

Use it like this:

.. code-block:: python

   needs_css = "blank.css"

To provide your own CSS file, the path must be absolute. Example:

.. code-block:: python

   import os

   conf_py_folder = os.path.dirname(__file__)
   needs_css =  os.path.join(conf_py_folder, "my_styles.css")

See :ref:`styles_css` for available CSS selectors and more.

.. _`needs_role_need_template`:

needs_role_need_template
~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.1.48

Provides a way of changing the text representation of a referenced need.

If you use the role :ref:`role_need`, **Sphinx-Needs** will create a text representation of the referenced need.
By default a referenced need is described by the following string:

.. code-block:: jinja

   {title} ({id})

By using ``needs_role_need_template`` this representation can be easily adjusted to own requirements.

Here are some ideas, how it could be used inside the **conf.py** file:

.. code-block:: python

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

.. _`needs_role_need_max_title_length`:

needs_role_need_max_title_length
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.14

Defines the maximum length of need title that is shown in need references.

By default, need titles that are longer than 30 characters are shortened when
shown in :ref:`role_need` text representation and "..." is added at end. By
using ``needs_role_need_max_title_length``, it is possible to change this
maximum length.

If set to -1 the title will never be shortened.

.. code-block:: python

   # conf.py
   needs_role_need_max_title_length = 45

.. _`needs_table_style`:

needs_table_style
~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.0

Defines the default style for each table. Can be overridden for specific tables by setting parameter
:ref:`needtable_style` of directive :ref:`needtable`.

.. code-block:: python

   # conf.py
   needs_table_style = "datatables"

Default value: ``"datatables"``

Supported values:

* **table**: Default Sphinx table
* **datatables**: Table with activated DataTables functions (Sort, search, export, ...).

.. _`needs_table_columns`:

needs_table_columns
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.0

Defines the default columns for each table. Can be overridden for specific tables by setting parameter
:ref:`needtable_columns` of directive :ref:`needtable`.

.. code-block:: python

   # conf.py
   needs_table_columns = "title;status;tags"

Default value: ``"id;title;status;type;outgoing;tags"``

Supported values:

* id
* title
* status
* type
* tags
* incoming
* outgoing

.. _`needs_id_regex`:

needs_id_regex
~~~~~~~~~~~~~~

.. versionadded:: 0.2.0

Defines a regular expression used to validate all manually set IDs and to generate valid IDs for needs
without a given ID.

Default value: ``^[A-Z0-9_]{5,}``

By default, an ID is allowed to contain upper characters, numbers and underscore only.
The ID length must be at least 3 characters.

.. warning::

   An automatically generated ID of needs without a manually given ID must match
   the default value of needs_id_regex only.

   If you change the regular expression, you should also set :ref:`needs_id_required`
   so that authors are forced to set an valid ID.

.. _`needs_functions`:

needs_functions
~~~~~~~~~~~~~~~

.. versionadded:: 0.3.0

Used to register own dynamic functions.

Must be a list of :py:class:`.DynamicFunction`.

Default value: ``[]``

Inside your **conf.py** file use it like this:

.. code-block:: python

   needs_functions == [my_own_function]

   def my_own_function(app, need, needs):
       return "Awesome"

See :ref:`dynamic_functions` for more information.

.. warning::

   Assigning a function to a Sphinx option will deactivate the incremental build feature of Sphinx.
   Please use the :ref:`Sphinx-Needs API <api_configuration>` and read :ref:`inc_build` for details.

It is better to use the following way in your **conf.py** file:

.. code-block:: python

   from sphinx_needs.api import add_dynamic_function

      def my_function(app, need, needs, *args, **kwargs):
          # Do magic here
          return "some data"

      def setup(app):
            add_dynamic_function(app, my_function)

.. _`needs_part_prefix`:

needs_part_prefix
~~~~~~~~~~~~~~~~~

.. versionadded:: 0.3.6

String used as prefix for :ref:`need_part` output in :ref:`tables <needtable_show_parts>`.

Default value: ``u'\u2192\u00a0'``

The default value contains an arrow right and a non breaking space.

.. code-block:: python

   needs_part_prefix = u'\u2192\u00a0'

See :ref:`needtable_show_parts` for an example output.

.. _`needs_warnings`:

needs_warnings
~~~~~~~~~~~~~~

.. versionadded:: 0.5.0

``needs_warnings`` allows the definition of warnings which all needs must avoid during a Sphinx build.

A raised warning will print a sphinx-warning during build time.

Use ``-W`` in your Sphinx build command to stop the whole build, if a warning is raised.
This will handle **all warnings** as exceptions.

.. code-block:: python

   def my_custom_warning_check(need, log):
       if need["status"] == "open":
           log.info(f"{need['id']} status must not be 'open'.")
           return True
       return False


   needs_warnings = {
     # req need must not have an empty status field
     'req_with_no_status': "type == 'req' and not status",

     # status must be open or closed
     'invalid_status' : "status not in ['open', 'closed']",

     # user defined filter code function
     'type_match': my_custom_warning_check,
   }

``needs_warnings`` must be a dictionary.
The **dictionary key** is used as identifier and gets printed in log outputs.
The **value** must be a valid filter string or a custom defined filter code function and defines a *not allowed behavior*.

So use the filter string or filter code function to define how needs are not allowed to be configured/used.
The defined filter code function must return ``True`` or ``False``.

.. warning::

   Assigning a function to a Sphinx option will deactivate the incremental build feature of Sphinx.
   Please use the :ref:`Sphinx-Needs API <api_configuration>` and read :ref:`inc_build` for details.

Example output:

.. code-block:: text

   ...
   looking for now-outdated files... none found
   pickling environment... done
   checking consistency... WARNING: Sphinx-Needs warnings were raised. See console / log output for details.

   Checking Sphinx-Needs warnings
     type_check: passed
     invalid_status: failed
         failed needs: 11 (STYLE_005, EX_ROW_1, EX_ROW_3, copy_2, clv_1, clv_2, clv_3, clv_4, clv_5, T_C3893, R_AD4A0)
         used filter: status not in ["open", "in progress", "closed", "done"] and status is not None

     type_match: failed
         failed needs: 1 (TC_001)
         used filter: <function my_custom_warning_check at 0x7faf3fbcd1f0>
   done
   ...

Due to the nature of Sphinx logging, a sphinx-warning may be printed wherever in the log.

.. _`needs_warnings_always_warn`:

needs_warnings_always_warn
~~~~~~~~~~~~~~~~~~~~~~~~~~

If set to ``True``, will allow you to log :ref:`needs_warnings` not passed into a given file if using your Sphinx build
command with ``-w``.

Default: ``False``.

For example, set this option to True:

.. code-block:: python

   needs_warnings_always_warn = True

Using Sphinx build command ``sphinx-build -M html {srcdir} {outdir} -w error.log``, all the :ref:`needs_warnings` not passed will be
logged into a **error.log** file as you specified.

If you use ``sphinx-build -M html {srcdir} {outdir} -W -w error.log``, the first :ref:`needs_warnings` not passed will stop the build and
be logged into the file error.log.

.. _`needs_layouts`:

needs_layouts
~~~~~~~~~~~~~

.. versionadded:: 0.5.0

You can use ``needs_layouts`` to define custom grid-based layouts with custom data.

Please read :ref:`layouts_styles` for a lot more detailed information.

``needs_layouts`` must be a dictionary and each key represents a layout. A layout must define the used grid-system and
a layout-structure.

Example:

.. code-block:: python

   needs_layouts = {
       'my_layout': {
           'grid': 'simple',
           'layout': {
               'head': ['my custom head'],
               'meta': ['my first meta line',
                        'my second meta line']
           }
       }
   }

.. note::

   **Sphinx-Needs** provides some default layouts. These layouts cannot be overwritten.
   See :ref:`layout list <layouts>` for more information.

.. _`needs_default_layout`:

needs_default_layout
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.5.0

``needs_default_layout`` defines the layout to use by default.

The name of the layout must have been provided by **Sphinx-Needs** or by user via
configuration :ref:`needs_layouts`.

Default value of ``needs_default_layout`` is ``clean``.

.. code-block:: python

   needs_default_layout = 'my_own_layout'

.. _`needs_default_style`:

needs_default_style
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.5.0

The value of ``needs_default_style`` is used as default value for each need which does not define its own
style information via ``:style:`` option.

See :ref:`styles` for a list of default style names.

.. code-block:: python

   needs_default_layout = 'border_yellow'

A combination of multiple styles is possible:

.. code-block:: python

   needs_default_style = 'blue, green_border'

Custom values can be set as well, if your projects provides the needed CSS-files for it.

.. _`needs_template_folder`:

needs_template_folder
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.5.2

``needs_template_folder`` allows the definition of your own **Sphinx-Needs** template folder.
By default this is ``needs_templates/``.

The folder must already exist, otherwise an exception gets thrown, if a need tries to use a template.

Read also :ref:`need_template option description <need_template>` for information of how to use templates.

.. _`needs_duration_option`:

needs_duration_option
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.5.5

Used to define option to store ``duration`` information for :ref:`needgantt`.

See also :ref:`needgantt_duration_option`, which overrides this value for specific ``needgantt`` charts.

Default: :ref:`need_duration`

.. _`needs_completion_option`:

needs_completion_option
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.5.5

Used to define option to store ``completion`` information for :ref:`needgantt`.

See also :ref:`needgantt_completion_option`, which overrides this value for specific ``needgantt`` charts.

Default: :ref:`need_completion`

.. _`needs_services`:

needs_services
~~~~~~~~~~~~~~

.. versionadded:: 0.6.0

Takes extra configuration options for :ref:`services`:

.. code-block:: python

   needs_services = {
       'jira': {
           'url': 'my_jira_server.com',
       },
       'git': {
           'url': 'my_git_server.com',
       },
       'my_service': {
           'class': MyServiceClass,
           'config_1': 'value_x',
       }
   }

Each key-value-pair in ``needs_services`` describes a service specific configuration.

Own services can be registered by setting ``class`` as additional option.

Config options are service specific and are described by :ref:`services`.

See also :ref:`needservice`.

.. _`needs_service_all_data`:

needs_service_all_data
~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.6.0

If set to ``True``, data for options which are unknown, is added as string to the need content.
If ``False``, unknown option data is not shown anywhere.

Default: ``False``.

.. code-block:: python

   needs_service_all_data = True

.. _`needs_import_keys`:

needs_import_keys
~~~~~~~~~~~~~~~~~

.. versionadded:: 4.2.0

For use with the :ref:`needimport` directive, mapping keys to file paths, see :ref:`needimport-keys`.

.. _`needs_external_needs`:

needs_external_needs
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.7.0

Allows to reference and use external needs without having their representation in your own documentation.
(Unlike :ref:`needimport`, which creates need-objects from a local ``needs.json`` only).

.. code-block:: python

   needs_external_needs = [
     {
       'base_url': 'http://mydocs/my_project',
       'json_url':  'http://mydocs/my_project/needs.json',
       'version': '1.0',
       'id_prefix': 'ext_',
       'css_class': 'external_link',
     },
     {
       'base_url': 'http://mydocs/another_project/',
       'json_path':  'my_folder/needs.json',
       'version': '2.5',
       'id_prefix': 'other_',
       'css_class': 'project_x',
     },
     {
       'base_url': '<relative_path_from_my_build_html_to_my_project>/<relative_path_to_another_project_build_html>',
       'json_path':  'my_folder/needs.json',
       'version': '2.5',
       'id_prefix': 'ext_',
       'css_class': 'project_x',
     },
     {
       "base_url": "http://my_company.com/docs/v1/",
       "target_url": "issue/{{need['id']}}",
       "json_path": "needs_test.json",
       "id_prefix": "ext_need_id_",
     },
     {
       "base_url": "http://my_company.com/docs/v1/",
       "target_url": "issue/{{need['type']|upper()}}",
       "json_path": "needs_test.json",
       "id_prefix": "ext_need_type_",
     },
     {
       "base_url": "http://my_company.com/docs/v1/",
       "target_url": "issue/fixed_string",
       "json_path": "needs_test.json",
       "id_prefix": "ext_string_",
     },
   ]

``needs_external_needs`` must be a list of dictionary elements and each dictionary must/can have the following
keys:

:base_url: Base url which is used to calculate the final, specific need url. Normally the path under which the ``index.html`` is provided.
  Base url supports also relative path, which starts from project build html folder (normally where ``index.html`` is located).
:target_url: Allows to config the final caculated need url. (*optional*)
  |br| If provided, ``target_url`` will be appended to ``base_url`` as the final calculate need url, e.g. ``base_url/target_url``.
  If not, the external need url uses the default calculated ``base_url``.
  |br| The ``target_url`` supports Jinja context ``{{need[]}}``, ``need option`` used as key, e.g ``{{need['id']}}`` or ``{{need['type']}}``.
:json_url: An url, which can be used to download the ``needs.json`` (or similar) file.
:json_path: The path to a ``needs.json`` file located inside your documentation project. Can not be used together with
  ``json_url``. |br| The value must be a relative path, which is relative to the project configuration folder
  (where the **conf.py** is stored). (Since version `0.7.1`)
:version: Defines the version to use inside the ``needs.json`` file (*optional*).
:id_prefix: Prefix as string, which will be added to all id of external needs. Needed, if there is the risk that
  needs from different projects may have the same id (*optional*).
:css_class: A class name as string, which gets set in link representations like :ref:`needtable`.
  The related CSS class definition must be done by the user, e.g. by :ref:`own_css`.
  (*optional*) (*default*: ``external_link``)

.. _`needs_needextend_strict`:

needs_needextend_strict
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.0.3

``needs_needextend_strict`` allows you to deactivate or activate
the :ref:`strict <needextend_strict>` option behaviour for all :ref:`needextend` directives.

.. _`needs_table_classes`:

needs_table_classes
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.7.2

Allows to define custom CSS classes which get set for the HTML tables of  ``need`` and ``needtable``.
This may be needed to avoid custom table handling of some specific Sphinx theme like ReadTheDocs.

.. code-block:: python

   needs_table_classes = ['my_custom_class', 'another_class']

These classes are not set for needtables using the ``table`` style, which is using the normal Sphinx table layout
and therefore must be handled by themes.

.. _`needs_builder_filter`:

needs_builder_filter
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.7.2

Defines a :ref:`filter_string` used to filter needs for the builder :ref:`needs_builder`.

Default is ``'is_external==False'``, so all locally defined need objects are taken into account.
Need objects imported via :ref:`needs_external_needs` get sorted out.

.. code-block:: python

   needs_builder_filter = 'status=="open"'

.. _`needs_string_links`:

needs_string_links
~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.7.4

Transforms a given option value to a link.

Helpful e.g. to generate a link to a ticket system based on the given ticket number only.

.. code-block:: python

   needs_string_links = {
       'custom_name': {
           'regex': "...",
           'link_url' : "...",
           'link_name': '...'
           'options': ['status', '...']
       }
   }

:regex: Must be a valid regular expression. Named capture groups are supported.
:link_url: The final url as string. Supports Jinja.
:link_name: The final link name as string. Supports Jinja.
:options: List of option names, for which the regex shall be checked.

``link_name`` and ``link_url`` support the `Jinja2 <https://jinja.palletsprojects.com>`__ syntax.
All named capture group values get injected, so that parts of the option-value can be reused for
link name and url.

**Example**:

.. code-block:: python

   # conf.py

   needs_string_links = {
       # Adds link to the Sphinx-Needs configuration page
       'config_link': {
           'regex': r'^(?P<value>\w+)$',
           'link_url': 'https://sphinx-needs.readthedocs.io/en/latest/configuration.html#{{value | replace("_", "-")}}',
           'link_name': 'Sphinx-Needs docs for {{value | replace("_", "-") }}',
           'options': ['config']
       },
       # Links to the related github issue
       'github_link': {
           'regex': r'^(?P<value>\w+)$',
           'link_url': 'https://github.com/useblocks/sphinx-needs/issues/{{value}}',
           'link_name': 'GitHub #{{value}}',
           'options': ['github']
       }
   }

.. need-example::

   .. spec:: Use needs_string_links
      :id: EXAMPLE_STRING_LINKS
      :config: needs_string_links
      :github: 404,652

      Replaces the string from ``:config:`` and ``:github:`` with a link to the related website.

.. note:: You must define the options specified under :ref:`needs_string_links` inside :ref:`needs_extra_options` as well.

.. _`needs_build_json`:

needs_build_json
~~~~~~~~~~~~~~~~

.. versionadded:: 0.7.6

Builds a ``needs.json`` file during other builds, like ``html``.

This allows to have one single Sphinx-Build for two output formats, which may save some time.

All other ``needs.json`` related configuration values, like :ref:`needs_file`,
:ref:`needs_build_json_per_id` and :ref:`needs_json_remove_defaults`
are taken into account.

Default: False

Example:

.. code-block:: python

   needs_build_json = True

.. hint::

   The created ``needs.json`` file gets stored in the ``outdir`` of the current builder.
   So if ``html`` is used as builder, the final location is e.g. ``_build/html/needs.json``.

   See :ref:`this section <needs_builder_format>`, for an explanation of the output format.

.. _`needs_reproducible_json`:

needs_reproducible_json
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2.0.0

Setting ``needs_reproducible_json = True`` will ensure the ``needs.json`` output is reproducible,
e.g. by removing timestamps from the output.

.. _`needs_json_exclude_fields`:

needs_json_exclude_fields
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2.2.0

Setting ``needs_json_exclude_fields = ["key1", "key2"]`` will exclude the given fields from all needs in the ``needs.json`` output.

Default: :need_config_default:`json_exclude_fields`

.. _`needs_json_remove_defaults`:

needs_json_remove_defaults
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2.1.0

Setting ``needs_json_remove_defaults = True`` will remove all need fields with default from ``needs.json``, greatly reducing its size.

The defaults can be retrieved from the ``needs_schema`` now also output in the JSON file (see :ref:`this section <needs_builder_format>` for the format).

Default: :need_config_default:`json_remove_defaults`

.. _`needs_build_json_per_id`:

needs_build_json_per_id
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2.0.0

Builds list json files for each need. The name of each file is the ``id`` of need.
This option works like :ref:`needs_build_json`.

Default: False

Example:

.. code-block:: python

   needs_build_json_per_id = False

.. hint:: The created single json file per need, located in :ref:`needs_build_json_per_id_path` folder, e.g ``_build/needs_id/abc_432.json``

.. _`needs_build_json_per_id_path`:

needs_build_json_per_id_path
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 2.0.0

This option sets the location of the set of ``needs.json`` for every needs-id.

Default value: ``needs_id``

Example:

.. code-block:: python

   needs_build_json_per_id_path = "needs_id"

.. hint:: The created ``needs_id`` folder gets stored in the ``outdir`` of the current builder. The final location is e.g. ``_build/needs_id``

.. _`needs_build_needumls`:

needs_build_needumls
~~~~~~~~~~~~~~~~~~~~

Exports :ref:`needuml` data during each build.

This option works like :ref:`needs_build_json`. But the value of :ref:`needs_build_needumls` should be a string,
not a boolean. Default value of is: ``""``.

This value of this option shall be a **relative folder path**, which specifies and creates the relative folder in the
``outdir`` of the current builder.

Example:

.. code-block:: python

   needs_build_needumls = "my_needumls"

As a result, all the :ref:`needuml` data will be exported into folder in the ``outdir`` of the current builder, e.g. ``_build/html/my_needumls/``.

.. _`needs_permalink_file`:

needs_permalink_file
~~~~~~~~~~~~~~~~~~~~

The option specifies the name of the permalink html file,
which will be copied to the html build directory during build.

The permalink web site will load a ``needs.json`` file as specified
by :ref:`needs_permalink_data` and re-direct the web browser to the html document
of the need, which is specified by appending the need ID as a query
parameter, e.g., ``http://localhost:8000/permalink.html?id=REQ_4711``.

Example:

.. code-block:: python

   needs_permalink_file = "my_permalink.html"

Results in a file ``my_permalink.html`` in the
html build directory.
If this directory is served on ``localhost:8000``, then the file will be
available at ``http://localhost:8000/my_permalink.html``.

Default value: ``permalink.html``

.. _`needs_permalink_data`:

needs_permalink_data
~~~~~~~~~~~~~~~~~~~~

This options sets the location of a ``needs.json`` file.
This file is used to create permanent links for needs as described
in :ref:`needs_permalink_file`.

The path can be a relative path (relative to the permalink html file),
an absolute path (on the web server) or an URL.

Default value: ``needs.json``

.. _`needs_constraints`:

needs_constraints
~~~~~~~~~~~~~~~~~

.. versionadded:: 1.0.1

.. code-block:: python

   needs_constraints = {

       "critical": {
           "check_0": "'critical' in tags",
           "check_1": "'security_req' in links",
           "severity": "CRITICAL"
       },

       "security": {
           "check_0": "'security' in tags",
           "severity": "HIGH"
       },

       "team": {
           "check_0": "author == \"Bob\"",
           "severity": "LOW"
       },

   }

needs_constraints needs to be enabled by adding "constraints" to :ref:`needs_extra_options`

needs_constraints contains a dictionary which contains dictionaries describing a single constraint. A single constraint's name serves as the key for the inner dictionary.
Inside there are (multiple) checks and a severity. Each check describes an executable constraint which allows to set conditions the specific need has to fulfill.
Depending on the severity, different behaviours in case of failure can be configured. See :ref:`needs_constraint_failed_options`

Each need now contains additional attributes named "constraints_passed" and "constraints_results".

constraints_passed is a bool showing if ALL constraints of a corresponding need were passed.

constraints_results is a dictionary similar in structure to needs_constraints above. Instead of executable python statements, inner values contain a bool describing if check_0, check_1 ... passed successfully.

.. versionadded:: 2.0.0

   The ``"error_message"`` key can contain a string, with Jinja templating, which will be displayed if the constraint fails, and saved on the need as ``constraints_error``:

   .. code-block:: python

      needs_constraints = {

          "critical": {
              "check_0": "'critical' in tags",
              "severity": "CRITICAL",
              "error_message": "need {{id}} does not fulfill CRITICAL constraint, because tags are {{tags}}"
          }

      }

.. code-block:: rst

   .. req::
       :id: SECURITY_REQ

       This is a requirement describing security processes.

   .. req::
       :tags: critical
       :links: SECURITY_REQ
       :constraints: critical

       Example of a successful constraint.

   .. req::
       :id: FAIL_01
       :author: "Alice"
       :constraints: team

       Example of a failed constraint with medium severity. Note the style from :ref:`needs_constraint_failed_options`

.. req::
   :id: SECURITY_REQ

   This is a requirement describing security processes.

.. req::
   :tags: critical
   :links: SECURITY_REQ
   :constraints: critical

   Example of a successful constraint.

.. req::
   :id: FAIL_01
   :author: "Alice"
   :constraints: team

   Example of a failed constraint with medium severity. Note the style from :ref:`needs_constraint_failed_options`

.. _`needs_constraint_failed_options`:

needs_constraint_failed_options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   needs_constraint_failed_options = {
       "CRITICAL": {
           "on_fail": ["warn"],
           "style": ["red_bar"],
           "force_style": True
       },

       "HIGH": {
           "on_fail": ["warn"],
           "style": ["orange_bar"],
           "force_style": True
       },

       "MEDIUM": {
           "on_fail": ["warn"],
           "style": ["yellow_bar"],
           "force_style": False
       },

       "LOW": {
           "on_fail": [],
           "style": ["yellow_bar"],
           "force_style": False
       }
   }

needs_constraint_failed_options must be a dictionary which stores what to do if a certain constraint fails.
Dictionary keys correspond to the severity set when creating a constraint.
Each entry describes in an "on_fail" action what to do:

- "break" breaks the build process and raises a NeedsConstraintFailed Exception when a constraint is not met.
- "warn" creates a warning in the sphinx.logger if a constraint is not met. Use -W in your Sphinx build command
  to stop the whole build, if a warning is raised. This will handle all warnings as exceptions.

"style" sets the style of the failed object see :ref:`styles` for available styles. **Please be aware of conflicting styles!**

If "force style" is set, all other styles are removed and just the constraint_failed style remains.

.. _`needs_variants`:

needs_variants
~~~~~~~~~~~~~~

.. versionadded:: 1.0.2

``needs_variants`` configuration option must be a dictionary which has pre-defined variants assigned to
"filter strings". The filter string defines which variant a need belongs in the current situations.

For example, in ``conf.py``:

.. code-block:: python

   needs_variants = {
     "var_a": "'var_a' in sphinx_tags"  # filter_string
     "var_b": "assignee == 'me'"
   }

The dictionary consists of key-value pairs where the key is a string used as a reference to the value.
The value is a string which consists of a Python-supported "filter string".

Default: ``{}``

.. _`needs_variant_options`:

needs_variant_options
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.0.2

``needs_variant_options`` must be a list which consists of the options to apply :ref:`variants handling <needs_variant_support>`.
You can specify the names of the options you want to check for variants.

for example, in ``conf.py``:

.. code-block:: python

   needs_variant_options = ["author", "status"]

From the example above, we apply variants handling to only the options specified.

Default: ``[]``

.. note::

   You must ensure the options ``needs_variant_options`` are one of:

   - ``status``
   - ``layout``
   - ``style``
   - :ref:`extra options <needs_extra_options>`

.. _`needs_render_context`:

needs_render_context
~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.0.3

This option allows you to use custom data as context when rendering `Jinja <https://jinja.palletsprojects.com/>`__ templates or strings.

Configuration example:

.. code-block:: python

   def custom_defined_func():
       return "my_tag"

   needs_render_context = {
       "custom_data_1": "Project_X",
       "custom_data_2": custom_defined_func(),
       "custom_data_3": True,
       "custom_data_4": [("Daniel", 811982), ("Marco", 234232)],
   }

The``needs_render_context`` configuration option must be a dictionary.
The dictionary consists of key-value pairs where the key is a string used as reference to the value.
The value can be any data type (string, integer, list, dict, etc.)

.. warning::

   The value can also be a custom defined function,
   however, this will deactivate the caching and incremental build feature of Sphinx.

The data passed via needs_render_context will be available as variable(s) when rendering Jinja templates or strings.
You can use the data passed via needs_render_context as shown below:

.. need-example::

   .. req:: Need with jinja_content enabled
      :id: JINJA1D8913
      :jinja_content: true

      Need with alias {{ custom_data_1 }} and ``jinja_content`` option set to {{ custom_data_3 }}.

      {{ custom_data_2 }}
      {% for author in custom_data_4 %}

        * author[0]
          + author[1]

      {% endfor %}

.. _`needs_debug_measurement`:

needs_debug_measurement
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 1.3.0

Activates :ref:`runtime_debugging`, which measures the execution time of different functions and creates a helpful
JSON and HTML report.

See :ref:`runtime_debugging` for details.

To activate it, set it to ``True``::

  needs_debug_measurement = True

.. _`needs_debug_filters`:

needs_debug_filters
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 4.0.0

If set to ``True``, all calls to :ref:`filter processing <filter>` will be logged to a ``debug_filters.jsonl`` file in the build output directory,
appending a single-line JSON for each filter call.

.. _`needs_schema_definitions`:

needs_schema_definitions
~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 6.0.0

Defines validation schemas for needs using a definition format derived from JSON Schema.
Schemas can be used to validate need fields, enforce constraints, and ensure data consistency.

Default value: ``{}``

.. code-block:: python

   needs_schema_definitions = {
       "$defs": {
           "type-spec": {
               "properties": {"type": {"const": "spec"}}
           },
           "safe-need": {
               "properties": {"asil": {"enum": ["A", "B", "C", "D"]}},
               "required": ["asil"]
           }
       },
       "schemas": [
           {
               "id": "unique-id-validation",
               "severity": "warning",
               "message": "ID must be uppercase",
               "validate": {
                   "local": {
                       "properties": {
                           "id": {"pattern": "^[A-Z0-9_]+$"}
                       }
                   }
               }
           },
           {
               "id": "safe-spec",
               "validate": {
                   "local": {
                       "allOf": [
                           {"$ref": "#/$defs/type-spec"},
                           {"$ref": "#/$defs/safe-need"}
                       ]
                   }
               }
           }
       ]
   }

See :ref:`schema_validation` for detailed documentation.

.. _`needs_schema_definitions_from_json`:

needs_schema_definitions_from_json
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 6.0.0

Path to a JSON file containing schema definitions. This is the recommended approach for
defining schemas as it provides better IDE support and maintainability.

Default value: ``None``

.. code-block:: python

   needs_schema_definitions_from_json = "schemas.json"

The JSON file should contain the same structure as :ref:`needs_schema_definitions`:

.. _`needs_schema_severity`:

needs_schema_severity
~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 6.0.0

Minimum severity level for schema validation reporting.
Extra option and extra link schema errors are always reported as violations.
For each entry in :ref:`needs_schema_definitions` the severity can be defined by the user.

Available severity levels:

- ``info``: Informational message (default)
- ``warning``: Warning message
- ``violation``: Violation message

The levels align with how `SHACL <https://www.w3.org/TR/shacl/#severity>`__ defines severity levels.

Default value: ``"info"``

.. code-block:: python

   needs_schema_severity = "warning"

.. _`needs_schema_debug_active`:

needs_schema_debug_active
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 6.0.0

Activates debug mode for schema validation. When enabled, the validation dumps JSON files,
schema files, and validation messages to help troubleshoot schema validation issues.

Default value: ``False``

.. code-block:: python

   needs_schema_debug_active = True

Debug files are written to the directory specified by :ref:`needs_schema_debug_path`.

.. _`needs_schema_debug_path`:

needs_schema_debug_path
~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 6.0.0

Directory path where schema debug files are stored when :ref:`needs_schema_debug_active` is
enabled.

If the path is relative, it will be resolved relative to the ``conf.py`` directory.

Default value: ``"schema_debug"``

.. code-block:: python

   needs_schema_debug_path = "debug/schemas"

.. _`needs_schema_debug_ignore`:

needs_schema_debug_ignore
~~~~~~~~~~~~~~~~~~~~~~~~~

.. versionadded:: 6.0.0

List of validation scenarios to ignore when dumping debug information. This helps reduce
noise in debug output by filtering out irrelevant validations.

Default value::

  [
     "extra_option_success",
     "extra_link_success",
     "select_success",
     "select_fail",
     "local_success",
     "network_local_success"
  ]

.. code-block:: python

   needs_schema_debug_ignore = [
       "extra_option_success",
       "local_success",
       "network_local_success"
   ]

To write all scenarios, set it to an empty list: ``[]``.

Available scenarios that can be ignored:

- ``cfg_schema_error``: The user provided schema is invalid
- ``extra_option_success``: Global extra option validation was successful
- ``extra_option_fail``: Global extra option validation failed
- ``extra_link_success``: Global extra link validations was successful
- ``extra_link_fail``: Global extra link validation failed
- ``select_success``: Successful select validation
- ``select_fail``: Failed select validation
- ``local_success``: Successful local validation
- ``local_fail``: Need local validation failed
- ``network_missing_target``: An outgoing link target cannot be resolved
- ``network_contains_too_few``: minContains or minItems validation failed for the given link_schema link type
- ``network_contains_too_many``: maxContains or maxItems validation failed for the given link_schema link type
- ``network_items_fail``: items validation failed for the given link_schema link type
- ``network_local_success``: Successful network local validation
- ``network_local_fail``: Need does not validate against the local schema in a network context
- ``network_max_nest_level``: The maximum nesting level of network links was exceeded

The debug information is written to the directory specified by :ref:`needs_schema_debug_path`.
The ``_success`` scenarios exist to analyze why a validation was successful and how the
final need and schema looks like.

.. note::

   For large need counts, the debug output can become very large.
   Writing debug output also affects the validation performance negatively.
