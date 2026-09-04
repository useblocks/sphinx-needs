TEST DOCUMENT
=============

Section 1
---------

.. req:: Command line interface
    :id: R_12345
    :tags: test;test2
    :introduced: 1.0.0
    :updated: 1.5.1
    :impacts: component_a

    The Tool **shall** have a command line interface.

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
    :columns: id;title;introduced;updated;impacts

Component A Requirement Table
-----------------------------

.. needtable::
    :columns: id;title;introduced;updated;impacts
    :filter: "component_a" in impacts

Component B Requirement List
----------------------------

.. needlist::
    :filter: "component_b" in impacts
