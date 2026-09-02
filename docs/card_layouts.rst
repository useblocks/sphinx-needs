.. _card_layouts:

Card layouts
============

.. versionadded:: 8.4.0

A **card layout** describes what a need shows — a header, a meta region, a footer, a side
region — as a small dictionary of options, instead of as hand-written layout strings.

Card specifications are given in :ref:`needs_card_layouts`. During configuration they are
compiled into ordinary :ref:`needs_layouts` entries, so a card can be used anywhere a
layout name is accepted: the ``:layout:`` option, :ref:`needs_default_layout`,
:ref:`needextract`, and services.

.. code-block:: python

   needs_card_layouts = {
       "product": {
           "meta": {"exclude": ["layout", "style"]},
           "footer": ["id", "type"],
           "collapse": "closed",
       }
   }

.. code-block:: rst

   .. req:: A requirement
      :id: REQ_1
      :layout: product

      The body of the need.

Card layouts are the recommended way to adjust how needs are rendered.
:ref:`needs_layouts` remains fully supported as the escape hatch for layouts that the card
vocabulary cannot express — nothing about it changes, and the two can be used side by side.

Writing a specification
-----------------------

Every key is optional. A specification with no keys at all is the ``clean`` card: a header
with the type name, title, id and a disclosure button, a meta region with all fields and
links, and the need's content.

``extends``
~~~~~~~~~~~

Name of another specification to inherit from — either one of your own cards, or one of the
:ref:`built-in specifications <card_layouts_builtins>`. Keys given by the card win, keys it
omits are inherited. The ``meta`` and ``side`` sub-tables are merged key by key, so a card
can change a single option of its base.

.. code-block:: python

   needs_card_layouts = {
       "with_image": {"extends": "clean_r"},
       "with_image_closed": {"extends": "with_image", "collapse": "closed"},
   }

Base names are resolved built-ins first, then your own cards. A chain that returns to a
name it already visited is a configuration error.

``header``
~~~~~~~~~~

A boolean, ``True`` by default. The header holds the need's type name, title and id.
Setting it to ``False`` produces a card with no header row — see
:ref:`card_layouts_limits` for what that implies for the other regions.

``content``
~~~~~~~~~~~

May only be ``True``. A need always renders its content; the key exists so that a
specification can state it.

``meta``
~~~~~~~~

Either ``False``, for a card without a meta region, or a table:

``fields``
   Which tier of need fields to show. One of:

   ``"stored"``
      the fields the need carries (default),
   ``"effective"``
      the same fields including schema defaults,
   ``"all"``
      every field, including the internal ones normally hidden from layouts.

``include``
   A list of field names. When given, exactly these fields are shown, in this order,
   instead of a whole tier.

``exclude``
   A list of field names to leave out.

``empties``
   A boolean, ``False`` by default. When true, fields with no value are shown anyway.

``links``
   A boolean, ``True`` by default. When false, no link fields are shown at all.

``links_back``
   A boolean, ``True`` by default. See :ref:`card_layouts_limits`.

.. code-block:: python

   needs_card_layouts = {
       "brief": {"meta": {"include": ["status", "tags"], "links": False}},
       "verbose": {"meta": {"fields": "all", "empties": True}},
       "no_meta": {"header": False, "meta": False},
   }

``footer``
~~~~~~~~~~

An ordered list of :ref:`elements <card_layouts_elements>`, rendered as one line each below
the need's content.

``side``
~~~~~~~~

Either ``False``, for a card without a side region, or a table describing a column beside
the need:

``elements``
   An ordered list of :ref:`elements <card_layouts_elements>`. An empty list means no side
   region, exactly as ``side = False`` does — either spelling declines a side region a card
   would otherwise inherit through ``extends``.

``position``
   ``"left"`` or ``"right"``, ``"left"`` by default.

``span``
   ``"full"`` (default) makes the side column reach down past the need's content;
   ``"partial"`` stops it after the meta region, so the content runs the full width below
   it.

.. code-block:: python

   needs_card_layouts = {
       "illustrated": {
           "side": {"elements": ["image:picture"], "position": "right", "span": "partial"}
       }
   }

``collapse``
~~~~~~~~~~~~

How the meta region's disclosure behaves. One of:

``"honour"``
   the need's own ``:collapse:`` option decides (default),
``"closed"``
   the meta region starts collapsed,
``"open"``
   the meta region is shown with no toggle at all.

The disclosure button is only emitted for a card that has both a header and a meta region,
since there would otherwise be no row for it to toggle.

.. _card_layouts_elements:

Elements
--------

