An invalid scope filter
=======================

A scope ``:filter:`` that cannot be evaluated is warned by the filter engine and
selects nothing, so every filter line counts zero. The literal line is not
counted over the scope, so the chart is still drawn.

.. needpie:: pie invalid scope filter
   :labels: s, t, a, lit
   :filter: xxx

   status == 'open'
   type == 'req'
   'a' in tags
   3
