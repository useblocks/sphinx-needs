TEST DOCUMENT NEEDUML MISSING ARCH KEY
======================================

.. spec:: Test spec
   :id: SP_001

   .. needuml::
      :key: sequence

      Alice -> Bob: Hi Bob

.. needuml::

   {{uml("SP_001", "nosuchkey")}}
