Variant Data Field Errors Test
==============================

.. req:: Invalid variant data path
   :id: REQ_SYNTAX
   :mystring: <{ platform }>

.. req:: Missing variant attribute
   :id: REQ_MISSING
   :mystring: <{ var.nonexistent }>

.. req:: Missing nested variant attribute
   :id: REQ_MISSING_NESTED
   :mystring: <{ var.build.missing }>

.. req:: Type mismatch (integer into string field)
   :id: REQ_BADTYPE_STR
   :myint: <{ var.platform }>

.. req:: Type mismatch (integer into array of strings)
   :id: REQ_BADTYPE_STRING
   :mystring: <{ var.build }>

.. req:: Type mismatch (integer into array of strings)
   :id: REQ_BADTYPE_ARRAY
   :myarray: a, <{ var.build.opt_level }>, c
