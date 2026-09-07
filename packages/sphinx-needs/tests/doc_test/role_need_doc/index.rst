TEST DOCUMENT EXTERNAL
======================


Local need
----------

.. req:: Test requirement 1
   :id: REQ_1

Local need ref: :need:`REQ_1`

Imported need
-------------

.. needimport:: needs_test_small.json
   :id_prefix: IMP_

Imported need ref: :need:`IMP_TEST_01`


External needs
--------------


External need ref: :need:`EXT_TEST_01`

.. toctree::

   subfolder/page


Imported need 2
---------------
Imported need ref: :need:`IMP_TEST_02`