.. _needflow:

needflow
========

.. versionadded:: 0.2.0

**needflow** creates a flowchart of filtered needs.

If you provide an argument, we use it as caption for the generated image.

.. syntax-example::

   .. needflow:: My first needflow
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :link_labels: outgoing
      :direction: right

.. versionadded:: 2.2.0

   You can now also set all or individual ``needflow`` directives to use the Graphviz engine for rendering the graph, which can speed up the rendering process for large amount of graphs.

   See the :ref:`needs_flow_engine` configuration option and the :ref:`directive engine option <needflow_engine>` for more information.

   .. dropdown:: Using Graphviz engine

      .. needflow:: My first needflow
         :engine: graphviz
         :filter: is_need
         :tags: flow_example
         :link_types: tests, blocks
         :link_labels: outgoing
         :direction: right

Dependencies
------------

plantuml
~~~~~~~~

``needflow``, with the default ``plantuml`` engine, uses `PlantUML <http://plantuml.com>`_ and the
Sphinx-extension `sphinxcontrib-plantuml <https://pypi.org/project/sphinxcontrib-plantuml/>`_ for generating the flows.

Both must be available and correctly configured to work.

Please read :ref:`install plantuml <install_plantuml>` for a step-by-step installation explanation.

graphviz
~~~~~~~~

``needflow``, with the ``graphviz`` engine uses the `Graphviz dot <https://graphviz.org/>`_ executable for rendering the flowchart,
and the built-in :any:`sphinx.ext.graphviz` extension from Sphinx.

See https://graphviz.org/download/ for how to install Graphviz,
and :any:`sphinx.ext.graphviz` for configuration options.
In particular, you may want to set the ``graphviz_output_format`` configuration option in your ``conf.py``.

Options
-------

.. note::

   **needflow** supports the full filtering possibilities of **Sphinx-Needs**.
   Please see :ref:`filter` for more information.

Some further options are accepted only for :ref:`ubCode compatibility <ubcode_compat_options>`, and are otherwise ignored.

.. _needflow_engine:

engine
~~~~~~

.. versionadded:: 2.3.0

You can set the engine to use for rendering the flowchart,
to either ``plantuml`` (default) or ``graphviz``.

.. _needflow_root_id:
.. _needflow_root_direction:
.. _needflow_root_depth:

.. _needflow_alt:

alt
~~~

.. versionadded:: 2.3.0

Set the ``alt`` option to a string to add an alternative text to the generated image.

If the option is not set, the graphviz engine describes the image as
``needflow graphviz diagram``.
Set the option to an empty value to publish an empty alternative text instead,
for a diagram that is purely decorative.

root_id
~~~~~~~

.. versionadded:: 2.2.0

To select a root need for the flowchart and its connected needs, you can use the ``:root_id:`` option.
This takes the id of the need you want to use as the root,
and then traverses the tree of connected needs, to create an initial selection of needs to show in the flowchart.

Connections are limited by the link types you have defined in the ``:link_types:`` option, or all link types if not defined.
The direction of connections can be set with the ``:root_direction:`` option:
``both`` (default), ``incoming`` or ``outgoing``.

If ``:root_depth:`` is set, only needs with a distance of ``root_depth`` to the root need are shown.

Other need filters are applied on this initial selection of connected needs.

.. syntax-example::

   .. needflow::
      :root_id: spec_flow_002
      :root_direction: incoming
      :link_types: tests, blocks
      :link_labels: outgoing

   .. needflow::
      :root_id: spec_flow_002
      :root_direction: outgoing
      :link_types: tests, blocks
      :link_labels: outgoing

   .. needflow::
      :root_id: spec_flow_002
      :root_direction: outgoing
      :root_depth: 1
      :link_types: tests, blocks
      :link_labels: outgoing

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :root_id: spec_flow_002
      :root_direction: incoming
      :link_types: tests, blocks
      :link_labels: outgoing

   .. needflow::
      :engine: graphviz
      :root_id: spec_flow_002
      :root_direction: outgoing
      :link_types: tests, blocks
      :link_labels: outgoing

   .. needflow::
      :engine: graphviz
      :root_id: spec_flow_002
      :root_direction: outgoing
      :root_depth: 1
      :link_types: tests, blocks
      :link_labels: outgoing

.. _needflow_show_filters:

