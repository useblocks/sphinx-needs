filter_tags_or
==============

Testing filter with and or
--------------------------

.. req:: req_a
   :tags: 1;
   :hide:

.. req:: req_b
   :tags: 2;
   :hide:

.. req:: req_c
   :tags: 1;2;
   :hide:

.. needfilter::
   :filter: "1" in tags or "2" in tags
