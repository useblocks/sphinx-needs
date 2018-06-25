.. sectnum::

TEST DOCUMENT
=============

First Section
-------------

.. req:: Command line interface
    :id: R_12345
    :tags: test;test2
    :introduced: 1.0.0
    :updated: 1.5.1
    :impacts: component_a

    The Tool **shall** have a command line interface.

Second Section
--------------
.. req:: Another Requirement
    :id: R_12346
    :tags: test;test2
    :introduced: 1.1.1
    :updated: 1.4.0
    :impacts: component_b

    The Tool **shall** have a command line interface.

All Requirements
----------------

.. needtable::
    :columns: id;section

First Section Only
------------------

.. needtable::
    :columns: id;title;section
    :filter: 'First Section' in section and section.startswith('1.1')
