.. _needflow:

needflow
========

.. versionadded:: 0.2.0

**needflow** creates a flowchart of filtered needs.

If you provide an argument, we use it as caption for the generated image.

.. need-example::

   .. needflow:: My first needflow
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :show_link_names:
      :config: lefttoright

.. versionadded:: 2.2.0

   You can now also set all or individual ``needflow`` directives to use the Graphviz engine for rendering the graph, which can speed up the rendering process for large amount of graphs.

   See the :ref:`needs_flow_engine` configuration option and the :ref:`directive engine option <needflow_engine>` for more information.

   .. dropdown:: Using Graphviz engine

      .. needflow:: My first needflow
         :engine: graphviz
         :filter: is_need
         :tags: flow_example
         :link_types: tests, blocks
         :show_link_names:
         :config: default,lefttoright

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

.. need-example::

   .. needflow::
      :root_id: spec_flow_002
      :root_direction: incoming
      :link_types: tests, blocks
      :show_link_names:

   .. needflow::
      :root_id: spec_flow_002
      :root_direction: outgoing
      :link_types: tests, blocks
      :show_link_names:

   .. needflow::
      :root_id: spec_flow_002
      :root_direction: outgoing
      :root_depth: 1
      :link_types: tests, blocks
      :show_link_names:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :root_id: spec_flow_002
      :root_direction: incoming
      :link_types: tests, blocks
      :show_link_names:

   .. needflow::
      :engine: graphviz
      :root_id: spec_flow_002
      :root_direction: outgoing
      :link_types: tests, blocks
      :show_link_names:

   .. needflow::
      :engine: graphviz
      :root_id: spec_flow_002
      :root_direction: outgoing
      :root_depth: 1
      :link_types: tests, blocks
      :show_link_names:

.. _needflow_show_filters:

show_filters
~~~~~~~~~~~~

Adds information of used filters below generated flowchart.

.. need-example::

   .. needflow::
      :tags: flow_example
      :show_filters:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :show_filters:

.. _needflow_show_legend:

show_legend
~~~~~~~~~~~

Adds a legend below generated flowchart. The legends contains all defined need-types and their configured color
for flowcharts.

.. need-example::

   .. needflow::
      :tags: flow_example
      :show_legend:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :show_legend:

.. _needflow_show_link_names:

show_link_names
~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

Adds the link type name beside connections.

You can configure it globally by setting :ref:`needs_flow_show_links` in **conf.py**.
Setup data can be found in test case document `tests/doc_test/doc_extra_links`.

.. need-example::

   .. needflow::
      :tags: flow_example
      :show_link_names:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :show_link_names:

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

See also :ref:`needs_extra_links` for more details about specific link types.

.. need-example::

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
      :show_link_names:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :tags: flow_example
      :link_types: tests, blocks
      :show_link_names:

.. _needflow_config:

config
~~~~~~

.. versionadded:: 0.5.2

You can specify a configuration using the ``:config:`` option but you should
set the :ref:`needs_flow_configs` configuration parameter in **conf.py**,
when using the ``plantuml`` engine,
or the :ref:`needs_graphviz_styles` configuration,
when using the ``graphviz`` engine.

.. need-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :show_link_names:
      :config: monochrome

You can apply multiple configurations together by separating them via ``,`` symbol.

.. need-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :show_link_names:
      :config: monochrome,lefttoright,handwritten

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :show_link_names:
      :config: default,lefttoright

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

You can set a scale factor for the final flow chart using the ``scale`` option.

``:scale: 50`` will set width and height to ``50%`` of the original image size.

We also support the numbers between ``1`` and ``300``.

.. need-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :scale: 50

.. _needflow_highlight:

highlight
~~~~~~~~~

.. versionadded:: 0.5.3

The ``:highlight:`` option takes a single :ref:`filter_string` as a value and
sets the border for each need of the needflow to **red** if the need also passes the filter string.

.. need-example::

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

The ``:border_color:`` allows for setting per need border colors, based on the need data.
The value should be written with the :ref:`variant syntax <needs_variant_support>`, and each return value should be a hex (RGB) color.

.. need-example::

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

.. need-example::

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

.. need-example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :config: lefttoright, handwritten
      :debug:

.. dropdown:: Using Graphviz engine

   .. needflow::
      :engine: graphviz
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :config: default,lefttoright
      :debug:

common filters
~~~~~~~~~~~~~~

* :ref:`option_status`
* :ref:`option_tags`
* :ref:`option_types`
* :ref:`option_filter`

