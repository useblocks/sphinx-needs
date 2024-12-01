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

need in API
-----------

.. py:class:: TestClass

    This is a test class.

    .. py:method:: test_method(self)

        This is a test method.

        .. test:: test method
            :id: T_001

All Requirements
----------------

.. needtable::
    :columns: id;sections
    :filter: "1 TEST DOCUMENT" in sections

First Section Only
------------------

.. needtable::
    :columns: id;title;sections
    :filter: 'First Section' in sections[0] and sections[0].startswith('1.1')
    