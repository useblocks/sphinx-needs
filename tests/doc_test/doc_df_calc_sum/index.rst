DYNAMIC FUNCTIONS
=================

.. spec:: TEST_1
    :id: TEST_1
    :hours: 10

.. spec:: TEST_2
   :id: TEST_2
   :hours: 200

.. spec:: TEST_3
   :id: TEST_3
   :hours: 3000

.. spec:: TEST_4
   :id: TEST_4
   :hours: 40000

.. spec:: Result 1
   :amount: [[calc_sum('hours')]]

.. spec:: Result 2
   :links: TEST_1,TEST_2,TEST_3
   :amount: [[calc_sum('hours', links_only=True)]]

.. spec:: Result 3
   :amount: [[calc_sum('hours', filter='id in ["TEST_1","TEST_2"]')]]