``footer`` and ``side`` range over the same set of elements:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Element
     - Renders
   * - ``id``
     - The need's id, as a link to the need.
   * - ``title``
     - The need's title. Only allowed when ``header`` is ``False``, and in at most one
       region, so that a need's title appears exactly once.
   * - ``type``
     - The need type's display name.
   * - ``layout_echo``
     - ``layout:`` followed by the name of the layout in use.
   * - ``style_echo``
     - ``style:`` followed by the need's style.
   * - ``field:<name>``
     - The value of the need field ``<name>``.
   * - ``image:<name>``
     - The image whose path is the value of the need field ``<name>``, centered.

Field names must consist of letters, digits, underscores and hyphens, and start with a
letter or underscore. A name that no field is registered under is reported as a warning,
because it would silently render nothing.

A prefixed element's payload is always a **field name**:
``image:diagram`` shows the image the need's ``diagram`` field points to —
the payload is never itself a literal path or URL.

An element with no value renders nothing, exactly as it does for :ref:`needs_layouts`.

.. _card_layouts_object_form:

The object form
~~~~~~~~~~~~~~~

Every element string is shorthand for an *object* — a dictionary with a ``type`` key:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - String
     - Object
   * - ``"id"``
     - ``{"type": "id"}``
   * - ``"field:owner"``
     - ``{"type": "field", "field": "owner"}``
   * - ``"image:diagram"``
     - ``{"type": "image", "field": "diagram"}``

Both spellings are valid wherever elements are accepted, and mix freely in one list.
An object without options compiles to **exactly** the same layout as its string shorthand —
the strings stay valid forever and remain the documented default.
The object form exists to carry options:

.. list-table::
   :header-rows: 1
   :widths: 12 12 76

   * - Option
     - On type
     - Value
   * - ``height``
     - ``image``
     - The rendered height:
       a number with an optional ``px``, ``em``, ``rem``, ``%`` or ``pt`` unit,
       at most 16 characters. A bare number means pixels.
   * - ``width``
     - ``image``
     - The rendered width, with the same value grammar as ``height``.
   * - ``label``
     - ``field``
     - Replaces the field name in the rendered ``name: value`` pair:
       1–64 characters of letters, digits, spaces and ``_().,/-``,
       starting and ending alphanumeric,
       with an underscore only directly between letters or digits
       (``user_name`` is valid, ``Owned_ by`` and ``a__b`` are not).

.. code-block:: python

   needs_card_layouts = {
       "illustrated": {
           "footer": [
               "id",
               {"type": "field", "field": "owner", "label": "Owned by"},
           ],
           "side": {
               "elements": [{"type": "image", "field": "picture", "height": "40px"}]
           },
       }
   }

``field`` is required for the ``field`` and ``image`` types and forbidden for all others.
Its value follows the same field-name grammar as the string shorthand,
and the payload invariant above holds unchanged:
the value of ``field`` is a **field name**, never a literal path or URL.
No other type takes any option;
an option on the wrong type, an unknown key, a missing or extra ``field``,
or a value outside its grammar makes the specification invalid —
the card is reported and skipped, exactly like any other invalid specification.

.. _card_layouts_builtins:

Built-in specifications
-----------------------

The built-in layouts are also available as specifications, which makes them usable as
``extends`` bases. They are data only: they are never registered as layouts, and a card
always compiles to a new, separately named entry.

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Name
     - Specification
   * - ``clean``
     - every key at its default
   * - ``clean_l`` / ``clean_lp`` / ``clean_r`` / ``clean_rp``
     - ``clean`` plus ``side`` showing ``image:image``, left or right, full or partial
   * - ``complete``
     - ``meta`` on the ``effective`` tier excluding ``layout`` and ``style``, plus a footer
       echoing both
   * - ``focus``
     - no header, no meta, a footer showing the id — note that this corresponds to the
       built-in ``focus_f`` layout, not to the built-in ``focus``, which has no footer at
       all. The naming is deliberate and shared with the same vocabulary in ubCode; the
       bare built-in ``focus`` is written ``header = False``, ``meta = False``,
       ``footer = []``.
   * - ``focus_l`` / ``focus_r``
     - no header, no meta, the id in a side region on the left or right
   * - ``debug``
     - ``meta`` on the ``all`` tier with empty fields shown, disclosure pinned open
   * - ``test``
     - an alias for ``clean``
   * - ``focus_f``
     - an alias for ``focus``

Grids
-----

Which :ref:`grid <grids>` a card compiles to follows from the regions it declares:

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Regions
     - Grid
   * - header + meta
     - :ref:`grid_simple`
   * - header + meta + footer
     - :ref:`grid_simple_footer`
   * - header + meta + side (``full``)
     - :ref:`grid_simple_side_left` / :ref:`grid_simple_side_right`
   * - header + meta + side (``partial``)
     - :ref:`grid_simple_side_left_partial` /
       :ref:`grid_simple_side_right_partial`
   * - content only
     - :ref:`grid_content`
   * - content + footer
     - :ref:`grid_content_footer`
   * - content + side
     - :ref:`grid_content_side_left` / :ref:`grid_content_side_right`
   * - content + side + footer
     - :ref:`grid_content_footer_side_left` /
       :ref:`grid_content_footer_side_right`