show_filters
~~~~~~~~~~~~

Adds information of used filters below generated flowchart.

.. syntax-example::

   .. needflow::
      :tags: flow_example
      :show_filters:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :show_filters:

.. _needflow_legend:

legend
~~~~~~

.. versionadded:: 8.4.0

Describes the diagram in a table beside it,
listing only what the diagram actually drew.
The value is a comma separated list of ``types``, ``links``, or both;
give the option without a value to draw no legend at all,
which is how a single diagram opts out of :ref:`needs_flow_legend`.

The legend is a document table rather than part of the picture,
so it looks the same on every engine, its text is selectable and searchable,
and it can describe link types -- which no in-diagram legend ever could.

.. syntax-example::

   .. needflow::
      :tags: flow_example
      :legend: types,links

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :legend: types,links

.. _needflow_link_labels:

link_labels
~~~~~~~~~~~

.. versionadded:: 8.4.0

Chooses what each connection is labelled with:

``none``
   Nothing (the default).
``outgoing``
   The outgoing title of the link type, e.g. ``links outgoing``.
``incoming``
   The incoming title of the link type, e.g. ``links incoming``.
``type``
   The bare link field name, e.g. ``links``,
   for a diagram that wants the data model rather than prose.

You can set the project default with :ref:`needs_flow_link_labels` in **conf.py**.
Because the option has four values rather than two,
a single diagram can always turn labels off again,
which the flag it replaces could not express.

.. syntax-example::

   .. needflow::
      :tags: flow_example
      :link_labels: outgoing

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :link_labels: outgoing

.. _needflow_link_types:

link_types
~~~~~~~~~~

.. versionadded:: 0.3.11

Defines the link types to show in the needflow.
Must contain a comma separated list of link type names.

.. code-block:: rst

    .. needflow::
       :link_types: links,blocks


By default, we show all link_types.

An identical link can show up twice in the generated needflow, if the ``copy``
option of a specific link type was set to ``True``.

In this case, the link_type **"link"** also contains the copies of the specified link_type and therefore
there will be two identical connections in the needflow.
You can avoid this by not setting **"links**" in the ``link_type`` option.

You can set this option globally via the configuration option :ref:`needs_flow_link_types`.

See also :ref:`needs_links` for more details about specific link types.

.. syntax-example::

   .. req:: A requirement
      :id: req_flow_001
      :tags: flow_example

   .. spec:: A specification
      :id: spec_flow_001
      :blocks: req_flow_001
      :tags: flow_example

      :need_part:`(subspec_1)A testable part of the specification`

      :need_part:`(subspec_2)Another testable part of the specification`

      .. spec:: A child specification
         :id: spec_flow_003
         :blocks: req_flow_001
         :tags: flow_example

   .. spec:: Another specification
      :id: spec_flow_002
      :links: req_flow_001
      :blocks: spec_flow_001
      :tags: flow_example

   .. test:: A test case
      :id: test_flow_001
      :tests: spec_flow_002, spec_flow_001.subspec_1, spec_flow_001.subspec_2
      :tags: flow_example

   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :link_labels: outgoing

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :link_types: tests, blocks
      :link_labels: outgoing

.. _needflow_direction:

direction
~~~~~~~~~

.. versionadded:: 8.4.0

Sets the direction the diagram flows in:
``down`` (the default), ``up``, ``right`` or ``left``.
The tokens ``TB``, ``TD``, ``BT``, ``LR`` and ``RL`` are accepted as aliases,
so a habit picked up from Graphviz or Mermaid does not have to be unlearned.

You can set the project default with :ref:`needs_flow_direction` in **conf.py**.

Not every engine can draw every direction.
PlantUML has no bottom-up or right-left layout at all,
so ``up`` is drawn ``down`` and ``left`` is drawn ``right``,
with one warning per project;
Graphviz draws all four.
A diagram is never refused for asking:
a plainer diagram is better than a failed build.

.. syntax-example::

   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :direction: right

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :link_types: tests, blocks
      :direction: right

.. _needflow_styles:

styles
~~~~~~

.. versionadded:: 8.4.0

Applies named style classes to the needs a filter selects.
Each rule is written ``[<filter>]:<class>``,
in the same variant syntax used elsewhere in **Sphinx-Needs**,
and several rules are separated by commas;
a class written without a filter applies to every need.

