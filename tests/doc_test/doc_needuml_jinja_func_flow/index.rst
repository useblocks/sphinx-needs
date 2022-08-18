TEST DOCUMENT NEEDUML JINJA FUNCTION FLOW
=========================================

.. story:: Test story
   :id: ST_001

   Some content

.. int:: Test needuml jinja func flow
   :id: INT_001

   .. needuml::

      DC -> Marvel: Hi Kevin
      Marvel --> DC: Anyone there?

      {{flow("ST_001")}}
