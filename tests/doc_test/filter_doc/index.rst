TEST DOCUMENT
=============

.. toctree::

    filter_tags_or
    filter_all
    filter_search
    nested_needs
    filter_no_needs

Testing simple filter
---------------------

.. story:: story_a_1
   :tags: a

.. story:: story_b_1
   :tags: b
   :hide:

.. story:: story_a_b_1
   :tags: a;b

.. needlist::
   :filter: "a" in tags


Testing filter with and or
--------------------------

.. req:: req_a_1
   :tags: 1
   :hide:
   :duration: 1

.. req:: req_b_1
   :tags: 2
   :hide:

.. req:: req_c_1
   :tags: 1;2
   :duration: 1

.. needlist::
   :filter: "1" in tags and "2" in tags

Testing bad filters
-------------------

.. needlist::
   :filter: xxx

.. needlist::
   :filter: 1

.. needlist::
   :filter: yyy

.. needlist::
   :sort_by: yyy

:need_count:`zzz`
