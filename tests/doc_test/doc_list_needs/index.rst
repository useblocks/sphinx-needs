list-needs
----------

.. list-needs::

    :req id=LIST-1a: Need example title

        Need example on level 1.
    :req id=LIST-1b:
        Another Need example with nested needs.

        :spec id=LIST-s2a status=open tags=list-tag1,list-tag2 author="John Doe": 
            Sub-Need on level 2 with other options set
        :spec id=LIST-s2b title="Another Sub-Need on level 2.": 
            With the title given in the parameters.

            :test id=LIST-s3 collapse: Sub-Need on level 3.
            
                Content can contain standard *syntax*.

``defaults``
~~~~~~~~~~~~

.. list-needs::
    :defaults:
        :status: open
        :tags: list-tag1,list-tag2

    :req id=LIST-d1: Need level 1

        :spec id=LIST-d2 status=closed: Sub-Need level 2

``maxdepth``
~~~~~~~~~~~~

.. list-needs::
    :maxdepth: 1

    :req id=LIST-m1: Need level 1

        :normal: field list

``links-up`` and ``links-down``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-needs::
    :links-down: blocks, triggers
    :links-up: tests, checks

    :req id=LIST-l1: Need level 1

        :spec id=LIST-l2a: Sub-Need level 2a
        :spec id=LIST-l2b: Sub-Need level 2b

            :test id=LIST-l3: Sub-Need level 3

``flatten``
~~~~~~~~~~~

.. list-needs::
    :links-down: blocks, triggers
    :links-up: tests, checks
    :flatten:

    :req id=LIST-f1: Need level 1

        :spec id=LIST-f2a: Sub-Need level 2a
        :spec id=LIST-f2b: Sub-Need level 2b

            :test id=LIST-f3: Sub-Need level 3
