.. _list2need:

list2need
=========
.. versionadded:: 1.2.0


``list2need`` allows to create need objects out ouf a given list, where each list entry is used to create
a single need.

It allows to speed up the need-creation process for simple needs, which in most cases just have a title
and limited meta-data.

The content area of the ``list2need`` directive must contain the list only.
The list-structure syntax is Sphinx-Needs specific, but borrowed from markdown.

No meta-data can be set, except a specific need-ID.
But you can use :ref:`needextend` to customize the created needs in a later step.

Need-IDs get generated automatically (hash value), if not given.
IDs can be set by the prefix ``(ID)`` in the line. Example: ``(REQ-1)My first requirement``.
This mechanism is the same as the one used by :ref:`need_part`.

.. code-block:: rst

   .. list2need::
      :types: req, spec, test
      :presentation: nested
      :delimiter: .

      * Need example on level 1
      * (NEED-002) Another Need example on level 1 with a given ID
        * Sub-Need on level 2
        * Another Sub-Need on level 2. Where this sentence will be used
          as content, the first one as title.
          * Sub-Need on level 3. With some rst-syntax support for
            the **content** by :ref:`list2need`

.. list2need::
   :types: req, spec, test
   :presentation: nested
   :delimiter: .

   * Need example on level 1
   * (NEED-002) Another Need example on level 1 with a given ID
     * Sub-Need on level 2
     * Another Sub-Need on level 2. Where this sentence will be used
       as content, the first one as title.
       * Sub-Need on level 3. With some rst-syntax support for
         the **content** by :ref:`list2need`

.. warning::

   There are currently known limitations in the list parser.
   For instance new content lines starting with `*` or `:` may get handled incorrectly.

List structure
--------------
The used list structure was defined to be as small as possible.

Each line starting with a ``*`` will create a new need object.

To define a child-need, add **2 additional whitespaces** infront of ``*``.
This is called the indentation level and each level must have a need-type defined in the ``types`` option.

A line starting **without** a ``*`` will be added to the prior one.
So it can be used to structure longer titles or content, and has no impact on the later representation.

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


List examples
-------------

List with need-ids
~~~~~~~~~~~~~~~~~~
.. code-block:: rst

   .. list2need::
      :types: feature

      * (LIST2NEED-001) Feature 1
      * (LIST2NEED-002) Feature 2
      * (FEATURE.3) Feature 3

.. list2need::
   :types: feature, req, spec

   * (LIST2NEED-001) Feature 1
   * (LIST2NEED-002) Feature 2
   * (FEATURE.3) Feature 3

Nested lists
~~~~~~~~~~~~
.. code-block:: rst

   .. list2need::
      :types: feature, req, spec, test

      * Level 1
        * Level 2
          * Level 3
            * Level 4

.. list2need::
   :types: feature, req, spec, test

   * Level 1
     * Level 2
       * Level 3
         * Level 4


List with newlines
~~~~~~~~~~~~~~~~~~
.. code-block:: rst

   .. list2need::
      :types: req, spec

      * Level 1 need with newlines.
        With text in a newline to keep it readable

        Empty lines are okay as well.

.. list2need::
   :types: req, spec

   * Level 1 need with newlines.
     With text in a newline to keep it readable

     Empty lines are okay as well.

Simple rst in lists
~~~~~~~~~~~~~~~~~~~

.. code-block:: rst

   .. list2need::
      :types: req, spec

      * Level 1 need with rst. With **some** rst-content for :ref:`list2need`

.. list2need::
   :types: req, spec

   * Level 1 need with rst. With **some** rst-content for :ref:`list2need`

rst-directives in lists
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: rst

   .. list2need::
      :types: req, spec

      * Level 1 need and more
        * And a complex sub-need on level 2 with an image-directive.

        .. image:: /_static/sphinx-needs-logo.png
           :align: center
           :width: 20%


.. list2need::
   :types: req, spec

   * Level 1 need and more
     * And a complex sub-need on level 2 with an image-directive.

     .. image:: /_static/sphinx-needs-logo.png
        :align: center
        :width: 20%

Lists with need-part support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: rst

   .. list2need::
      :types: req, spec

      * (LIST2NEED-REQ-1)Requirement which shall get also need-parts.
        Some need-parts:

        First: :np:`(1)The first need-part`

        Second: :np:`(ANOTHER)ANOTHER need-part`

        * And a spec need.
          Lets reference a need-part frm above: :need:`LIST2NEED-REQ-1.1`

.. list2need::
   :types: req, spec

   * (LIST2NEED-REQ-1)Requirement which shall get also need-parts.
     Some need-parts:

     First: :np:`(1)The first need-part`

     Second: :np:`(ANOTHER)ANOTHER need-part`

     * And a spec need.
       Lets reference a need-part frm above: :need:`LIST2NEED-REQ-1.1`

Set meta-data
~~~~~~~~~~~~~
To set also meta-data for selected needs created by :ref:`list2need`, you can use
:ref:`needextend` in a second step.

.. code-block:: rst

   .. list2need::
      :types: feature, req

      * (EXT-FEATURE-A)Feature A
        * (EXT-REQ-1)Requirement 1. It shall be fast.
        * (EXT-REQ-2)Requirement 2. It shall be big.
      * (EXT-FEATURE-B)Feature B


   .. needextend:: EXT-REQ-1
      :status: closed
      :style: green_border

   .. needextend:: EXT-REQ-2
      :status: open
      :style: red_border

   .. needextend:: id in ["EXT-FEATURE-A", "EXT-FEATURE-B"]
      :tags: fast, big

   .. needextend:: EXT-FEATURE-B
      :links: EXT-FEATURE-A

.. list2need::
   :types: feature, req

   * (EXT-FEATURE-A)Feature A
     * (EXT-REQ-1)Requirement 1. It shall be fast.
     * (EXT-REQ-2)Requirement 2. It shall be big.
   * (EXT-FEATURE-B)Feature B


.. needextend:: EXT-REQ-1
   :status: closed
   :style: green_border

.. needextend:: EXT-REQ-2
   :status: open
   :style: red_border

.. needextend:: id in ["EXT-FEATURE-A", "EXT-FEATURE-B"]
   :tags: fast, big

.. needextend:: EXT-FEATURE-B
   :links: EXT-FEATURE-A