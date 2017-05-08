TEST DOCUMENT
=============

.. toctree::

    filter_tags_or
    filter_all

Testing simple filter
---------------------

.. story:: story_a
   :tags: a;
   :hide:

.. story:: story_b
   :tags: b;
   :hide:

.. story:: story_a_b
   :tags: a;b;
   :hide:

.. needfilter::
   :filter: "a" in tags


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
   :filter: "1" in tags and "2" in tags