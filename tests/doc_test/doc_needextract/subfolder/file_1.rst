subfolder file
==============

.. story:: Subfolder example with an absolute image
   :id: US_SUB_001

   Use an absolut path for the image

   .. image:: /_images/smile.png

   Path: ``/_images/smile.png``

.. story:: Subfolder example with a relative image
   :id: US_SUB_002

   Use a relative path for the image

   .. image:: ../_images/smile.png

   Path: ``../_images/smile.png``

.. story:: Subfolder example with image in same folder (indirect relative path)
   :id: US_SUB_003

   Use a relative path for the image

   .. image:: ../subfolder/smile.png

   Path: ``../subfolder/smile.png``

.. story:: Subfolder example with image in same folder (direct relative path)
   :id: US_SUB_004

   Use a relative path for the image

   .. image:: smile.png

   Path: ``smile.png``

.. story:: Subfolder example with image in same folder (absolute path)
   :id: US_SUB_005

   Use a absolute path for the image

   .. image:: /subfolder/smile.png

   Path: ``/subfolder/smile.png``

**Needextracts**


**from subfolder / this file**

.. needextract:: US_SUB_001
   :style: red_border

.. needextract:: US_SUB_002
   :style: red_border

.. needextract:: US_SUB_003
   :style: red_border

.. needextract:: US_SUB_004
   :style: red_border

.. needextract:: US_SUB_005
   :style: red_border

**from /index.rst**


.. needextract:: US_002
   :layout: clean
   :style: blue_border

.. needextract:: US_003