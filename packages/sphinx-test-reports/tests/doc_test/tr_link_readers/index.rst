tr_link readers
===============

.. req:: Req A
   :id: REQ_A
   :covers: [[links_from_filter("type == 'test' and 'REQ_A' in links")]]
   :cov_u: [[links_from_filter("'REQ_A' in all_links")]]

.. req:: Req B
   :id: REQ_B
   :covers: [[links_from_filter("type == 'test' and 'REQ_B' in links")]]

.. test:: Test 1
   :id: TEST_1
   :classname: REQ_A
   :links: [[tr_link('classname', 'id')]]

.. test:: Test 2
   :id: TEST_2
   :classname: REQ_B
   :links: [[tr_link('classname', 'id')]]

.. test:: Test 3
   :id: TEST_3
   :classname: REQ_A, REQ_B
   :links: [[tr_link('classname', 'id')]]
