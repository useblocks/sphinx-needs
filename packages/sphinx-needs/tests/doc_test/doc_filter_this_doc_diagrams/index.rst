TEST DOCUMENT c.this_doc() in diagrams
======================================

.. story:: Sender
   :id: SENDER
   :links: MESSAGE
   :duration: 1

.. story:: Message
   :id: MESSAGE
   :links: INDEX_RECV, PAGE_RECV
   :duration: 1

.. story:: Index receiver
   :id: INDEX_RECV
   :duration: 1

.. needsequence:: Index sequence
   :start: SENDER
   :filter: c.this_doc()

.. needflow:: Index flow
   :highlight: c.this_doc()

.. needgantt:: Index gantt
   :milestone_filter: c.this_doc()

.. toctree::

   page
