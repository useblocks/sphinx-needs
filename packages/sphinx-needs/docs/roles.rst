.. _roles:

Roles
=====

You can use Roles to get short information of needs inside single sentences.

.. _role_need:
.. _needref:

need
----

The role ``:need:`` will add title, id and a link to the need.

We use it to reference an existing need, without the need to keep title and link location manually in sync.

With ``[[`` and ``]]`` you can refer to defined and set :ref:`extra fields <needs_fields>`.

The possible variables are listed in the configuration documentation for :ref:`needs_role_need_template`.

.. syntax-example::

   .. req:: Sliced Bread
      :id: roles_req_1
      :status: open
      :value: 20
      :unit: slices

      | The requirement :need:`roles_req_1` is the most important one.
      | But we can also set :need:`a custom link name <roles_req_1>`.
      | And we can change the text even more e.g. :need:`[[value]] [[unit]] of [[title]] ([[id]] [[status]]) <roles_req_1>`.

.. note::

   You can customize the string representation by using the
   configuration parameters :ref:`needs_role_need_template` and
   :ref:`needs_role_need_max_title_length`.
   ``needs_role_need_template`` is rendered using `Jinja <https://jinja.palletsprojects.com/>`_ syntax.
   The explicit inline variant ``:need:`[[...]] <ID>``` is also rendered as
   Jinja, using ``[[`` and ``]]`` as the variable delimiters.
   RST-attributes like ``**bold**`` are **not** supported.

.. warning::

   If you refer to a whole :ref:`external need <needs_external_needs>`, the algorithm is different
   and you will only get the need id as link text.
   A reference to a part of an external need, ``:need:`EXT_ID.part```, is written as one to a part of a
   need of the project, with the part's text and ``EXT_ID.part`` (or the text given in the role).
   It links the part's anchor on the external page when the need's url ends in its id, as the default one does,
   and the need's url otherwise (see ``target_url`` in :ref:`needs_external_needs`).


.. _role_need_outgoing:

need_outgoing
-------------
.. versionadded:: 0.1.25

``:need_outgoing:`` adds a list of all outgoing links of the given need.
The list contains the need IDs only, no title or any other information is printed.

.. syntax-example::

   .. req:: Butter on Bread
      :id: roles_req_2
      :links: roles_req_1

      To get butter on our bread, we need to fulfill :need_outgoing:`roles_req_2`

.. _role_need_incoming:

need_incoming
-------------
.. versionadded:: 0.1.25

``:need_incoming:`` prints a list of IDs of needs which have set outgoing links to the given need.
Given a :ref:`need part <need_part>`'s address ``ID.part``, it lists only the needs linking that part, where ``ID``
lists every need linking the need, through one of its parts or whole, a link naming a part it does not have included.

.. syntax-example::

   The realisation of **Sliced Bread** is really important because the needs :need_incoming:`roles_req_1` are based on
   it.

.. _need_part:

need_part / np
----------------
.. versionadded:: 0.3.0

You can use ``:need_part:`` or as shortcut ``:np:`` inside needs to set a sub-id for a specific sentence/part.
This sub-ids can be linked and referenced in other need functions like links and co.

The used need_part id can be freely chosen, but should not contain any whitespaces or dots.

A part written ``(id) text`` has as its text everything after the ``(id)``, without white space at either end:
``(2) An acceleration`` and ``(2)An acceleration`` both have the text ``An acceleration``, and a text that starts
on the line after the ``(id)`` starts with its first word. White space and line breaks inside the text are kept.
A need has one part of an id: when its content marks an id more than once, the first role is the part, and every
later one is shown as its text alone, with no anchor, and reported as ``needs.duplicate_part_id``.
In LaTeX and texinfo output the part is anchored at the start of its text, except in a caption (of a figure, a code
block or a ``literalinclude``), where a LaTeX anchor would stop ``pdflatex``, and, in texinfo, in text that writer
writes as plain text (an admonition's title, a hyperlink's text, a ``centered`` line): there no anchor is written
at the text.

A need part is a named, addressable piece of one need: an id, a text, and the links that point at it.
It has no fields, no type, no status and no outgoing links of its own; a piece of a need that needs any of
those is a need of its own. A link to a part, ``<need id>.<part id>``, reads and counts as a link to its need:
its condition, the target types and the counts are the need's. It is a dead link when the need has no such part.

.. _need_stated_parts:

**Parts a need is given**

.. versionadded:: 9.4.0

A need may also be given parts its content does not mark ("stated" parts): an imported need by its record
(:ref:`needimport`), and a need created through the API by ``create_need(..., parts={"r1": "a stated part"})``
(:func:`~sphinx_needs.api.need.create_need`), a mapping of part id to text. A need whose content is read has the
parts its content marks, in the order written, then the given parts whose id its content does not mark, in the order
given. It takes a given part's text on one line: each run of white space that holds a line break (LF, VT, FF, CR,
NEL U+0085, LS U+2028 or PS U+2029) is one space, and every other character, the text's ends included, is kept, so
the stored part, ``needs.json``, a filter and every place the text is written have that one line. Where both give
an id, the content's part is the part, with its text, and nothing is reported. A part id is one word: a given part
whose id holds white space (a character of Unicode's ``White_Space`` property) or a control character (one of the
general category ``Cc``) is not taken by a need whose content is read, and nothing is reported; ``create_need``
refuses one. A stated part is a part like any other: a link to it is live, its back links are computed, and a
filter that asks for parts sees it. So does a view's filter while :ref:`needs_views_include_parts` is unset or
``True``: a view whose filter an imported need passes lists that need's stated parts too, and while the value is
unset reports ``needs.views_include_parts`` for it; set the value to ``False`` to select needs alone, or to
``True`` to keep the parts without the report. There is no option to state a part in markup: there, a part is
written in the content.

The stated parts of a need on a page are shown after its content, in a block with the class
``needs-stated-parts``: one line per part, in order, each its text, its id and its anchor ``<need id>.<part id>``,
as a part in the content is shown, with the class ``need-part-stated`` beside ``need-part``. A line shows the
part's stored text, which is on one line. html, singlehtml, epub, LaTeX and texinfo anchor each line; text and man,
which write no anchors, print its text and its id after the need's content (text in the need's cell, which it
writes on one line; man with no blank line before the first). A link or a ``:need:`` reference to a stated part
lands on its line. A need with no stated part has no block. A hidden need, whose content is not read, has the
parts it is given alone, their texts as given, and shows nothing, and an external need
(:ref:`needs_external_needs`) has the parts its record states, as given.

A need's parts are stored in order, its content's then its stated ones, and the block, needextract, a needtable's
``:show_parts:`` rows, needlist and needflow list them in that order. A needtable whose filter selects parts sorts
them as it sorts its rows, and :ref:`links_from_match` and a derived join take them in part-id order.

.. syntax-example::

   .. req:: Car must be awesome
      :id: my_car_1
      :tags: car
      :status: open

      My new car must be the fastest on the world. Therefor it shall have:

      * :need_part:`(1)A top speed of 300 km/h`
      * :np:`(2) An acceleration of 200 m/s² or much much more`

      And we also need --> :np:`(awesome_3) a turbo button`!


   .. spec:: Build awesome car
      :id: impl_my_car_1
      :links: my_car_1.1, my_car_1.2

      Requirements :need:`my_car_1.1` and :need:`my_car_1.2` are no problem and can
      be realised by doing rocket science.

      But no way to get :need:`my_car_1.awesome_3` realised.


   Reference to a part of a need from outside need scope: :need:`my_car_1.2`.

**Presentation in needflow**

What a :ref:`needflow` draws for a link to a need part follows :ref:`needs_views_include_parts`
(:ref:`needflow_need_parts`).
With ``False``, the default from 10.0, a needflow draws needs alone, and a link to a part of a need it draws is an
edge to that need in the link type's ``style_part``, dotted by default, labelled with the part's id:
``impl_my_car_1``, linking ``my_car_1.1`` and ``my_car_1.2``, is one edge to ``my_car_1`` labelled ``1, 2``.
With ``True``, and while it is unset through 9.x, a part the needflow's filter selects, of a need it also selects,
is a node inside that need, and a link to it an edge to that node; a link to a part the filter does not select
draws no edge.
This documentation sets ``True``, and the filter below selects the two needs and none of their parts:
the needflow draws the two needs, and no edge between them.

.. syntax-example::

   .. needflow::
      :filter: id in ["my_car_1","impl_my_car_1"]

**Presentation in needtable**

