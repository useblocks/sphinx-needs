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

Need-IDs can be set by putting them in brackets in the line. Example: ``(REQ-1)My first requirement``.
If no ID is given, one gets generated from the title. See :ref:`list2need_ids` for both cases.

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
   A content line starting with ``*`` begins a new need instead of continuing the one
   above it, and a content line starting with ``:`` stays content —
   it is rendered as a field list in the need's body, and is not read as an option.

List structure
--------------
The used list structure was defined to be as small as possible.

Each line starting with a ``*`` will create a new need object.

To define a child-need, add **2 additional whitespaces** infront of ``*``.
This is called the indentation level and each level must have a need-type defined in the ``types`` option.

The indentation must be a multiple of 2 spaces, and one level is always exactly 2 spaces:
4 spaces mean level 2, not a second level 1.
An indentation that is not a multiple of 2 ends the build with an error.

Tabs cannot be used for the indentation.
Before the directive sees the line, a tab is expanded to the next tab stop (8 columns by default),
so the indentation it ends up producing depends on the column that tab happens to sit in.
A tab-indented line therefore usually ends the build,
and where the expansion does come out as a multiple of 2 it silently lands on a level that was never written.

A line starting **without** a ``*`` will be added to the prior one.
So it can be used to structure longer titles or content, and has no impact on the later representation.
Such a line must not start in the first column of the list; a line that does loses its first word.

.. _list2need_ids:

Need IDs
--------

An ID is recognised only as a bracketed group inside the line.
The group starts at the **first** ``(`` and, because it is matched greedily,
ends at the **last** ``)``.
It may contain any character except ``"``, ``'``, ``=`` and a line break,
which are excluded because the option syntax uses them.

Two consequences are worth knowing:

* A line that carries a second bracketed group, such as ``(REQ-1) The system (as defined) shall work``,
  produces the ID ``REQ-1) The system (as defined``.
  An ID of that shape is normally refused by :ref:`needs_id_regex`,
  and the need is then not created at all.
* A line with no leading ID but with a parenthetical elsewhere, such as ``Some (draft) title``,
  uses ``draft`` as the ID and removes it from the title.

So avoid brackets in a title that is also meant to carry an ID.

.. note::

   Despite the similar look, this is **not** the mechanism used by :ref:`need_part`.
   ``need_part`` anchors its match to the start of the text and accepts only word characters and ``-``,
   whereas ``list2need`` searches the whole line with a much wider character class.

Generated IDs
~~~~~~~~~~~~~

If a line contains no bracketed group, the ID gets generated from the title:

.. code-block:: text

   <prefix of the need type> + SHA1(<title>) as uppercase hex, cut to needs_id_length

Only the title feeds the hash.
The content, the document and the position in the list take no part in it,
and the need type contributes its prefix but nothing to the hash.
So the ID stays the same when the list gets reordered or the document gets renamed,
it changes whenever the title changes,
and the same title used at two levels of one list gives two different IDs, one per prefix.
See :ref:`needs_id_length` for the length and :ref:`needs_types` for the prefix of each type.

.. versionchanged:: 8.4.0

   A line whose bracketed group is empty, ``()``, gets its ID from the formula above,
   exactly as a line with no brackets at all does.
   Until 8.4.0 such a line was given its ID by the need directives' own generator
   instead — which reads :ref:`needs_id_from_title`, and hashes the content when the
   title is empty — so one list could produce two kinds of generated ID,
   chosen by two characters of punctuation.
   Under the default configuration both produced the same ID,
   so only a project that sets ``needs_id_from_title``,
   or writes ``()`` on a line with no title, sees a different ID than before.

.. warning::

   Because the document is not part of the input,
   two lines with the same title and the same need-type produce the **same ID**,
   even in different documents.
   The second need is then not created, and a warning reports the duplicated ID.
   Give such needs an explicit ID.

Markdown (MyST)
---------------

.. versionchanged:: 8.4.0

   Before 8.4.0 a ``{list2need}`` fence reported an error and created no needs,
   and the ``eval-rst`` block below was the only way to reach the directive
   from a Markdown document.

``list2need`` can be written as a fenced directive in a MyST Markdown document:

.. code-block:: markdown

   ```{list2need}
   :types: req, spec

   * (MD-REQ-1) A requirement written from Markdown
     * (MD-SPEC-1) And a specification below it
   ```

The list itself keeps the syntax described on this page:
it is read by ``list2need`` rather than by the host parser,
so it is the same in both kinds of document.
The **content** of each need is parsed by the host, so it is Markdown in a
``.md`` file and reStructuredText in an ``.rst`` file.

The directive still works inside an ``eval-rst`` block, where its content is
reStructuredText:

.. code-block:: markdown

   ```{eval-rst}
   .. list2need::
      :types: req, spec

      * (MD-REQ-1) A requirement written from Markdown
   ```

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

:nested: Needs of level 2 are placed inside the parent need (level 1) and so on.
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
      * (LIST2NEED-003) Feature 3

.. list2need::
   :types: feature

   * (LIST2NEED-001) Feature 1
   * (LIST2NEED-002) Feature 2
   * (LIST2NEED-003) Feature 3

Note that the ID must not contain the delimiter.
With the default delimiter ``.``, an ID such as ``(FEATURE.3)`` gets split before it is read,
which leaves ``(FEATURE`` as the title and generates an ID from it.
Use an ID without the delimiter, or set a different one via the ``delimiter`` option.

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

Only the **first** ``((...))`` region of a line is read, and the region is matched greedily:
it starts at the first ``((`` and ends at the last ``))``.
A line that carries two such regions therefore loses the text between them,
so keep all options of a need in one region.

Inside the region, options are written as ``name="value"`` pairs.
Instead of ``"`` also ``'`` can be used.
Text between two pairs is ignored, so the pairs may simply be separated by a space or by ``,``.

A value must be quoted. An unquoted value, as in ``((status=open))``, is silently ignored.

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
