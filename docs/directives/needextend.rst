.. _needextend:

needextend
==========
.. versionadded:: 0.7.0

``needextend`` allows to modify existing needs. It doesn't provide any output, as the modifications get presented
at the original location of the modified need.

.. code-block:: rst

   .. needextend:: <filter_string>
      :-option:
      :+option: new value


The following modifications are supported:

* ``+option``: add new value to an existing value of an option.
* ``-option``: delete a complete option.

``+option`` and ``-option`` can be combined to completely reset the value of a need.

The argument of ``needextend`` must be a :ref:`filter_string`, which defines the needs to modify.

**Example**

.. code-block:: rst

    .. req:: A requirement
       :id: extend_test_001
       :status: open
       :author: Foo
       :tags: extend, tag_1, tag_2

    .. req:: Another requirement
       :id: extend_test_002
       :status: closed
       :author: Bar
       :links: extend_test_001
       :tags: extend

    .. needextend:: status == "open"
       :-status:
       :+status: in progress
       :+author: and me
       :+links: NEW_LINK_1, NEW_LINK_2


.. req: A requirement
   :id: extend_test_001
   :status: open
   :tags: tag_1, tag_2

.. req: Another requirement
   :id: extend_test_002
   :status: closed
   :links: extend_test_001

.. needextend:: extend
   :-status:
   :+status: in progress
   :+author: New author
   :+links: New link
   :-blocks:
   :+blocks: NEW_LINK_ID_123
