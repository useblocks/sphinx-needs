.. _needflow:

needflow
========

.. versionadded:: 0.2.0

**needflow** creates a flowchart of filtered needs.

If an argument is provided, this is taken as caption for the generated image.

.. code-block:: rst

   .. needflow:: My first needflow
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :show_link_names:

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

.. note:: **needflow** supports the full filtering possibilities of sphinx-needs.
          Please see :ref:`filter` for more information.

Supported options:

 * :ref:`needflow_show_filters`
 * :ref:`needflow_show_legend`
 * :ref:`needflow_show_link_names`
 * :ref:`needflow_link_types`
 * :ref:`needflow_config`
 * :ref:`needflow_scale`
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


.. code-block:: rst

   .. needflow::
      :tags: main_example
      :show_filters:


.. needflow::
   :tags: main_example
   :show_filters:


.. _needflow_show_legend:

show_legend
~~~~~~~~~~~

Adds a legend below generated flowchart. The legends contains all defined need-types and their configured color
for flowcharts.

.. code-block:: rst

   .. needflow::
      :tags: main_example
      :show_legend:

.. needflow::
   :tags: main_example
   :show_legend:

.. _needflow_show_link_names:

show_link_names
~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

Adds the link type name beside connections.

Can be configured globally by setting :ref:`needs_flow_show_links` in ``conf.py``.


.. code-block:: rst

   .. needflow::
      :tags: main_example
      :show_link_names:

Setup data can be found in test case document `tests/doc_test/doc_extra_links`

.. needflow::
   :tags: main_example
   :show_link_names:

.. _needflow_link_types:

link_types
~~~~~~~~~~

.. versionadded:: 0.3.11

Defines which link types shall be shown in the needflow.
Must contain a comma separated list of link_typ option names::

    .. needflow::
       :link_types: links,blocks


By default all link_types are shown.

An identical link can show up twice in the generated needflow, if the ``copy``
option of a specific link type was set to ``True``.
In this case the link_type **"link"** contains also the copies of the specified link_type and therefore
there will be two identical connections in the needflow.
You can avoid this by not setting **"links**" in the ``link_type`` option.

This option can be set globally via configuration option :ref:`needs_flow_link_types`.

See also :ref:`needs_extra_links` for more details about specific link types.

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

Allows to specify a configuration, which must be provided by setting :ref:`needs_flow_configs`.

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :show_link_names:
      :config: monochrome

.. needflow::
   :filter: is_need
   :tags: flow_example
   :types: spec
   :link_types: tests, blocks
   :show_link_names:
   :config: monochrome

Multiple configurations can be set together by separating them via ``,``.

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :types: spec
      :link_types: tests, blocks
      :show_link_names:
      :config: monochrome,lefttoright,handwritten

.. needflow::
   :filter: is_need
   :tags: flow_example
   :types: spec
   :link_types: tests, blocks
   :show_link_names:
   :config: monochrome,lefttoright,handwritten

``Sphinx-Needs`` provides already some useful configurations:

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

``scale`` allows to set a scale factor for the final flow chart.

``:scale: 50`` will set width and height to ``50%`` of the original image size.

Numbers between ``1`` and ``300`` are supported.

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :scale: 50

.. needflow::
   :filter: is_need
   :tags: flow_example
   :link_types: tests, blocks
   :scale: 50

.. _needflow_highlight:

highlight
~~~~~~~~~

.. versionadded:: 0.5.3

``highlight`` takes a single :ref:`filter_string` as value and sets the border to **red** for each need of the needflow,
which also passes the given filter string.

.. code-block:: rst

   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :highlight: id in ['spec_flow_002', 'subspec_2'] or type == 'req'

.. needflow::
   :tags: flow_example
   :link_types: tests, blocks
   :highlight: id in ['spec_flow_002', 'subspec_2'] or type == 'req'

.. _needflow_align:

align
~~~~~

Set ``align`` value for PlantUML image.
Allowed values are: ``left``, ``center``, ``right``

.. code-block:: rst

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :align: center

.. needflow::
   :filter: is_need and type == 'spec'
   :tags: flow_example
   :align: center

.. _needflow_debug:

debug
~~~~~

.. versionadded:: 0.5.2

If ``debug`` is set, a debug-output of the generated PlantUML code gets added after the generated image.

Helpful to identify reasons why a PlantUML build may have thrown errors.

Example::

   .. needflow::
      :filter: is_need
      :tags: flow_example
      :link_types: tests, blocks
      :config:  lefttoright, handwritten
      :debug:

.. needflow::
   :filter: is_need
   :tags: flow_example
   :link_types: tests, blocks
   :config:  lefttoright, handwritten
   :debug:

