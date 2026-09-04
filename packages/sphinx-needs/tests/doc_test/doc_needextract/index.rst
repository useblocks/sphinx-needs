TEST DOCUMENT NEEDEXTRACT
=========================

.. toctree::

   check_need_refs
   check_images
   subfolder/file_1.rst

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

.. story:: A complex content example
   :id: US_002

   Check if image gets copied as well.

   .. image:: _images/smile.png

.. story:: Absolute path example
   :id: US_003

   Use an absolut path for the image

   .. image:: /_images/smile.png


.. story:: Substitution Test
   :id: US_004

   Awesome |SN|

   .. image:: /_images/smile.png

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
