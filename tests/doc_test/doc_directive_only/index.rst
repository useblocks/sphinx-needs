Only directive Test
=====================

.. req:: always_here_1
   :id: REQ_000

    out of only is alwasy here

.. only:: tag_a

   .. req:: only_tag_a
      :id: REQ_001

       I shall not appear if not running tag_a

       .. req:: only_tag_a_again
          :id: REQ_001_1
   
           need within need under only, shall neither appear if not running tag_a


.. only:: tag_b

   .. req:: only_tag_b
      :id: REQ_002

      I shall not appear if not running tag_b


.. only:: tag_a or tag_b

   .. req:: only_tag_a_or_b
      :id: REQ_003

      I shall not appear if not running either tag_a or tag_b
       

.. req:: always_here_2
   :id: REQ_004

    I shall always appear


Needs table
--------------

.. needtable::


Needs list
--------------
.. needlist::

