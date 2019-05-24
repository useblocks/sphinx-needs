.. _needflow:

needflow
========

.. versionadded:: 0.2.0

**needflow** creates a flowchart of filtered needs.


.. code-block:: rst

   .. needflow::
      :tags: main_example

{% if READTHEDOCS %}

.. image:: /_static/needflow_flow.png

{% else %}

.. needflow::
   :tags: main_example

{% endif %}

Options
-------

.. note:: **needflow** supports the full filtering possibilities of sphinx-needs.
          Please see :ref:`filter` for more information.

Supported options:

 * :ref:`needflow_show_filters`
 * :ref:`needflow_show_legend`
 * :ref:`needflow_show_link_names`
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
