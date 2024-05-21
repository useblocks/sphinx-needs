TEST DOCUMENT for warning handling
==================================

.. spec:: Command line interface
    :id: SP_TOO_000
    :status: implemented
    :tags: test;test2
    :pre_template: pre_content
    :post_template: post_content

    .. spec:: Command line interface child 1
        :id: SP_TOO_001
        :status: implemented
        :tags: test3;test4

        :unknown1:`content`

    .. "Real" content of SP_TOO_000

    The Tool awesome shall have a command line interface.

    Malformed Content of SP_TOO_000:

    :unknown2:`content`

    .. spec:: Command line interface child 2
        :id: SP_TOO_002
        :status: implemented
        :tags: test5;test6

        :unknown3:`content`
