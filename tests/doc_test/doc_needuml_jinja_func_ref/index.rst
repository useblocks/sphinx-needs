TEST DOCUMENT NEEDUML JINJA FUNCTION REF 
========================================

.. story:: Test story
   :id: ST_001

   Some content

.. story:: Another story
   :id: ST_002

   Different conftent content

.. int:: Test needuml jinja func ref
   :id: INT_001

   .. needuml::

      DC -> Marvel: {{ref("ST_001", content="title")}}
      Marvel --> DC: {{ref("ST_002", text="Different text to explain the story")}}
