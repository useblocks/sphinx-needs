TEST DOCUMENT for warning handling
==================================

.. spec:: Command line interface
    :id: SP_TOO_000
    :status: implemented
    :tags: test;test2

    .. spec:: Command line interface child 1
        :id: SP_TOO_001
        :status: implemented
        :tags: test3;test4

        Malformed Content of SP_TOO_001:

        +-------+---------+
        | hello | world 1
        +-------+---------+
        | hello | world 1 |
        +-------+---------+

        We expect to get a warning about malformed table in line 16.

    .. "Real" content of SP_TOO_000

    The Tool awesome shall have a command line interface.

    Malformed Content of SP_TOO_000:

    +-------+-------+
    | hello | world
    +-------+-------+
    | hello | world |
    +-------+-------+

    We expect to get a warning about malformed table in line 30.

    .. spec:: Command line interface child 2
        :id: SP_TOO_002
        :status: implemented
        :tags: test5;test6

        Content of SP_TOO_002:
        Malformed Content of SP_TOO_002:

        +-------+---------+
        | hello | world 2
        +-------+---------+
        | hello | world 2 |
        +-------+---------+

        We expect to get a warning about malformed table in line 46.
