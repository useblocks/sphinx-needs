TEST DOCUMENT
=============

.. toctree::

    filter_tags_or
    filter_all
    filter_search

Testing simple filter
---------------------

.. story:: story_a_1
   :tags: a;

.. story:: story_b_1
   :tags: b;
   :hide:

.. story:: story_a_b_1
   :tags: a;b;

.. needfilter::
   :filter: "a" in tags


Testing filter with and or
--------------------------

.. req:: req_a_1
   :tags: 1;
   :hide:

.. req:: req_b_1
   :tags: 2;
   :hide:

.. req:: req_c_1
   :tags: 1;2;

.. needfilter::
   :filter: "1" in tags and "2" in tags