The classes themselves live in :ref:`needs_flow_styles` in **conf.py**,
so a rule says *which* needs look different and the configuration says *how*.
Rules cascade the way CSS declarations do:
every matching rule contributes,
and a later one overrides an earlier one property by property.

One class is built in.
``highlight`` draws the red outline that the deprecated ``:highlight:``
option has always drawn, so moving from the option to the class changes nothing.

.. syntax-example::

   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :styles: [type == 'req']:highlight

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :link_types: tests, blocks
      :styles: [type == 'req']:highlight

.. _needflow_engine_config:
.. _needflow_config:

engine_config
~~~~~~~~~~~~~

.. versionadded:: 8.4.0

.. deprecated:: 8.4.0
   The ``:config:`` spelling of this option is deprecated.
   Use ``:engine_config:``, which selects from the same registries.

Selects engine specific customisation by name.
This is the one deliberate way out of the portable vocabulary,
and it is meant to be used sparingly:
everything else on this page means the same thing on every engine,
whereas an engine config is written in one engine's own syntax.

The customisation lives in :ref:`needs_flow_engine_config` in **conf.py**,
under the engine it belongs to,
so the *document* stays portable even when the *project* chooses not to be.
The older :ref:`needs_flow_configs` (plantuml) and :ref:`needs_graphviz_styles`
(graphviz) registries are still read under exactly the same names and values,
so nothing has to move.

An engine config is a preamble of defaults:
where it and a portable option disagree, the option wins.

.. syntax-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :link_labels: outgoing
      :engine_config: monochrome

You can apply multiple configurations together by separating them via ``,`` symbol.

.. syntax-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :link_labels: outgoing
      :direction: right
      :engine_config: monochrome,handwritten

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :link_labels: outgoing
      :direction: right
      :engine_config: default

**Sphinx-Needs** provides some necessary configurations already.

For ``needs_flow_configs`` they are:

.. list-table::
   :header-rows: 1
   :widths: 30,70

   - * config name
     * description
   - * mixing
     * Allows mixing of different PlantUML diagram types (e.g. Class and Deploy diagrams)
   - * monochrome
     * Changes all colors to monochrome colors
   - * handwritten
     * All lines look like they were handwritten (squiggly)
   - * lefttoright
     * Direction of boxes is left to right
   - * toptobottom
     * Direction of boxes is top to bottom (PlantUML default value)
   - * transparent
     * Transparent background
   - * tne
     * Tomorrow night eighties theme. Look `here <https://github.com/gabrieljoelc/plantuml-themes>`_ for example.
   - * cplant
     * Cplant theme. Read `this <https://github.com/aoki/cplant>`_ for example.

For ``needs_graphviz_styles`` they are:

.. list-table::
   :header-rows: 1
   :widths: 30,70

   - * config name
     * description
   - * default
     * Default style used when ``config`` is not set
   - * lefttoright
     * Direction of boxes is left to right
   - * toptobottom
     * Direction of boxes is top to bottom (default value)
   - * transparent
     * Transparent background

.. _needflow_scale:

scale
~~~~~

.. versionadded:: 0.5.3

.. deprecated:: 8.4.0
   ``:scale:`` sizes a raster image, which the ``graphviz`` engine has always
   ignored silently, so the same option never meant the same thing on both engines.
   Use ``:width:`` / ``:height:`` instead.
   It is still honoured by the ``plantuml`` engine.

You can set a scale factor for the final flow chart using the ``scale`` option.

``:scale: 50`` will set width and height to ``50%`` of the original image size.

We also support the numbers between ``1`` and ``300``.

.. syntax-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :scale: 50

.. _needflow_highlight:

highlight
~~~~~~~~~

.. versionadded:: 0.5.3

.. deprecated:: 8.4.0
   Use :ref:`styles <needflow_styles>` with the built-in ``highlight`` class instead,
   e.g. ``:styles: [type == 'req']:highlight``, which draws exactly the same outline.
   ``:highlight:`` is still honoured.

The ``:highlight:`` option takes a single :ref:`filter_string` as a value and
sets the border for each need of the needflow to **red** if the need also passes the filter string.

