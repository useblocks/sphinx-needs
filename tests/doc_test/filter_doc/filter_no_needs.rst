filter_no_needs
===============

.. req:: filter_warning_req_a
   :id: FILTER_001
   :tags: 1
   :status: open
   :hide:
   :duration: 1

.. req:: filter_warning_req_b
   :id: FILTER_002
   :tags: 2
   :status: closed
   :hide:

   
Testing tables
-------------------------

Should show default message

.. needtable::
   :filter: ("5" in tags)

Should show specific message
   
.. needtable::
   :filter: ("6" in tags)
   :filter_warning: got filter warning from needtable

Should show no specific message and no default message

.. needtable::
   :filter: ("7" in tags)
   :filter_warning: 

Should show no specific message cause needs found
   
.. needtable::
   :filter: ("2" in tags)
   :filter_warning: no filter warning from needtable
   
   
Testing Lists
-------------------------

Should show specific message

.. needlist::
   :tags: 7
   :filter_warning: got filter warning from needlist


Should show default message

.. needlist::
   :tags: 7
   
Should show no specific message and no default message

.. needlist::
   :tags: 7
   :filter_warning: 
   
Should show no specific message cause needs found

.. needlist::
   :tags: 1
   :filter_warning: no filter warning from needlist

   
Testing Flows
-------------------------
   
Should show specific message

.. needflow::
   :filter: ("7" in tags)
   :filter_warning: got filter warning from needflow
   
Should show default message

.. needflow::
   :filter: ("7" in tags)
   

Should show no specific message and no default message

.. needlist::
   :filter: ("7" in tags)
   :filter_warning: 
   
Should show no specific message cause needs found

.. needflow::
   :filter: ("1" in tags)
   :filter_warning: no filter warning from needflow

   
Testing Gantt
-------------------------
   
Should show specific message

.. needgantt::
   :tags: 7
   :filter_warning: got filter warning from needgant

Should show default message

.. needgantt::
   :tags: 7

Should show no specific message and no default message

.. needgantt::
   :tags: 7
   :filter_warning: 
   

Should show no specific message cause needs found
   
.. needgantt::
   :tags: 1
   :filter_warning: no filter warning from needgant

Testing Sequence
-------------------------

.. user:: User A
    :id: USER_A
    :links: ACT_ISSUE
    :style: blue_border

.. action:: Creates issue
    :id: ACT_ISSUE
    :links: USER_B
    :style: yellow_border

.. user:: User B
    :id: USER_B
    :style: blue_border

Should show specific message

.. needsequence:: My filtered sequence
   :start: USER_A, USER_B
   :link_types: links, triggers
   :filter: ("User" not in title)
   :filter_warning: got filter warning from needsequence
   
Should show default message

.. needsequence:: My filtered sequence
   :start: USER_A, USER_B
   :link_types: links, triggers
   :filter: ("User" not in title)


Should show no specific message and no default message

.. needsequence:: My filtered sequence
   :start: USER_A, USER_B
   :link_types: links, triggers
   :filter: ("User" not in title)
   :filter_warning:
   
Should show no specific message cause needs found

.. needsequence:: My nonfiltered sequence
   :start: USER_A, USER_B
   :link_types: links, triggers
   :filter_warning: no filter warning from needsequence

Testing Pie
-------------------------
   
Should show specific message

.. needpie:: Empty Pie 0
   :labels: Running, Others
   :filter_warning: got filter warning from needpie
   
   '7' in tags
   '9' in tags

Should show default message

.. needpie:: Empty Pie 1
   :labels: Running, Others

   '7' in tags
   '9' in tags

Should show no specific message and no default message

.. needpie:: Empty Pie 2
   :labels: Running, Others
   :filter_warning: 
   
   '7' in tags
   '9' in tags

Should show no specific message cause needs found
   
.. needpie:: Success Pie
   :labels: Open, Closed, Others
   :filter_warning: no filter warning from needpie
   
   10
   20
   30

   
