TEST DOCUMENT NEEDUML SAVE
==========================

.. story:: Test story
   :id: ST_001

   Some content

.. story:: Test story 2
   :id: ST_002

   Some other content

.. int:: Test needuml save
   :id: INT_001

   .. needuml::
      :save: _build/my_needuml.puml

      DC -> Marvel: Hi Kevin
      Marvel --> DC: Anyone there?

   .. needuml::
      :save: _out//sub_folder/my_needs.puml

      {{uml("ST_001")}}
      {{uml("ST_002")}}
