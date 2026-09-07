filter_all
==========

.. req:: req_a_not
   :tags: 1
   :status: open
   :hide:
   :duration: 1

.. req:: req_b_found
   :tags: 2
   :status: closed

.. req:: req_c_not
   :tags: 1;2
   :status: open
   :hide:
   :duration: 1

.. req:: req_d_found
   :tags: 1;2
   :status: closed
   :duration: 1

.. story:: story_1_not
   :tags: 3
   :status: none
   :hide:

.. story:: story_2_found
   :tags: 2
   :status: none

.. test:: my_test
   :id: my_test_id
   :tags: my_test_tag
   :status: tested

   My test content

.. needlist::
   :filter: ("1" in tags or "2" in tags) and ("story" == type or "closed" == status)

.. needlist::
   :filter: "test" in title and "test" in status and "test" in content and "TEST" in id