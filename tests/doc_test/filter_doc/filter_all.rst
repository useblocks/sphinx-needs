filter_all
==========

.. req:: req_a_not
   :tags: 1;
   :status: open
   :hide:

.. req:: req_b_found
   :tags: 2;
   :status: closed
   :hide:

.. req:: req_c_not
   :tags: 1;2;
   :status: open
   :hide:

.. req:: req_d_found
   :tags: 1;2;
   :status: closed
   :hide:

.. story:: story_1_not
   :tags: 3;
   :status: none
   :hide:

.. story:: story_2_found
   :tags: 2;
   :status: none
   :hide:

.. needfilter::
   :filter: ("1" in tags or "2" in tags) and ("story" in type or "closed" in status)
