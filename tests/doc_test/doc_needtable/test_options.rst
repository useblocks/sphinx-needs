TEST OPTIONS
============

.. spec:: test123
    :id: SP_TOO_003
    :status: implemented
    :tags: test;test2

    The Tool awesome shall have a command line interface.

.. story:: test abc
   :links: SP_TOO_003
   :tags: 1

.. spec:: Use needs_string_links
   :id: EXAMPLE_STRING_LINKS
   :config: needs_string_links
   :github: 404;303

   Replaces the string from ``:config:`` and ``:github:`` with a link to the related website.


table 1
--------
.. needtable::

table 2
-------

.. needtable::
   :columns: Incoming;Id;tags;STATUS;TiTle

table 3
-------

.. needtable:: Example table
   :filter: 'EXAMPLE_STRING_LINKS' in id
   :columns: id;title;config;github
   :style: table
