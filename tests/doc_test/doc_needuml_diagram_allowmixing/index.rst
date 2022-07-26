TEST DOCUMENT NEEDUML GIAGRAM ALLOWMIXING
=========================================

.. story:: Test story
   :id: ST_001

   Some content

.. int:: Test needuml diragram allowmixing
   :id: INT_001

   stuff

   .. needuml::

      allowmixing
      
      DC -> Marvel: Hi Kevin
      Marvel --> DC: Anyone there?

      {{uml("ST_001")}}

      node "System A" as sys_2
      sys_2 --> int

      class "test component" as comp {
         name
         functions
         activate()
      }

   .. needuml::
      :config: mixing

      {{uml("ST_001")}}

      class "test component" as comp {
         name
         functions
         activate()
      }

   .. needuml::

      start
      :Hello Bob;
      :Hello Alice;
      note
      Nice to hear from you!
      endnote

.. needuml::
   :config: mixing

   DC -> Marvel: Hi Kevin
   Marvel --> DC: Anyone there?

   {{uml("ST_001")}}

   node "System A" as sys_2
   sys_2 --> int

   class "test component" as comp {
      name
      functions
      activate()
   }

.. needuml::

   start
   :Hello Bob;
   :Hello Alice;
   note
   Nice to hear from you!
   endnote
