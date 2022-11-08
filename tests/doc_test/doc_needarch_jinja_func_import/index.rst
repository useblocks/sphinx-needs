TEST DOCUMENT NEEDARCH JINJA FUNC IMPORT
========================================


.. story:: Story
   :id: US_001

   Some content

.. story:: Story 002
   :id: US_002

   Some other content.

.. int:: Test interface
   :id: INT_001

   circle "Int_X" as int

.. int:: Test interface2
   :id: INT_002

   stuff.

.. test:: Test example title
   :id: TC_001
   :uses: US_001, US_002
   :tests: INT_001, INT_002

   test content.

   .. needarch::
      :scale: 50
      :align: center
      :debug:

      Alice -> Bob: Hi Bob
      Bob --> Alice: hi Alice

      {{import("uses", "tests")}}
