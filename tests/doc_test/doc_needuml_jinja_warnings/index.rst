TEST DOCUMENT NEEDUML JINJA FUNCTION WARNINGS
=============================================

.. spec:: Test spec
   :id: SP_001

   Some content

.. spec:: Another spec
   :id: SP_002
   :links: SP_001

   .. needarch::

      Alice -> Bob: {{ref("SP_001", option="title", text="both given")}}
      Bob --> Alice: {{ref("SP_001")}}
      Alice -> Bob: {{ref("SP_001", text="only text")}}

      {{import("links")}}
      {{import("no_such_option")}}
