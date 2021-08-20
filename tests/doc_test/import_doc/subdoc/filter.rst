Filter
======

.. needimport:: needs_test_small.json
   :id_prefix: small_
   :filter: "test" in tags

.. needimport:: subdoc/needs_test_small.json
   :id_prefix: small2_
   :filter: search("AAA", title)

.. needimport:: /subdoc/needs_test_small.json
   :id_prefix: small_abs_path_
   :filter: "test" in tags
