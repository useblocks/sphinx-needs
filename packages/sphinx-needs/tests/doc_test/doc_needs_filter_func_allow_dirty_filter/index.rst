Needs Data to be filtered
=========================

.. feature:: Feature 001
   :id: FE_001

   Example feature 001 content.

.. usecase:: Usecase 001
   :id: USE_001
   :ti: 1
   :features: FE_001

   Example tesusecaset 001 content.

   .. needtable:: Filter func table 001
      :style: table
      :columns: id, title, tcl
      :filter-func: filter_func.my_own_filter(USE_001,features)

.. usecase:: Usecase 002
   :id: USE_002
   :ti: 3
   :features: FE_001

   Example usecase 002 content.

   .. needtable:: Filter func table 002
      :style: table
      :columns: id, title, tcl
      :filter-func: filter_func.my_own_filter(USE_002,features)
