NEED PARTS
==========

.. spec:: Command line interface
    :id: SP_TOO_001
    :status: implemented
    :tags: test;test2

    The Tool awesome shall have a command line interface with following commands:

    * :need_part:`(1)exit()`
    * :need_part:`(2)start()`
    * :need_part:`(awesome_id)blub()`
    * :need_part:`(multiline_id)
      has multi-lines`


    * :np:`unknown_id_1`
    * :np:`unknown_id_2`

    .. spec:: TEST_2
        :id: TEST_2

        Part in nested need: :need_part:`(nested_id)something`

:np:`hallo`

:need:`SP_TOO_001.1`

:need:`SP_TOO_001.2`

:need:`SP_TOO_001.awesome_id`

:need:`My custom link name <SP_TOO_001.awesome_id>`

:need:`SP_TOO_001.unknown_part`

.. test:: Other
    :id: OTHER_1
    :other_links: SP_TOO_001,SP_TOO_001.1,
    :links: SP_TOO_001.unknown_part

.. test:: Other 2
    :id: OTHER_2
    :more_links: SP_TOO_001
