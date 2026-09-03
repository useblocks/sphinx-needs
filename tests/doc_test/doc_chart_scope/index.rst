TEST DOCUMENT CHART SCOPE
=========================

.. req:: One
   :id: REQ_1
   :status: open
   :tags: a

.. req:: Two
   :id: REQ_2
   :status: open
   :tags: b

.. req:: Three
   :id: REQ_3
   :status: closed
   :tags: a

.. spec:: S1
   :id: SPEC_1
   :status: open
   :tags: a

.. spec:: S2
   :id: SPEC_2
   :status: closed

.. test:: T1
   :id: TEST_1
   :status: open
   :tags: a

   Body with :need_part:`(P1) part one` inside.

Scoped pies
-----------

.. needpie:: pie unscoped
   :labels: s, t, a, lit

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie status
   :labels: s, t, a, lit
   :status: open

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie tags
   :labels: s, t, a, lit
   :tags: a

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie types
   :labels: s, t, a, lit
   :types: req

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie types by title
   :labels: s, t, a, lit
   :types: Requirement

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie status and tags
   :labels: s, t, a, lit
   :status: open
   :tags: a

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie filter
   :labels: s, t, a, lit
   :filter: type == 'req'

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie status and filter
   :labels: s, t, a, lit
   :status: open
   :filter: type == 'req'

   status == 'open'
   type == 'req'
   'a' in tags
   3

.. needpie:: pie scope selects nothing
   :labels: s, t, a, lit
   :status: nonexistent

   status == 'open'
   type == 'req'
   'a' in tags
   3

Empty states
------------

.. needpie:: pie all filters and no scope members
   :labels: s, t, a
   :status: nonexistent

   status == 'open'
   type == 'req'
   'a' in tags

.. needpie:: pie all filters and no scope members warned
   :labels: s, t, a
   :status: nonexistent
   :filter_warning: nothing is in this scope

   status == 'open'
   type == 'req'
   'a' in tags

A scope on a filter function
----------------------------

.. needpie:: pie filter func
   :labels: seen, one
   :status: open
   :filter-func: chart_scope_func.sizes

Scoped bars
-----------

.. needbar:: bar unscoped
   :xlabels: sA, tB, aC
   :ylabels: row
   :show_sum:

   status == 'open', type == 'req', 'a' in tags

.. needbar:: bar status
   :xlabels: sA, tB, aC
   :ylabels: row
   :show_sum:
   :status: open

   status == 'open', type == 'req', 'a' in tags

.. needbar:: bar filter
   :xlabels: sA, tB, aC
   :ylabels: row
   :show_sum:
   :filter: type == 'req'

   status == 'open', type == 'req', 'a' in tags

.. needbar:: bar scope selects nothing
   :xlabels: sA, tB, aC
   :ylabels: row
   :show_sum:
   :status: nonexistent

   status == 'open', type == 'req', 'a' in tags

.. needbar:: bar filter with a comma
   :xlabels: sA, tB, aC
   :ylabels: row
   :show_sum:
   :filter: status in ['closed', 'nonexistent']

   status == 'open', type == 'req', 'a' in tags

.. toctree::

   invalid
