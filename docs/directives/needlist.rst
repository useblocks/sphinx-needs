.. _needlist:

needlist
========

.. versionadded:: 0.2.0

**needlist** creates a list, which elements are based on the result of given filters.

.. code-block:: rst

   .. needlist::
      :tags: main_example

.. needlist::
   :tags: main_example

Options
-------

.. note:: **needlist** supports the full filtering possibilities of sphinx-needs.
          Please see :ref:`filter` for more information.

Supported options:

 * :ref:`needlist_show_status`
 * :ref:`needlist_show_tags`
 * :ref:`needlist_show_filters`
 * Common filters:
    * :ref:`option_status`
    * :ref:`option_tags`
    * :ref:`option_types`
    * :ref:`option_filter`


.. _needlist_show_status:

show_status
~~~~~~~~~~~
Flag for adding status information of found needs to list result.

If a filtered need has no status information, no status output is written for this need.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needlist::
         :show_status:
         :status: done; implemented

   .. needlist::
      :show_status:
      :status: done; implemented

.. _needlist_show_tags:

show_tags
~~~~~~~~~
Flag for adding tag information of found needs to list result.

If a filtered need has no tag information, no tag output is written for this need.

.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needlist::
         :show_tags:
         :status: done; implemented

   .. needlist::
      :show_tags:
      :status: done; implemented


.. _needlist_show_filters:

show_filters
~~~~~~~~~~~~

If set, the used filter is added below of result list:


.. container:: toggle

   .. container::  header

      **Show example**

   .. code-block:: rst

      .. needlist::
         :show_filters:
         :status: done; implemented

   .. needlist::
      :show_filters:
      :status: done; implemented
