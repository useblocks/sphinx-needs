TEST DOCUMENT NEEDS CONSTRAINTS
===============================

.. spec:: Command line interface
    :id: SP_TOO_001
    :status: implemented
    :tags: test;test2

    The Tool awesome shall have a command line interface.

.. spec:: CLI
    :id: SP_TOO_002
    :status: dev
    :tags: hello;there
    :constraints: critical
    :style: red_border

    asdf

.. spec:: test1
    :id: SECURITY_REQ

    This is a requirement describing OPSEC processes.

.. spec:: test2
    :tags: critical
    :links: SECURITY_REQ
    :constraints: critical

    Example of a successful constraint.

.. spec:: test3
    :links: SECURITY_REQ
    :constraints: critical
    :layout: debug

    Example of a failed constraint.

.. spec:: FAIL_01
    :constraints: team

    Example of a failed constraint with medium severity. Note the style from :ref:`needs_constraint_failed_options`

.. toctree:: style_test
