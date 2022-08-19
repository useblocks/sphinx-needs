.. _needarch:

needarch
========

``needarch`` behaves exactly like :ref:`needuml`, but only works inside a need.

|ex|

.. code-block:: rst

   .. req:: Requirement arch
      :id: req_arch_001
         
      .. needarch::
         :scale: 50
         :align: center
         :debug:

         Alice -> Bob: Hi Bob
         Bob --> Alice: hi Alice

|out|

.. req:: Requirement arch
   :id: req_arch_001

   .. needarch::
      :scale: 50
      :align: center
      :debug:

      Alice -> Bob: Hi Bob
      Bob --> Alice: hi Alice
