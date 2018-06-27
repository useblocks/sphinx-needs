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

   .. needflow::
         :tags: main_example
         :show_filters:


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

   .. needflow::
         :tags: main_example
         :show_legend:


