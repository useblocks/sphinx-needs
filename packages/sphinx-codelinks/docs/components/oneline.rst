.. _oneline:

One Line Comment Style
======================

Many users have raised concerns about the complexity of defining ``Sphinx-Needs`` need items with RST in source code.
Therefore, ``CodeLinks`` provides a customizable one-line comment style pattern to define ``need items``
to simplify the effort required to create a need in source code.

:ref:`Here <oneline_comment_style>` is the default one-line comment style.

**Additional examples and use cases:**

For more comprehensive examples and advanced configurations, see the `test cases <https://github.com/useblocks/sphinx-needs/tree/master/packages/sphinx-codelinks/tests>`__.

Start and End sequences
-----------------------

To have a better understanding of the syntax of a one-line comment, we will break it down as follows:

**start_sequence** defines the characters where the one-line comment starts.
**end_sequence** defines the characters where the one-line comment ends.

The text between **start_sequence** and **end_sequence** contains the fields of a ``need item``.

field_split_char
----------------

Since there are always multiple fields for a need,

**field_split_char** defines the character to split the text into multiple ``pieces/fields``.

needs_fields
------------

Each field in a need may have different data types.
It could be a string if it is a field for ``id`` or ``title``. On the other hand,
it could be a list of strings as well, if the field requires a list of strings to represent ``links``.

This is where **needs_fields** comes in.

**needs_fields** contains the fields that are required for needs:

Each need field defines its:

- name
- data type (Optional)
- default value (Optional)

The examples in the following sections use :ref:`the default <oneline_comment_style>` to
explain the syntax of the one-line comment.

DataType
~~~~~~~~

By default, a field has the data type of ``str``.

For example, if the field definition is as follows:

.. code-block:: python

   {
       "name": "title
   }

It's equivalent to:

.. code-block:: python

   {
       "name": "title",
       "type": "str"
   }

If the field is expected to have a list of strings, it shall be defined as the following:

.. code-block:: python

   {
       "name": "links",
       "type": "list[str]"
   }

When the field has data type ``list[str]``:

- the strings must be given within ``[`` and ``]`` brackets
- ``,`` shall be used as the separator.

For example, with the following **needs_fields** configuration:

.. _`fields_config`:

.. tabs::

   .. code-tab:: python

      needs_fields = [
         {"name": "title"},
         {"name": "id"},
         {"name": "type", "default": "impl"},
         {"name": "links", "type": "list[str]", "default": []},
      ],

   .. code-tab:: toml

      needs_fields = [
         { name = "title" },
         { name = "id" },
         { name = "type", default = "impl" },
         { name = "links", type = "list[str]", default = [] },
      ]

the one-line comment shall be defined as follows:

.. tabs::

   .. code-tab:: c

      // @ title, id_123, implementation, [link1, link2]

   .. code-tab:: rst

       .. implementation:: title
           :id: id_123
           :links: link1, link2

Default value
~~~~~~~~~~~~~

The value mapped to the key ``default`` in a need field definition is the default value of a need field
when it is not given in the need definition.

For example, with the following needs_fields definition,

.. tabs::

   .. code-tab:: python

      needs_fields = [
         {
            "name": "title"
         },
         {
            "name": "type",
            "default": "implementation"
         },
      ]

   .. code-tab:: toml

      needs_fields = [
         { name = "title" },
         { name = "type", default = "implementation" }
      ]

the following need definition in source code is equivalent to RST shown below:

.. tabs::

   .. code-tab:: c

      // @ title here and default is used for type

   .. code-tab:: rst

      .. implementation:: title here and default is used for type

Positional Fields
~~~~~~~~~~~~~~~~~

All of the fields defined in ``needs_fields`` are positional fields.
This means the ``order of needs_fields`` determines ``the position of the field`` in the one-line comment.

For example, with the mentioned :ref:`needs_fields definition <fields_config>`

field ``title`` is the first element in the list, so the string of the title must be
the first field in the one-line comment.

.. tabs::

   .. code-tab:: c

      // @ this is title, this is id, this_type, [link1, link2]

   .. code-tab:: rst

      .. this_type:: this is title
         :id: this is id
         :links: link1, link2

.. note:: A field without a default value cannot follow a field that has a default value set.

Escaping Characters
~~~~~~~~~~~~~~~~~~~

If the value of the field contains characters that are ``field_split_char`` or angular brackets ``[`` and ``]``,

