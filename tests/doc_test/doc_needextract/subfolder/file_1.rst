.. _ref_internal:

subfolder file
==============

.. toctree::

    check_images_2

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

.. story:: Need references
   :id: US_SUB_REF_001

   Test ``:need:``.

   - :need:`US_001`
   - :need:`US_002`
   - :need:`US_SUB_004`

.. story:: Need download
   :id: US_SUB_REF_002

   :download:`smile.png`


.. story:: Need references internal
   :id: US_SUB_REF_003

   :ref:`ref_internal`

.. story:: Need references external
   :id: US_SUB_REF_004

   `test/me <test/me>`__

   `/test/me </test/me>`__

   `../test/me <../test/me>`__



