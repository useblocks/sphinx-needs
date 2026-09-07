Diagrams
========

.. spec:: Command line interface
    :id: SP_001
    :status: implemented
    :tags: test;test2

    The Tool awesome shall have a command line interface.

    .. needuml::

       node peter
       card max

       peter --> max

    More text...


.. spec:: Multiple needuml
   :id: SP_002

   Some text ...

   .. needuml::

      card Yehaa
      card Ups

      Yehaa <--> Ups

   Another text...

   .. needuml::

      node test_me
      node now

      test_me => now

   More text