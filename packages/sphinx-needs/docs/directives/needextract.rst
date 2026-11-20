.. _needextract:

needextract
===========

.. versionadded:: 0.5.1

``needextract`` generates copies of filtered needs with custom layout and style.

It supports custom creation of extracts from existing needs.
For instance, a supplier could get a copy of requirements but would not see all the internal meta-data.

.. syntax-example::

   .. feature:: A feature
      :id: EXTRACT_FEATURE_1

      This is a feature that should be extracted.

   .. needextract::
      :filter: id == 'EXTRACT_FEATURE_1'
      :layout: clean
      :style: green_border


.. caution::

   ``needextract`` supports correct rendering of most, but not all, content coming from the original need.
   Be careful when using complex content in the original need, like custom roles or directives
   that require any sphinx transforms.
   
``needextract`` supports the full filtering possibilities of sphinx-needs.
Please read :ref:`filter` for more information.

It also supports arguments as filter string,
which works like the option ``filter``, but also
supports need ID as filter argument. A need part's address (``ID.part``) reads as the part's need when that need
has the part, also when the argument could be read as a filter: given a need ``var`` with a part ``flag``,
``var.flag`` extracts ``var`` (write ``(var.flag)`` to have the filter). An argument naming no part of a need, such as
``status.upper() == "OPEN"`` or ``REQ_1.p9`` (``REQ_1`` has no part ``p9``), is read as a need ID or a filter string,
as any other argument is.

.. syntax-example::

   .. needextract:: EXTRACT_FEATURE_1
      :layout: clean
      :style: green_border

.. note:: arguments and option filter can't be used at the same time.

Options
-------

.. _needextract_layout:

layout
~~~~~~

``:layout:`` overwrites the need-specific layout option and sets the same layout for each need.
The original need provides the style information, if not overwritten by :ref:`needextract_style`.

See :ref:`layouts` for a list of available layouts.

.. syntax-example::

   .. needextract:: EXTRACT_FEATURE_1
      :layout: focus_r

.. _needextract_style:

style
~~~~~

``:style:`` overwrites the need-specific style option and sets the same style for each need.
The original need provides the layout information , if not overwritten by :ref:`needextract_layout`.

See :ref:`styles` for a list of available styles.

.. syntax-example::

   .. needextract:: EXTRACT_FEATURE_1
      :style: blue_border
