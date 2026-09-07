filter_search
=============

.. req:: search_a
   :id: AAAA
   :tags: filter_search
   :status: open

.. req:: search_b
   :id: BBB
   :tags: filter_search
   :status: closed
   :hide:

.. req:: search_c
   :id: CCC
   :tags: filter_search
   :status: open
   :hide:

.. req:: search_d
   :id: DDD
   :tags: filter_search
   :status: closed
   :hide:

.. story:: search_2_1
   :id: ABC
   :tags: filter_search
   :status: none

.. story:: search_2_2
   :id: CBA
   :tags: filter_search
   :status: none

.. test:: test_email
   :id: TEST_123
   :tags: filter_search
   :status: none

   me@myemail.com

.. needlist::
   :filter: search("A", id) and "filter_search" in tags

.. needlist::
    :filter: search(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", content) and type=="test"