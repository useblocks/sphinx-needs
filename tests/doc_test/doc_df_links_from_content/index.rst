DYNAMIC FUNCTION: links_from_content
====================================

.. need:: Reference Need 1
   :id: N_REF_1

   :np:`(1) sub 1`
   :np:`(2) sub 1`

.. need:: Reference Need 2
   :id: N_REF_2

   :np:`(1) sub 1`
   :np:`(2) sub 1`

.. need:: Main Need
   :id: N_MAIN
   :links: [[links_from_content()]]

   This need links to

   - :need:`N_REF_1`
   - :need:`N_REF_1`
   - :need:`N_REF_1.1`
   - :need:`_REF_1.1`
   - :need:`N_REF_1.2`
   - :need:`N_REF_1.2`
   - :need:`n2 <N_REF_2>`
   - :need:`n2 <N_REF_2>`
   - :need:`n2.1 <N_REF_2.1>`
   - :need:`n2.1 <N_REF_2.1>`
   - :need:`n2.2 <N_REF_2.2>`
   - :need:`n2.2 <N_REF_2.2>`

   using dynamic function links_from_content.

   Expected links:
   - 1x N_REF_1
   - 1x N_REF_1.1
   - 1x N_REF_1.2
   - 1x N_REF_2
   - 1x N_REF_2.1
   - 1x N_REF_2.2
