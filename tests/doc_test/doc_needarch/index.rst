TEST DOCUMENT NEEDARCH
======================

.. story:: Test story
   :id: ST_001

   Some content

.. int:: Test interface
   :id: INT_001

   circle "Int_X" as int

.. int:: Test interface2
   :id: INT_002

   .. needarch::
      :scale: 50
      :align: center
      :debug:

      Alice -> Bob: Hi Bob
      Bob --> Alice: hi Alice

   .. needarch::
      :debug:

      circle "Int_C" as Int_c
      circle "Int_D" as Int_d

.. int:: Test interface3
   :id: INT_003

   .. needuml::

      circle "Int_A" as Int_a
      circle "Int_B" as Int_b

.. needuml::

   title Sequence diagram title

   Alice --> Bob
   Bob ---> Alice

.. needuml::

   title Use case diagram title

   actor Alice
   actor Bob
