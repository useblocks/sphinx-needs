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

.. spec:: story 1
    :id: STORY_1
    :author: foo

.. spec:: story 2
    :id: STORY_2
    :author: foo

.. spec:: story 3
    :id: STORY_3
    :author: bar

.. needpie:: Test pie
   :labels: All, A, B, C

   True
   "a" in tags
   "b" in tags
   "c" in tags

.. needpie:: Test pie 2
   :labels: foo, bar, not_set
   :legend:

   author == 'foo'
   author == 'bar'
   author == 'not_set'


.. toctree::

   page