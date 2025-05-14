TEST DOCUMENT IMPORT
====================

.. needimport:: needs_test.json


HIDDEN
------
.. needimport:: needs_test.json
   :id_prefix: hidden_
   :tags: hidden
   :hide:

COLLAPSED
---------
.. needimport:: needs_test.json
   :id_prefix: collapsed_
   :collapse: True
   :tags: should,be,collapsed

TEST
----
.. needimport:: key
   :id_prefix: test_
   :tags: imported; new_tag

FILTERED
--------
.. needimport:: needs_test.json
   :id_prefix: filter_
   :tags: imported
   :filter: id == 'IMPL_01'

.. needimport:: needs_test.json
   :id_prefix: ids_
   :tags: imported
   :ids: ROLES_REQ_1,ROLES_REQ_2



.. toctree::

   subdoc/filter
   subdoc/abs_path_import
   subdoc/rel_path_import

.. req:: Test requirement 1
   :id: REQ_1

.. spec:: Test specification 1
   :id: SPEC_1
