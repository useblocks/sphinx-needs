DYNAMIC FUNCTIONS
=================

.. spec:: TEST_1
    :id: TEST_1
    :status: done

.. spec:: TEST_2
   :id: TEST_2
   :status: done

.. spec:: TEST_3
   :id: TEST_3
   :status: open

.. spec:: Result 1
   :links: TEST_1, TEST_2
   :status: [[check_linked_values('all_good', 'status', 'done')]]

.. spec:: Result 2
   :links: TEST_1, TEST_2, TEST_3
   :status: [[check_linked_values('all_bad', 'status', 'done')]]

.. spec:: Result 3
   :links: TEST_1, TEST_2, TEST_3
   :status: [[check_linked_values('all_awesome', 'status', 'done', one_hit=True)]]