.. syntax-example::

   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :highlight: id in ['spec_flow_002', 'subspec_2'] or type == 'req'

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :link_types: tests, blocks
      :highlight: id in ['spec_flow_002', 'subspec_2'] or type == 'req'

.. _needflow_border_color:

border_color
~~~~~~~~~~~~

.. versionadded:: 3.0.0

.. deprecated:: 8.4.0
   Use :ref:`styles <needflow_styles>` with a class setting ``border`` instead,
   which says the same thing and can set the rest of a need's presentation too.
   ``:border_color:`` is still honoured.

The ``:border_color:`` allows for setting per need border colors, based on the need data.
The value should be written with the :ref:`variant syntax <needs_variant_support>`, and each return value should be a hex (RGB) color.

.. syntax-example::

   .. needflow:: Engineering plan to develop a car
      :tags: flow_example
      :link_types: tests, blocks
      :border_color:
         [type == 'req']:FF0000,
         [type == 'spec']:0000FF,
         [type == 'test']:00FF00

.. dropdown:: Using Graphviz engine

   .. needflow:: Engineering plan to develop a car
      :engine: graphviz
      :tags: flow_example
      :link_types: tests, blocks
      :border_color:
         [type == 'req']:FF0000,
         [type == 'spec']:0000FF,
         [type == 'test']:00FF00

.. _needflow_align:

align
~~~~~

You can set the alignment for the PlantUML image using the ``align`` option.
Allowed values are: ``left``, ``center``, ``right``

.. syntax-example::

   .. needflow::
      :filter: is_need and type == 'spec'
      :tags: flow_example
      :align: center

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :filter: is_need and type == 'spec'
      :tags: flow_example
      :align: center

.. _needflow_debug:

debug
~~~~~

.. versionadded:: 0.5.2

If you set the ``:debug:``, we add a debug-output of the generated PlantUML code after the generated image.

Helpful to identify reasons why a PlantUML build may have thrown errors.

.. syntax-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :direction: right
      :engine_config: handwritten
      :debug:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :direction: right
      :engine_config: default
      :debug:

.. _needflow_max_items:

max_items
~~~~~~~~~

.. versionadded:: 8.4.0

The maximum number of needs to show, applied identically by both engines.

We apply the limit after filtering and sorting, so the diagram keeps the first needs it would otherwise have shown,
and tells the reader how many needs it is hiding.
A truncated view says so in the page and emits a ``needs.max_items`` warning,
so that a build does not have to be read page by page to find it;
a project that caps deliberately can silence the warning with
``suppress_warnings = ["needs.max_items"]``.
The limit counts the entries the filter returned, which are needs and need parts alike.
Since the limit is applied before the diagram is built,
a link to a dropped need is not drawn at all,
and a need whose parent was dropped is drawn as a root instead of nested.

``:max_items: 0`` means no limit, also for a project that sets :ref:`needs_views_max_items`.
Without the option, the diagram shows as many needs as that configuration allows.

.. syntax-example::

   .. needflow::
      :tags: flow_example
      :max_items: 2

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :max_items: 2

common filters
~~~~~~~~~~~~~~

* :ref:`option_status`
* :ref:`option_tags`
* :ref:`option_types`
* :ref:`option_filter`


.. _needflow_legacy_options:

Legacy options
--------------

These options still work, and will keep working,
but each has a portable replacement above that means the same thing on every engine.
Using one emits a ``needs.deprecated`` warning naming the replacement.

.. _needflow_show_legend:

show_legend
~~~~~~~~~~~

.. deprecated:: 8.4.0
   Use :ref:`legend <needflow_legend>` instead.

Adds a legend inside the generated image,
listing need types and their configured colors.
Its rendering differs between the two engines --
``plantuml`` lists every configured need type and ``graphviz`` only the drawn ones --
which is exactly why :ref:`legend <needflow_legend>` exists.
That difference is deliberately left as it is,
so no existing diagram changes.

.. code-block:: rst

   .. needflow::
      :tags: flow_example
      :show_legend:

.. _needflow_show_link_names:

show_link_names
~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

.. deprecated:: 8.4.0
   Use ``:link_labels: outgoing``, see :ref:`link_labels <needflow_link_labels>`.

Adds the link type name beside connections.
Equivalent to ``:link_labels: outgoing``.

.. code-block:: rst

   .. needflow::
      :tags: flow_example
      :show_link_names:

