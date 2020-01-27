.. _needextract:

needextract
===========

.. versionadded:: 0.5.1

``needextract`` generates copies of filtered needs with custom layout and style.


.. req:: TEST ME
   :id: EXTRACT_1
   :status: open

   Some extract test

.. req:: TEST ME2
   :id: EXTRACT_2
   :status: open
   :links: EXTRACT_1

   Some extract test2

   :ref:`filter`

   :ref:`needlist`

**Test 1**

.. needextract::
   :filter: type == 'feature' or id.startswith('EXTRACT')
   :layout: focus_r
   :style: clean
