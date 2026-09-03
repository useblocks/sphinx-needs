Filter code ARGS test cases
===========================

.. impl:: impl1
   :id: impl1
   :status: open
   :variant: project_x

.. impl:: impl2
   :id: impl2
   :status: done
   :variant: project_x

.. impl:: impl3
   :id: impl3
   :status: new
   :variant: project_x

.. impl:: impl4
   :id: impl4
   :status: new
   :variant: project_x


.. needtable:: Filter code func table
   :style: table
   :filter-func: filter_code_func.own_filter_code_args(open,foo)


.. needpie:: Filter code func pie
    :labels: new,done
    :filter-func: filter_code_func.my_pie_filter_code_args(new,done)
