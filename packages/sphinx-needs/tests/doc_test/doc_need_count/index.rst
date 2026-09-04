NEED PARTS
==========

.. spec:: TEST_1
   :id: TEST_1
   :tags: A

.. spec:: TEST_2
   :id: TEST_2
   :tags: A

.. spec:: TEST_3
   :id: TEST_3
   :tags: A, B

.. spec:: TEST_4
   :id: TEST_4
   :tags: B


result_1-:need_count:`"A" in tags`

result_2-:need_count:`"B" in tags`

result_3-:need_count:`True`

result_4-:need_count:`"A" in tags ? "B" in tags`

result_5-:need_count:`"A" in tags ? "X" in tags`
