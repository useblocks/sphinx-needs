Filter code test cases
======================

.. needtable:: Filter code table
   :style: table

   results = []
   # Lets create a needs_dict to address needs by ids more easily.
   needs_dict = {x['id']: x for x in needs}

   for need in needs:
       if need['type'] == 'story':
           results.append(need)


.. needtable:: Filter code func table
   :style: table
   :filter-func: filter_code_func.own_filter_code


.. needpie:: Filter code func pie
    :labels: project_x, project_y
    :filter-func: filter_code_func.my_pie_filter_code

.. needtable:: Filter code func table with multiple dots filter function path 
   :style: table
   :filter-func: module.filter_code_func.own_filter_code


.. needpie:: Filter code func pie with multiple dots filter function path 
    :labels: project_x, project_y
    :filter-func: module.filter_code_func.my_pie_filter_code

.. needtable:: Malformed filter func table
   :style: table
   :filter-func: filter_code_func.own_filter_code(


.. needpie:: Malformed filter func pie
    :labels: project_x, project_y
    :filter-func: filter_code_func.my_pie_filter_code(

.. needtable:: Malformed filter func table with multiple dots filter function path 
   :style: table
   :filter-func: module.filter_code_func.own_filter_code(


.. needpie:: Malformed filter func pie with multiple dots filter function path 
    :labels: project_x, project_y
    :filter-func: module.filter_code_func.my_pie_filter_code(