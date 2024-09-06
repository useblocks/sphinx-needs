DYNAMIC FUNCTIONS
=================

.. spec:: Command line interface
    :id: SP_TOO_001
    :status: implemented
    :tags: test;test2

    This is id [[copy("id")]]

    This is also id :need_func:`[[copy("id")]]`

.. spec:: TEST_2
   :id: TEST_2
   :tags: my_tag; [[copy("tags", "SP_TOO_001")]]

.. spec:: TEST_3
   :id: TEST_3
   :test_func: [[test()]]

.. spec:: TEST_4
    :id: TEST_4
    :tags: test_4a;test_4b;[[copy('title')]]

    Test dynamic func in tags: [[copy("tags")]]

.. spec:: TEST_5
    :id: TEST_5
    :tags: [[copy('id')]]

    Test a `link <http://www.[[copy('id')]]>`_

    .. spec:: TEST_6
        :id: TEST_6

        nested id [[copy('id')]]

        nested id also :need_func:`[[copy("id")]]`

This should warn since it has no associated need: :need_func:`[[copy("id")]]`
