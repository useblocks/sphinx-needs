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
.. needimport:: needs_test.json
   :id_prefix: test_
   :tags: imported; new_tag




.. toctree::

   subdoc/filter

.. req:: Test requirement 1
   :id: REQ_1

.. spec:: Test specification 1
   :id: SPEC_1
