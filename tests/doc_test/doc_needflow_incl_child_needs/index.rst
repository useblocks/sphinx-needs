TEST DOCUMENT NEEDFLOW INCL CHILD NEEDS
=======================================

.. story:: A story
   :id: STORY_1

   The user story defined.

   :np:`(1) substory 1`

   :np:`(2) substory 2`

   .. story:: A child story
      :id: STORY_2

      :np:`(3) subsubstory 3`

      .. spec:: A spec
         :id: SPEC_1

   .. spec:: Sibling child spec
      :id: SPEC_3

.. story:: Story3
   :id: STORY_3
   :links: STORY_1.1, STORY_1.2

   The user story3 defined.

   .. spec:: Spec 2
      :id: SPEC_2


.. needflow::
   :show_link_names:
   :debug:
