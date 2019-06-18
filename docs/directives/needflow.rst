.. _needflow:

needflow
========

.. versionadded:: 0.2.0

**needflow** creates a flowchart of filtered needs.

{% if READTHEDOCS %}

.. code-block:: rst

   .. needflow::
      :tags: main_example

.. image:: /_static/needflow_flow.png

{% else %}

.. code-block:: rst

   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :show_link_names:

.. needflow::
   :tags: flow_example
   :link_types: tests, blocks
   :show_link_names:

{% endif %}

Options
-------

.. note:: **needflow** supports the full filtering possibilities of sphinx-needs.
          Please see :ref:`filter` for more information.

Supported options:

 * :ref:`needflow_show_filters`
 * :ref:`needflow_show_legend`
 * :ref:`needflow_show_link_names`
 * :ref:`needflow_link_types`
 * Common filters:
    * :ref:`option_status`
    * :ref:`option_tags`
    * :ref:`option_types`
    * :ref:`option_filter`


.. _needflow_show_filters:

show_filters
~~~~~~~~~~~~

Adds information of used filters below generated flowchart.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needflow::
         :tags: main_example
         :show_filters:

   {% if READTHEDOCS %}

   .. image:: /_static/needflow_flow.png

   {% else %}

   .. needflow::
      :tags: main_example
      :show_filters:

   {% endif %}


.. _needflow_show_legend:

show_legend
~~~~~~~~~~~

Adds a legend below generated flowchart. The legends contains all defined need-types and their configured color
for flowcharts.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needflow::
         :tags: main_example
         :show_legend:



   {% if READTHEDOCS %}

   .. image:: /_static/needflow_flow_legend.png

   {% else %}

   .. needflow::
      :tags: main_example
      :show_legend:

   {% endif %}

.. _needflow_show_link_names:

show_link_names
~~~~~~~~~~~~~~~

.. versionadded:: 0.3.11

Adds the link type name beside connections.

Can be configured globally by setting :ref:`needs_flow_show_links` in ``conf.py``.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needflow::
         :show_legend:
         :show_link_names:

   Setup data can be found in test case document `tests/doc_test/doc_extra_links`

   .. image:: /_static/needflow_link_names.png

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


.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. req:: A requirement
         :hide:
         :id: req_flow_001
         :tags: flow_example

      .. spec:: A specification
         :hide:
         :id: spec_flow_001
         :blocks: req_flow_001
         :tags: flow_example

         :need_part:`(subspec_1)A testable part of the specification`

         :need_part:`(subspec_2)Another testable part of the specification`

      .. spec:: Another specification
         :hide:
         :id: spec_flow_002
         :links: req_flow_001
         :blocks: spec_flow_001
         :tags: flow_example

      .. test:: A test case
         :hide:
         :id: test_flow_001
         :tests: spec_flow_002, spec_flow_001.subspec_1, spec_flow_001.subspec_2
         :tags: flow_example


      .. needflow::
         :tags: flow_example
         :link_types: tests, blocks
         :show_link_names:

   .. req:: A requirement
      :hide:
      :id: req_flow_001
      :tags: flow_example

   .. spec:: A specification
      :hide:
      :id: spec_flow_001
      :blocks: req_flow_001
      :tags: flow_example

      :need_part:`(subspec_1)A testable part of the specification`

      :need_part:`(subspec_2)Another testable part of the specification`

   .. spec:: Another specification
      :hide:
      :id: spec_flow_002
      :links: req_flow_001
      :blocks: spec_flow_001
      :tags: flow_example

   .. test:: A test case
      :hide:
      :id: test_flow_001
      :tests: spec_flow_002, spec_flow_001.subspec_1, spec_flow_001.subspec_2
      :tags: flow_example


   .. needflow::
      :tags: flow_example
      :link_types: tests, blocks
      :show_link_names:
