.. _needextract:

needextract
===========

.. versionadded:: 0.5.1

``needextract`` generates copies of filtered needs with custom layout and style.

It is mainly designed to support the customized creation of extracts from existing needs.
For instance a supplier should get a copy of requirements, but shall not see all the internal meta-data.

.. code-block:: rst

   .. needextract::
      :filter: type == 'feature'
      :layout: clean
      :style: green_border

Options
-------

.. note:: **needextract** supports the full filtering possibilities of **Sphinx-Needs**.
          Please see :ref:`filter` for more information.


* :ref:`needextract_layout`
* :ref:`needextract_style`
* Common filters:
   * :ref:`option_status`
   * :ref:`option_tags`
   * :ref:`option_types`
   * :ref:`option_filter`

.. _needextract_layout:

layout
~~~~~~

``layout`` overwrites the need-specific layout option and sets the same layout for each need.
The style information is taken from the original need, if not overwritten by :ref:`needextract_style`.

See :ref:`layouts` for a list of available layouts.

**Example**

.. code-block:: rst

   .. needextract::
      :filter: id in ['FEATURE_3', 'FEATURE_4']
      :layout: focus_r

**Result**

.. needextract::
   :filter: id in ['FEATURE_3', 'FEATURE_4']
   :layout: focus_r

.. _needextract_style:

style
~~~~~

``style`` overwrites the need-specific style option and sets the same style for each need.
The layout information is taken from the original need, if not overwritten by :ref:`needextract_layout`.

See :ref:`styles` for a list of available styles.

**Example**

.. code-block:: rst

   .. needextract::
      :filter: id in ['FEATURE_3', 'FEATURE_4']
      :style: blue_border

**Result**

.. needextract::
   :filter: id in ['FEATURE_3', 'FEATURE_4']
   :style: blue_border
