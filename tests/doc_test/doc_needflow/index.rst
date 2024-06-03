TEST DOCUMENT NEEDFLOW
=======================

.. toctree::

   page
   empty_needflow_with_debug
   needflow_with_root_id


.. spec:: Command line interface
    :id: SPEC_1
    :status: implemented
    :tags: test;test2

    The Tool awesome shall have a command line interface.

.. spec:: Spec_2
   :id: SPEC_2

.. story:: A story
   :id: STORY_1
   :links: SPEC_1, SPEC_2

   :np:`(1) subspec 1`

   :np:`(2) subspec 2`

   :np:`(subspec) subspec Awesome`

.. story:: Another story
   :id: STORY_2
   :links: SPEC_1, SPEC_2

   :np:`(another_one) subspec`

.. needflow::
   :debug:

Empty needflow, with no results.

.. needflow::
   :filter: status == "NOTHING"