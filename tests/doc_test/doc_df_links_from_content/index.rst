LINKS FROM CONTENT
==================

.. req:: Requirement 1
   :id: CON_REQ_1

.. req:: Requirement 2
   :id: CON_REQ_2

.. req:: Requirement with hyphens
   :id: CON-REQ-3

.. spec:: Spec that extracts links from own content
   :id: CON_SPEC_1
   :links: [[links_from_content()]]

   This specification cares about the realisation of:

   * :need:`CON_REQ_1`
   * :need:`My need <CON_REQ_2>`
   * :need:`CON-REQ-3`

.. spec:: Spec that extracts links from another need
   :id: CON_SPEC_2
   :links: [[links_from_content('CON_SPEC_1')]]

   Links retrieved from content of :need:`CON_SPEC_1`.

.. spec:: Spec with filter
   :id: CON_SPEC_3
   :links: [[links_from_content(filter='type == "req"')]]

   This also references:

   * :need:`CON_REQ_1`
   * :need:`CON_SPEC_1`

   But only requirements should pass the filter.

.. spec:: Spec with nested need
   :id: CON_SPEC_4
   :links: [[links_from_content()]]

   This references :need:`CON_REQ_1` but also contains a nested need:

   .. req:: Nested requirement
      :id: CON_REQ_4

      This nested need references :need:`CON_REQ_2` which should NOT be collected.
