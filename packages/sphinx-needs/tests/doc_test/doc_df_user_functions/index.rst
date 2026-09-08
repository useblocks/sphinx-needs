DYNAMIC FUNCTIONS
=================

.. spec:: TEST_1
    :id: TEST_1
    :status: [[my_own_function()]]

    :ndf:`my_own_function()`

    [[my_own_function()]] is not a dynamic function here

.. spec:: TEST_2
    :id: TEST_2
    :status: [[bad_function()]]

    :ndf:`bad_function()`

    :ndf:`invalid`

    :ndf:`unknown()`

    .. code-block:: toml

        # this should not be a func 
        [[something]]