a leading character ``\`` must be used to escape them.

For example, with the mentioned :ref:`needs_fields definition <fields_config>`,
``,`` is escaped with ``\`` and is not considered as a separator.

.. tabs::

   .. code-tab:: c

      // @ title\, 3, IMPL_3 , impl, []

   .. code-tab:: rst

      .. impl:: title, 3
         :id: IMPL_3

The other example shows the angular brackets ``[`` and ``]`` and comma being escaped:

.. tabs::

   .. code-tab:: c

      // @ title 3, IMPL_3 , impl, [\[SPEC\,_1\]]

   .. code-tab:: rst

      .. impl:: title 3
         :id: IMPL_3
         :links: [SPEC,_1]

To have a backslash ``\`` as a literal in the value, use ``\\`` as shown in the following:

.. tabs::

   .. code-tab:: c

      // @ title\\ 3, IMPL_3 , impl, [\[SPEC\,_1\]]

   .. code-tab:: rst

      .. impl:: title\ 3
         :id: IMPL_3
         :links: [SPEC,_1]

.. caution:: Field values can never contain any newline characters ``\r`` or ``\n``.

.. _`oneline_invalid`:

Invalid markers
---------------

A line that starts like a marker but does not fit the style creates no need, and is
reported as one of these kinds, the kind leading the message:

- ``too_few_fields`` -- fewer fields than the style requires (the fields with no default):
  ``1 given fields, minimum is 2``;
- ``too_many_fields`` -- more fields than ``needs_fields`` defines:
  ``5 given fields, maximum is 4``;
- ``missing_square_brackets`` -- a ``list[str]`` field given without ``[`` and ``]``;
- ``not_start_or_end_with_square_brackets`` -- a ``list[str]`` field whose brackets are not
  its first and last characters, such as ``[REQ_1];``;
- ``newline_in_field`` -- a field holding a newline (not produced from a source file,
  which is parsed one line at a time);
- ``docstring_tag`` -- a line of a Python docstring (never a ``#`` comment) whose start
  sequence is directly followed by a docstring tag such as ``param``, ``return`` or
  ``raises`` in the Epydoc field shape, ``:`` directly or one word and ``:``
  (``@return: text``, ``@param a: text``):
  ``'@param' is a docstring tag, not a one-line need; use a start sequence that docstrings
  do not contain``. A start sequence the docstrings also use cannot tell a need from
  documentation, so choose another one, ``[[`` for example.

A line with nothing between the start and end sequences is not a marker. A marker that
fits the style but whose need Sphinx-Needs refuses -- an id that does not match
``needs_id_regex``, say -- is reported too, with the Sphinx-Needs reason leading the
message: ``invalid_id: one-line need could not be created: Given ID 'b' does not match
configured regex '^[A-Z0-9_]{5,}'``.

In a build, the ``src-trace`` directive reports each at the marker's file and line, relative
to the git root (else the source directory), as a ``codelinks.oneline`` warning:

.. code-block:: text

   src/x.cpp:3: WARNING: too_few_fields: 1 given fields, minimum is 2 [codelinks.oneline]

The build goes on, without that need; with ``-W`` it fails. One entry,
``suppress_warnings = ["codelinks.oneline"]``, silences them all. A project that no
``src-trace`` directive traces creates no needs, and reports none. A file that two
directives' scopes share is analysed by each, and each reports its markers. ``codelinks
analyse`` prints the parser's kinds to the console; it creates no needs, so a need
Sphinx-Needs refuses is reported by a build only.

**A one-character start sequence without the field separator is not a marker.** When the
start sequence is a single character -- the default ``@`` -- and the text after it holds no
``field_split_char``, while the style requires more than one field, the line is left alone:
no need and no warning. That is what keeps documentation tags quiet on the default style:

.. code-block:: c

   /**
    * @brief Does a, IMPL_1
    * @param x the value
    * @return nothing
    */

``@param x the value`` and ``@return nothing`` are not markers; ``@brief Does a, IMPL_1``
has the separator, so it is the need ``IMPL_1`` titled ``brief Does a``, as it always was.
A tag line that does contain a comma is read as a marker, and warns if it does not fit the
style, or if it fits but Sphinx-Needs refuses the need -- an id that does not match
``needs_id_regex``, say.
A multi-character start sequence such as ``[[`` is specific enough to be a marker on its
own, so ``[[ only-title ]]`` on a style requiring two fields warns ``too_few_fields``.