.. _card_layouts_examples:

Rendered examples
-----------------

The two cards below are declared in this documentation's own ``ubproject.toml`` and read
through :ref:`needs_from_toml`, so what follows is this page rendering its own
configuration.

``card_profile`` extends the built-in ``clean`` with a side region holding the need's image
and id. Since ``span`` is ``"partial"``, the side column stops after the meta region and the
content runs the full width below it — the :ref:`grid_simple_side_left_partial` grid.

.. code-block:: toml

   [needs.card_layouts.card_profile]
   extends = "clean"

   [needs.card_layouts.card_profile.meta]
   exclude = ["layout", "style"]

   [needs.card_layouts.card_profile.side]
   elements = ["image:image", "id"]
   position = "left"
   span = "partial"

.. syntax-example::

   .. spec:: A specification with a picture
      :id: EX_CARD_PROFILE
      :author: daniel
      :image: _images/daniel.png
      :status: open
      :tags: example
      :layout: card_profile

      The side region shows the value of the ``image`` field, then the need's id.

Compare this with the hand-written ``example`` layout in :ref:`own_layouts`, which builds its
image path out of the ``author`` value with a ``{{author}}`` placeholder. A card names the
*field* holding the path instead, because a specification is never interpolated into a layout
string — which is also why the hand-written layout stays the right tool for that job.

``card_summary`` shows two named fields and no links, and puts the id, the type and the layout
name in a footer — the :ref:`grid_simple_footer` grid. ``collapse = "closed"`` starts the meta
region collapsed, so the card opens as a title bar above a footer.

.. code-block:: toml

   [needs.card_layouts.card_summary]
   collapse = "closed"
   footer = ["id", "type", "layout_echo"]

   [needs.card_layouts.card_summary.meta]
   include = ["status", "author"]
   links = false

.. syntax-example::

   .. req:: A requirement summarised on a card
      :id: EX_CARD_SUMMARY
      :author: daniel
      :status: open
      :tags: example
      :layout: card_summary

      Use the chevron in the header to open the meta region.

.. _card_layouts_limits:

Limits
------

The card vocabulary is compiled onto the existing grid and layout machinery, which it does
not extend. That leaves a small number of documented differences:

Not every combination of regions has a grid
   A card with a header, a side region **and** a footer, or a card with a meta region but no
   header, cannot be built from the available grids. Such a specification is reported and
   skipped.

A headerless side region is always full height
   There is no partial side grid for headerless cards, so ``span = "partial"`` is reported
   and rendered as ``"full"``.

``links_back`` cannot be switched off on its own
   The link types are not yet known when card layouts are compiled, so a card with
   ``links = True`` and ``links_back = False`` is reported and rendered with back links.
   To drop link lines entirely, set ``links = False``.

``collapse = "open"`` removes the toggle
   The meta region is always shown, but there is no button to collapse it — the need's own
   ``:collapse:`` option cannot be overridden by a layout, only left out.

``"stored"`` and ``"effective"`` render the same fields
   The renderer shows the fields a need actually carries, whichever tier is asked for. The
   distinction is kept in the vocabulary because it is meaningful in other tools that
   consume the same specifications.

A header without a meta region leaves an empty band
   The header grids always emit a meta row, so ``meta = False`` together with
   ``header = True`` shows an empty striped row. Use ``header = False`` for a card with no
   metadata at all.

``id`` in a side region renders horizontally
   The vertical id strip of the built-in ``focus_l`` and ``focus_r`` layouts comes from CSS
   selected on those layout names. A card compiles to its own name and therefore renders the
   id in the normal reading direction.

Layouts registered by services are not part of the collision set
   Services register their layouts later in the build than card layouts are compiled, so a
   card named after one of them — ``github``, for the :ref:`GitHub service <github_service>`
   — takes precedence over it silently, exactly as a :ref:`needs_layouts` entry of that name
   does today.

Invalid specifications
----------------------

A specification that cannot be compiled is reported as a ``needs.card_layout`` warning and
skipped. The build continues, and every other card still compiles. A card is also skipped,
rather than used, when its name is already taken by a built-in layout or by a
:ref:`needs_layouts` entry.

To silence these warnings, add them to Sphinx's ``suppress_warnings``:

.. code-block:: python

   suppress_warnings = ["needs.card_layout"]

.. seealso::

   :ref:`layouts_styles`
      Layouts, styles and grids in general.

   :ref:`own_layouts`
      Writing ``needs_layouts`` entries by hand.

   :ref:`layout_functions`
      The functions available inside a hand-written layout.
