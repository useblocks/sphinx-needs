TEST DOCUMENT c.this_doc() in charts
====================================

.. story:: Story 1
    :id: INDEX_1

.. story:: Story 2
    :id: INDEX_2

index_count-:need_count:`c.this_doc()`

index_ratio_a-:need_count:`c.this_doc() ? True`

index_ratio_b-:need_count:`True ? c.this_doc()`

.. needpie:: Index pie

   c.this_doc()

.. needbar:: Index bar

   c.this_doc()

.. needpie:: Index scoped pie
   :filter: c.this_doc()

   type == 'story'
   1

.. toctree::

   page
