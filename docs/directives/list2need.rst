.. _list2need:

list2need
=========
.. versionadded:: 1.2.0


``list2need`` allows to create need objects out ouf a given list, where each list entry is used to create
a single need.

It allows to speed up the need-creation process for simple needs, which in most cases just have a title
and limited meta-data.

The content area of the ``list2need`` directive must contain the list only.
The list-structure syntax must be markdown (only supported format currently).
The single lines still need to follow the syntax of your document.

You can not set any meta-data for a specific need, except the ID of the need.
If this is needed, please use :ref:`needextend`.

Need-IDs get generated automatically (hash value), if not given.
IDs can be set by the prefix ``(ID)`` in the line. Example: ``(REQ-1)My first requirement``.
This mechanism is the same as the one used by :ref:`need_part`.

.. code-block:: rst

   .. list2need::
      :types: requirement, specification, test
      :presentation: nested
      :delimiter: .

      * Need example on level 1
      * (NEED-002) Another Need example on level 1 with a given ID
        * Sub-Need on level 2
          * Sub-Need on level 3
        * Another Sub-Need on level 2. Where this sentence will be used as content, the first one as title.


.. list2need::
   :types: requirement, specification, test
   :presentation: nested
   :delimiter: .

   * Need example on level 1
   * (NEED-002) Another Need example on level 1 with a given ID
     * Sub-Need on level 2
       * Sub-Need on level 3
         * Sub-Need on level 4
     * Another Sub-Need on level 2. Where this sentence will be used as content, the first one as title.


Options
-------

presentation
~~~~~~~~~~~~
Defines how the single Sphinx-Needs objects shall be presented.

:nested: Needs of level 2 are defined in the content of the parent need (level 1) and so on.
:standalone: Each list element gets its own, independent need object. They are not nested.


Default: **nested**

delimiter
~~~~~~~~~

Character to be used as delimiter, to define which part of the list-element shall be used as title, which one as
content.

The first split part is used as title, the rest as content.

Default: **.**

format
~~~~~~
Defines the syntax format of the list.
Currently only **markdown** is supported.

This format is only used for the list-structure.
The line-content itself still need to follow the syntax of the current documentation.

.. hint::

   The list syntax in markdown is slightly shorter as the one in restructuredText.
   Also the differences are really small, so that **markdown** got chosen.

Default: **markdown**
