filter_tags_or
==============

Testing filter with and or
--------------------------

.. req:: req_a
   :tags: 1
   :duration: 1

.. req:: req_b
   :tags: 2

.. req:: req_c
   :tags: 1;2
   :duration: 1

.. needlist::
   :filter: "1" in tags or "2" in tags
