Second page
===========

.. story:: Page receiver
   :id: PAGE_RECV
   :duration: 1

.. needsequence:: Page sequence
   :start: SENDER
   :filter: c.this_doc()

.. needflow:: Page flow
   :highlight: c.this_doc()

.. needgantt:: Page gantt
   :milestone_filter: c.this_doc()
