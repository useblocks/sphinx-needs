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

Meta-data can be set via inline text. See :ref:`list2need_meta_data` for details.

Need-IDs get generated automatically (hash value), if not given.
IDs can be set by the prefix ``(ID)`` in the line. Example: ``(REQ-1)My first requirement``.
This mechanism is the same as the one used by :ref:`need_part`.

Options for the need-objects can be set by adding them like ``((status="open"))``.
For details please see :ref:`list2need_meta_data`.


.. code-block:: rst

   .. list2need::
      :types: req, spec, test
      :presentation: nested
      :delimiter: .

      * Need example on level 1
      * (NEED-002) Another Need example on level 1 with a given ID
        * Sub-Need on level 2 with status option set
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
     * Sub-Need on level 2 with status option set ((status='open'))
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

types
~~~~~

List of need-types, which are used for the different list-levels.
As input name the ``directive`` entry from the configuration variable  :ref:`needs_types` is used.

There is no default value and ``types`` must be set.

.. code-block:: rst

      .. list2need::
         :types: feature, function, test

         * Login user
           * Provide login screen
           * Create password hash
             * Recalculate hash and compare



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

links-down
~~~~~~~~~~
``links-down`` set automatically links between the different levels of the list.

.. code-block:: rst

   .. list2need::
      :types: req, spec, test
      :presentation: standalone
      :links-down: triggers, tests

      * (NEED-A)Login user
        * (NEED-B)Provide login screen
        * (NEED-C)Create password hash
          * (NEED-D)Recalculate hash and compare

``:links-down: triggers, tests`` will set a link from type ``triggers`` from ``NEED-A`` to ``NEED-B`` and ``NEED-C``.
``NEED-C`` will get a link from type ``tests`` to ``NEED-D``.

So links get set from the upper level down to all need-objects on the direct lower level (top-down approach).

The amount of given link-types must be the amount of used levels minus 1.

**Result from the above example**:

.. list2need::
   :types: req, spec, test
   :presentation: standalone
   :links-down: triggers, tests

   * (NEED-A)Login user
     * (NEED-B)Provide login screen
     * (NEED-C)Create password hash
       * (NEED-D)Recalculate hash and compare


tags
~~~~

``tags`` sets tags globally to all items in the list.

.. code-block:: rst

   .. list2need::
      :types: req, spec
      :tags: A, B

      * (NEED-A)Login user
        * (NEED-B)Provide login screen
        * (NEED-C)Create password hash
          * (NEED-D)Recalculate hash and compare


The tags ``A`` and ``B`` are attached to all ``NEED-A``, ``NEED-B``, ``NEED-C`` and ``NEED-D``.


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

        .. image:: /_images/logos/sphinx-needs-logo.png
           :align: center
           :width: 20%


.. list2need::
   :types: req, spec

   * Level 1 need and more
     * And a complex sub-need on level 2 with an image-directive.

     .. image:: /_images/logos/sphinx-needs-logo-old.png
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

.. _list2need_meta_data:

Set meta-data
~~~~~~~~~~~~~
Meta-data can be set directly in the related line via: ``((status="open"))``.
Or if the amount of option/values is getting too complex, in a second step
by using :ref:`needextend`.

The position of the option-string inside the line is not important.
Multiple options need to be separated by ``,``.
And instead of ``"`` also ``'`` can be used.

.. code-block:: rst

   .. list2need::
      :types: feature, req

      * (EXT-FEATURE-A)Feature A
        * (EXT-REQ-1)Requirement 1. It shall be fast. ((tags="A, fast", style="green_border"))
        * (EXT-REQ-2)Requirement 2. It shall be big. ((tags="A, big", style="red_border"))
      * (EXT-FEATURE-B)Feature B.
        Options are given in next line for readability
        ((status="done", tags="B", links="EXT-FEATURE-A"))

   .. needextend:: EXT-FEATURE-B
      :style: yellow


.. list2need::
   :types: feature, req

   * (EXT-FEATURE-A)Feature A
     * (EXT-REQ-1)Requirement 1. It shall be fast. ((tags="A, fast", style="green_border"))
     * (EXT-REQ-2)Requirement 2. It shall be big. ((tags="A, big", style="red_border"))
   * (EXT-FEATURE-B)Feature B.
     Options are given in next line for readability
     ((status="done", tags="B", links="EXT-FEATURE-A"))

.. needextend:: EXT-FEATURE-B
   :style: yellow