.. _needflow:

needflow
========

.. versionadded:: 0.2.0

**needflow** creates a flowchart of filtered needs.

If you provide an argument, we use it as caption for the generated image.

|ex|

.. code-block:: rst

   .. needflow:: My first needflow
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :show_link_names:

|out|

.. needflow:: My first needflow
   :filter: is_need
   :tags: flow_example
   :link_types: tests, blocks
   :show_link_names:

Dependencies
------------

``needflow`` uses `PlantUML <http://plantuml.com>`_ and the
Sphinx-extension `sphinxcontrib-plantuml <https://pypi.org/project/sphinxcontrib-plantuml/>`_ for generating the flows.

Both must be available and correctly configured to work.

Please read :ref:`install_plantuml` for a step-by-step installation explanation.

Options
-------

.. note::

   **needflow** supports the full filtering possibilities of **Sphinx-Needs**.
   Please see :ref:`filter` for more information.

Supported options:

* :ref:`needflow_show_filters`
* :ref:`needflow_show_legend`
* :ref:`needflow_show_link_names`
* :ref:`needflow_link_types`
* :ref:`needflow_config`
* :ref:`needflow_scale`
* :ref:`needflow_align`
* :ref:`needflow_highlight`
* :ref:`needflow_debug`
* Common filters:
    * :ref:`option_status`
    * :ref:`option_tags`
    * :ref:`option_types`
    * :ref:`option_filter`


.. _needflow_show_filters:

show_filters
~~~~~~~~~~~~

Adds information of used filters below generated flowchart.

|ex|

.. code-block:: rst

   .. needflow::
      :tags: main_example
      :show_filters:

|out|

.. needflow::
   :tags: main_example
   :show_filters:


.. _needflow_show_legend:

show_legend
~~~~~~~~~~~

Adds a legend below generated flowchart. The legends contains all defined need-types and their configured color
for flowcharts.

|ex|

.. code-block:: rst

   .. needflow::
      :tags: main_example
      :show_legend:

|out|

.. needflow::
   :tags: main_example
   :show_legend:

.. _needflow_show_link_names:

show_link_names
~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

Adds the link type name beside connections.

You can configure it globally by setting :ref:`needs_flow_show_links` in **conf.py**.

|ex|

.. code-block:: rst

   .. needflow::
      :tags: main_example
      :show_link_names:

Setup data can be found in test case document `tests/doc_test/doc_extra_links`

|out|

.. needflow::
   :tags: main_example
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

|ex|

.. code-block:: rst

   .. req:: A requirement
      :id: req_flow_001
      :tags: flow_example

   .. spec:: A specification
      :id: spec_flow_001
      :blocks: req_flow_001
      :tags: flow_example

      :need_part:`(subspec_1)A testable part of the specification`

      :need_part:`(subspec_2)Another testable part of the specification`

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

|out|

.. req:: A requirement
   :id: req_flow_001
   :tags: flow_example

.. spec:: A specification
   :id: spec_flow_001
   :blocks: req_flow_001
   :tags: flow_example

   :need_part:`(subspec_1)A testable part of the specification`

   :need_part:`(subspec_2)Another testable part of the specification`

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

.. _needflow_config:

config
~~~~~~

.. versionadded:: 0.5.2

You can specify a configuration using the ``:config:`` option but you should
set the :ref:`needs_flow_configs` configuration parameter in **conf.py**.

|ex|

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :show_link_names:
      :config: monochrome

|out|

.. needflow::
   :filter: is_need
   :tags: flow_example
   :types: spec
   :link_types: tests, blocks
   :show_link_names:
   :config: monochrome

You can apply multiple configurations together by separating them via ``,`` symbol.

|ex|

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :show_link_names:
      :config: monochrome,lefttoright,handwritten

|out|

.. needflow::
   :filter: is_need
   :tags: flow_example
   :types: spec
   :link_types: tests, blocks
   :show_link_names:
   :config: monochrome,lefttoright,handwritten

``Sphinx-Needs`` provides some necessary configurations already. They are:

.. list-table::
   :header-rows: 1
   :widths: 30,70

   - * config name
     * description
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

.. _needflow_scale:

scale
~~~~~

.. versionadded:: 0.5.3

You can set a scale factor for the final flow chart using the ``scale`` option.

``:scale: 50`` will set width and height to ``50%`` of the original image size.

We also support the numbers between ``1`` and ``300``.

|ex|

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :scale: 50

|out|

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

|ex|

.. code-block:: rst

   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :highlight: id in ['spec_flow_002', 'subspec_2'] or type == 'req'

|out|

.. needflow::
   :tags: flow_example
   :link_types: tests, blocks
   :highlight: id in ['spec_flow_002', 'subspec_2'] or type == 'req'

.. _needflow_align:

align
~~~~~

You can set the alignment for the PlantUML image using the ``align`` option.
Allowed values are: ``left``, ``center``, ``right``

|ex|

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :align: center

|out|

.. needflow::
   :filter: is_need and type == 'spec'
   :tags: flow_example
   :align: center

.. _needflow_debug:

debug
~~~~~

.. versionadded:: 0.5.2

If you set the ``:debug:``, we add a debug-output of the generated PlantUML code after the generated image.

Helpful to identify reasons why a PlantUML build may have thrown errors.

|ex|

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :config:  lefttoright, handwritten
      :debug:

|out|

.. needflow::
   :filter: is_need
   :tags: flow_example
   :link_types: tests, blocks
   :config:  lefttoright, handwritten
   :debug:

