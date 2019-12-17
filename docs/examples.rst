.. _examples:

Examples
========

.. code-block:: rst

    **Some needs**
    .. req:: My first requirement
       :status: open
       :tags: requirement; test; awesome

       This is my **first** requirement!!
       .. note:: You can use any rst code inside it :)

    .. spec:: Specification of a requirement
       :id: OWN_ID_123
       :links: R_F4722

       Outgoing links of this spec: :need_outgoing:`OWN_ID_123`.

    .. impl:: Implementation for specification
       :id: IMPL_01
       :links: OWN_ID_123

       Incoming links of this spec: :need_outgoing:`IMPL_01`.

    .. test:: Test for XY
       :status: implemented
       :tags: test; user_interface; python27
       :links: OWN_ID_123; IMPL_01

       This test checks :need:`IMPL_01` for :need:`OWN_ID_123` inside a
       Python 2.7 environment.

    **Linking inside text**

    As :need:IMPL_01 shows, the linked :need:OWN_ID_123 is realisable.

    **Filter result as list**

    .. needfilter::
       :tags: test
       :show_filters:

    **Filter result as table**

    .. needfilter::
       :tags: test
       :status: implemented; open
       :show_filters:
       :layout: table

    **Filter result as diagram**

    .. needfilter::
       :layout: diagram



This will be rendered to:


**Some needs**

.. req:: My first requirement
   :status: open
   :tags: requirement; test; awesome

   This is my **first** requirement!!

   .. note:: You can use any rst code inside it :)

.. spec:: Specification of a requirement
   :id: OWN_ID_123
   :links: R_F4722

   Outgoing links of this spec: :need_outgoing:`OWN_ID_123`.

.. impl:: Implementation for specification
   :id: IMPL_01
   :links: OWN_ID_123

   Incoming links of this spec: :need_incoming:`IMPL_01`.

.. test:: Test for XY
   :status: implemented
   :tags: test; user_interface; python27
   :links: OWN_ID_123; IMPL_01

   This test checks :need:`IMPL_01` for :need:`OWN_ID_123` inside a
   Python 2.7 environment.

**Linking inside text**

As :need:`IMPL_01` shows, the linked :need:`OWN_ID_123` is realisable.

**Filter result as list**

.. needtable::
   :tags: test
   :show_filters:

**Filter result as table**

.. needtable::
   :tags: test
   :status: implemented; open
   :show_filters:

**Filter result as diagram**

.. needflow::
   :filter: "Examples" == section_name


Single needs
------------

.. req:: Open requirement example
   :status: open

.. req:: In progress requirement example
   :status: in_progress

.. req:: Closed requirement example
   :status: closed


