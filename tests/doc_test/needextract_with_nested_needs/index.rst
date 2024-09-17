Test
====

.. toctree::
   
   needextract
   
.. spec:: Test spec
   :id: SPEC_1

   Another, child spec

   This is id [[copy("id")]] :ndf:`copy("id")`

   .. spec:: Child spec
     :id: SPEC_1_1
   
      awesome child spec.
      and now a grandchild spec

      .. spec:: Grandchild spec
         :id: SPEC_1_1_1
   
         awesome grandchild spec.

      another grandchild spec

      .. spec:: Grandchild spec
         :id: SPEC_1_1_2
   
         awesome grandchild spec number 2.

         This is grandchild id [[copy("id")]] :ndf:`copy("id")`
   
   Some parent text