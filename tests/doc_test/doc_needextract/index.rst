TEST DOCUMENT NEEDEXTRACT
=========================

.. spec:: Test needextract
   :id: SP_001
   :status: implemented
   :tags: test

   Test content for needextarct.

   :np:`This is a need part content.`

.. spec:: Test needextract 02
   :id: SP_002
   :status: open
   :tags: test2

   Test content for needextarct.

   :np:`(1)This is another need part content.`

.. story:: A story
   :id: US_001
   :status: open
   :tags: 1


.. needextract::
   :tags: test

.. needextract::
   :status: open
   :style: blue_border

.. needextract::
   :filter: id == "US_001"
   :layout: clean
   :style: green_border

.. needextract:: id == "US_001"
   :layout: clean
   :style: blue_border

.. needextract:: id == "SP_002"
   :layout: clean
   :style: green_border

.. needextract:: US_001
   :layout: clean
   :style: blue_border
