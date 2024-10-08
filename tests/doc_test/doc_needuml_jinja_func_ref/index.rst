TEST DOCUMENT NEEDUML JINJA FUNCTION REF 
========================================

.. story:: Test story
   :id: ST_001

   Some content

   :np:`(np_id) np_content`

.. story:: Another story
   :id: ST_002

   Different content content

.. int:: Test needuml jinja func ref
   :id: INT_001

   .. needuml::

      DC -> Marvel: {{ref("ST_001", option="title")}}
      Marvel --> DC: {{ref("ST_002", text="Different text to explain the story")}}

      DC -> Marvel: {{ref("ST_001.np_id", option="id")}}
      Marvel --> DC: {{ref("ST_001.np_id", option="content")}}
      
      DC -> Marvel: {{ref("ST_001.np_id", text="Different text to explain the story 2")}}