Please see :ref:`needtable_show_parts` of :ref:`needtable` configuration documentation.

.. syntax-example::

   .. needtable::
      :style: table
      :filter: 'car' in tags and is_need
      :show_parts:
      :columns: id, title, incoming, outgoing

.. _need_count:

need_count
----------
.. versionadded:: 0.3.1

Counts found needs for a given filter and shows the final amount.

The content of the role must be a valid filter-string as used e.g. by :ref:`needlist` in the ``:filter:`` option.
See :ref:`filter_string` for more information.

.. syntax-example::

   | All needs: :need_count:`True`
   | Specification needs: :need_count:`type=='spec'`
   | Open specification needs: :need_count:`type=='spec' and status=='open'`
   | Needs with tag *test*: :need_count:`'test' in tags`
   | Needs with title longer 10 chars: :need_count:`search("[\\\\w\\\\s]{10,}", title)`
   | All need_parts: :need_count:`is_part`
   | All needs containing need_parts: :need_count:`is_need and len(parts)>0`

.. note::

   If backslashes ``\`` are used inside the regex function ``search``, in a role the text loses one level of
   backslashes before the filter is read, so a backslash of the pattern is written four times there
   (``"\\\\d"``, as in the example above), or avoided with a character class (``"[.]"``).

.. note::

   ``need_count`` tests the given filter on needs and, where :ref:`needs_views_include_parts` is true (as in this
   documentation, and unset in 9.x), on need parts too: then the result may count found needs *and* found need
   parts. To count needs alone, add ``is_need`` to your filter. With the value false (the meaning of unset from
   10.0) it counts needs alone, and ``is_part`` counts nothing.


.. _need_count_ratio:

Ratio
~~~~~

.. versionadded:: 0.5.3

To calculate the ratio of one filter to another filter, you can define two filters separated by ``_?_``
(question mark surrounded by one space on each side).

.. syntax-example::

   :need_count:`status == open and type == "spec" ? type == "spec"` % of our specifications are open.


.. _need_func:

need_func
---------
.. versionchanged:: 9.0.0

   The ``need_func`` role is removed; use :ref:`ndf` instead.

.. _ndf:

ndf
---
.. versionadded:: 4.0.0

Executes a :ref:`need dynamic function <dynamic_functions>` and uses the return values as content.

.. syntax-example::

    A nice :ndf:`echo("first test")` for dynamic functions.

.. _role_variant:

variant
-------
.. versionadded:: 8.2.0

Resolves a reference into :ref:`needs_variant_data` and is *immediately*
replaced during parsing by a text node holding the looked-up value.

The role content is a dotted path into the configured variant data, rooted at
``var`` (the ``var`` root is implicit and must not be written).

Given the configuration:

.. code-block:: python

    needs_variant_data = {
        "platform": "arm",
        "build": {"opt_level": 2},
    }

then in a document:

.. code-block:: rst

    Platform: :variant:`platform`
    Optimisation level: :variant:`build.opt_level`

resolves to ``arm`` and ``2`` respectively.

Type handling
~~~~~~~~~~~~~

The role always produces a single text node. The resolved value is serialised
to text as follows:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Variant data value
     - Rendered text
   * - String (``"arm"``)
     - The string itself (``arm``).
   * - Integer / float (``2``, ``1.5``)
     - Its ``str()`` form (``2``, ``1.5``).
   * - Boolean (``True``)
     - ``True`` / ``False`` (Python's ``str(bool)``).
   * - Array (``["arm", "x86"]``)
     - The elements joined into a comma-separated string (``arm, x86``).
   * - Mapping (``{...}``)
     - Not allowed — emits a warning and renders empty text (reference a leaf
       value instead).

The lookup is a constrained ``var.*`` path resolution (the same as used by
:ref:`needs_variant_data` field references), not an arbitrary expression: no
operators, function calls, or item access are allowed. An invalid reference,
an unknown key, or a path that resolves to a mapping emits a ``needs.variant``
warning and produces empty text.

.. note::

    The value is resolved at parse time and baked into the document. Changing
    :ref:`needs_variant_data` triggers a full rebuild so the resolved values
    stay current, and so does editing the *contents* of a
    :ref:`needs_variant_data_file` without changing its path, because the merged
    data is part of the configuration that is compared between builds.
