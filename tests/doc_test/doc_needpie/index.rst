TEST DOCUMENT Needpie
=======================

.. spec:: Spec 1
    :id: SPEC_1
    :tags: a

.. spec:: Spec 2
    :id: SPEC_2
    :tags: a

.. spec:: Spec 3
    :id: SPEC_3
    :tags: a

.. spec:: Spec 4
    :id: SPEC_4
    :tags: b

.. spec:: Spec 5
    :id: SPEC_5
    :tags: b

.. spec:: Spec 6
    :id: SPEC_6
    :tags: c


.. needpie:: Test pie
   :labels: All, A, B, C

   True
   "a" in tags
   "b" in tags
   "c" in tags



.. toctree::

   page