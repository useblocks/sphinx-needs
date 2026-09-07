TEST DOCUMENT NEEDUML KEY DUPLICATE
===================================

.. int:: Test negative 01
   :id: INT_001

   .. needuml::
      :key: sequence

      DC -> Marvel: Hi Kevin
      Marvel --> DC: Anyone there?

   .. needuml::

      Superman -> Batman: Hi Bruce
      Batman --> Superman: Hi Clark

   .. needuml::
      :key: sequence

      Alice -> Bob: Hi Bob
      Bob --> Alice: Hi Alice
