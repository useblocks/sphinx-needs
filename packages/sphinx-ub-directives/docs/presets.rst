Directive presets
=================

A directive preset is a new directive name that is an existing directive with preset options,
or project-wide option defaults for an existing directive.
Declare one in ``ubproject.toml``, keyed by the name you will write in your documents:

.. code-block:: toml

   # A new directive: a requirement that starts as a draft (needs sphinx-needs).
   [parse.directive_presets.req-draft]
   base = "req"
   description = "A requirement that starts as a draft"
   argument = "Untitled requirement"
   options = { status = "draft", tags = "triage" }

   # A note that always carries the class "callout", plus any the author adds.
   [parse.directive_presets.callout]
   base = "note"
   append_options = { class = "callout" }

   # Project-wide defaults for sphinx-design's dropdown itself.
   [parse.directive_presets.dropdown]
   base = "dropdown"
   options = { icon = "pencil" }

Then write the preset like any directive, in reStructuredText or MyST Markdown:

.. code-block:: rst

   .. req-draft:: Export the report as PDF
      :id: REQ_042

   .. callout::
      :class: wide

      Rendered with the classes ``callout wide``.

A use of a preset is its base directive with the options merged in:
it renders, is checked and is indexed exactly as the base written with those options.
A need-type base gives each need that type, and the output carries no trace of the preset.

Set up a preset
---------------

1. Pick the base: a built-in directive, one from a loaded extension (such as sphinx-design's ``dropdown``),
   or a sphinx-needs need type.
2. Pick the name. A new name must not already be a directive;
   the same name as the base sets defaults for the base itself (a *self-preset*).
3. Choose how each option combines with what a use writes:
   ``options`` are defaults (a written value replaces the default),
   ``append_options`` go in front of a written value (``class`` and ``class-*`` options only),
   and ``force_options`` cannot be changed by a use.
4. Build. A preset with a problem is reported once, at its ``ubproject.toml`` entry, and left out.

Which value wins, from highest to lowest:
a forced value; what the use writes (for an appended option, the preset's values first);
the preset's default; the base's own defaults (a field's ``default``, ``needs_global_options``).

Reference
---------

Each ``[parse.directive_presets.<name>]`` entry takes:

``base`` (string, required)
   The directive the preset is. It cannot be another preset (presets do not chain),
   and a need type spelled with upper-case letters cannot be a base:
   Sphinx looks every directive name up in lower case, so such a type is not usable as a directive.
   A preset of a directive that also has a self-preset is the original directive, without the self-preset's values.
``description`` (string)
   The text an editor shows for the preset (ubCode); Sphinx does not use it.
``argument`` (string or number)
   The argument a use gets when it writes none, for a base that takes one.
``options``, ``append_options``, ``force_options`` (tables of strings, booleans or numbers)
   Option values by the base's option names. Write a flag option as ``true``;
   ``false`` cannot switch a flag off. A number is its decimal text;
   ``true`` for an option that is not a flag is the text ``true``.

A use that writes a forced option is warned (``ub_directives.preset_forced_option``) and the preset's value is used.

Each check runs once per build; the warning names the entry path (``[parse.directive_presets.x.base]``):

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Warning (``ub_directives.<code>``)
     - When
   * - ``directive_preset_unknown_base``
     - ``base`` is missing, names no directive, or names a need type spelled with upper-case letters.
   * - ``directive_preset_base_is_preset``
     - ``base`` names another preset.
   * - ``directive_preset_name_taken``
     - The name is already a directive other than the preset's base, or two presets' names differ only in case.
   * - ``directive_preset_unknown_option``
     - An option the base does not take.
   * - ``directive_preset_invalid_value``
     - A value the base's option rejects, or an entry that is not a preset at all.
   * - ``directive_preset_option_conflict``
     - The same option in two of ``options``, ``append_options`` and ``force_options``.
   * - ``directive_preset_append_not_list``
     - ``append_options`` for an option other than ``class`` or ``class-*``.
   * - ``directive_preset_argument_not_accepted``
     - ``argument`` for a base that takes none.
   * - ``directive_preset_identity_option``
     - The base's ``:name:``, or a need's ``:id:``: an option that identifies each use.
   * - ``directive_preset_unknown_key``
     - An entry key other than the six above; the preset is kept.

In a MyST page, an option the base does not know is dropped with a warning rather than failing the directive,
as MyST does for every directive.
