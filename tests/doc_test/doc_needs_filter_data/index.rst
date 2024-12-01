Needs filter data
=================

.. story:: Story Example 1
   :id: extern_filter_story_001
   :tags: test_tag_001
   :variant: project_x
  
.. story:: Story Example 2
   :id: extern_filter_story_002
   :tags: test_tag_002
   :variant: project_y

.. test:: Test Example 3
   :id: extern_filter_test_003
   :tags: my_tag
   :links: extern_filter_story_001
   :variant: project_x

Needextract example
~~~~~~~~~~~~~~~~~~~

.. needextract::
   :filter: variant == current_variant
   :layout: clean
   :style: green_border


.. needextend:: variant == current_variant
   :+tags: current_variant

Needcount example
~~~~~~~~~~~~~~~~~

The amount of needs that belong to current variants: :need_count:`variant==current_variant`

Needpie Example
~~~~~~~~~~~~~~~

.. needpie:: My Pie
   :labels: project_x, project_y

   variant == current_variant
   variant != current_variant

Needtable example
~~~~~~~~~~~~~~~~~

.. needtable:: Example table
   :filter: sphinx_tag in tags
   :style: table

Needlist example
~~~~~~~~~~~~~~~~

.. needlist::
   :filter: sphinx_tag in tags

Needflow example
~~~~~~~~~~~~~~~~

.. needflow:: My needflow
   :filter: variant == current_variant


.. toctree::

   filter_code
   filter_code_args
