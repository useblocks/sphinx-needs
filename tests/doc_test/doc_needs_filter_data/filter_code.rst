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
