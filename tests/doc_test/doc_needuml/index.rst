TEST DOCUMENT NEEDUML
=====================

.. story:: Test story
   :id: ST_001

   Some content

.. story:: Test story2
   :id: ST_002

   Some content 2

.. int:: Test interface
   :id: INT_001

   circle "Int_X" as int

.. comp:: Test component
   :id: COMP_001

   class "test component" as comp {
       name
       functions
       activate()
   }

   {{uml("INT_001")}}

   comp --> int


.. sys:: Test System
   :id: SYS_001

   {{uml("COMP_001")}}

   class "Component 2" as comp_2 {
       name
       street
   }

   comp_2 --> int


.. prod:: Test Product
   :id: PROD_001

   allowmixing
   {{uml("SYS_001")}}

   node "System A" as sys_2
   sys_2 --> int


.. needuml::
   :scale: 50%
   :align: center
   :config: mixing
   :debug:

   class "{{needs['ST_001'].title}}" as test {
     implement
     {{needs['ST_001'].status}}
   }

   {{uml("SYS_001")}}


.. int:: Test interface2
   :id: INT_002

   .. needuml::
      :scale: 50%
      :align: center
      :config: mixing

      class "{{needs['ST_001'].title}}" as test {
         implement
         {{needs['ST_001'].status}}
      }

      {{uml("SYS_001")}}

   .. needuml::
      :scale: 50%
      :align: center
      :config: mixing
      :key: sequence

      Alice -> Bob: Hi Bob
      Bob --> Alice: Hi Alice


.. int:: Test interface3
   :id: INT_003

   .. needuml::
      :key: class

      allowmixing

      class "{{needs['ST_001'].title}}" as test {
         implement
         {{needs['ST_001'].status}}
      }

      {{uml("INT_002", "sequence")}}

   .. needuml::
      :key: sequence

      Alice -> Bob: Hi Bob
      Bob --> Alice: Hi Alice


.. int:: Test interface4
   :id: INT_004

   .. needuml::
      :scale: 50%
      :key: class

      allowmixing

      class "{{needs['ST_001'].title}}" as test {
         implement
         {{needs['ST_001'].status}}
      }

      {{uml("SYS_001")}}

   .. needuml::

      Superman -> Batman: Hi Bruce
      Batman --> Superman: Hi Clark

   .. needuml::
      :key: sequence

      DC -> Marvel: Hi Kevin
      Marvel --> DC: Anyone there?

   .. needuml::

      Alice -> Bob: Hi Bob
      Bob --> Alice: Hi Alice

.. needtable:: 
   :filter: arch
   :style: table
   :columns: id, type, title
