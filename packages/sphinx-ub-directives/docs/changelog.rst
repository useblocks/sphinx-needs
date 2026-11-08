.. _changelog:

Changelog
=========

Unreleased
----------

- ⬆️ Templates render with minijinja 3 (``minijinja>=3.0.5,<4``, which was ``~=2.15``), the series ubCode renders
  with; the template corpus both tools are held to is recorded against 3.0.5 **(changed output)**
  (`#2475 <https://github.com/useblocks/sphinx-needs/pull/2475>`__)

  A value a template builds itself prints differently: a list or map with Python's quoting (``['a']``),
  ``items`` pairs as tuples, ``tojson`` spaced as ``json.dumps`` spaces it, and ``round`` half to even. Context
  data prints as the engine prints its values, so ``{{ rows }}`` is ``[1, 'a']``, which was ``[1, "a"]``.
  The full list is in sphinx-needs' changelog entry for the same move.

- ⬆️ Templates render with minijinja 3.1 (``minijinja>=3.1.0,<4``, which was ``>=3.0.5,<4``); the template corpus
  is recorded against 3.1.0, no case in it moves, and one is added **(changed output)**
  (`#2500 <https://github.com/useblocks/sphinx-needs/pull/2500>`__)

  A value a template builds or tests itself can render differently: ``true`` and ``false`` compare and sort as
  ``1`` and ``0`` (``[true, 2, false, 1, 0]|sort`` is ``[False, 0, True, 1, 2]``), ``max`` and ``groupby`` keep the
  first of equal items, ``title`` and ``capitalize`` follow Unicode's case mappings, a map reverses, a negative
  repeat is empty, and ``replace`` takes a count. Under the strict undefined of a template directive, ``|join`` of
  an undefined name is ``template_render_error``, where it was empty. ``4 is divisibleby(0)`` and a slice with a
  negative step, which crashed the engine, are now an error and a result (``[1, 2, 3][5:0:-1]`` is ``[3, 2]``).
  The full list is in sphinx-needs' changelog entry for the same move.

  A render's fuel now also counts the bytes and items it makes, writes or scans, so it bounds memory as well as
  time; the heaviest render in the corpus uses under 0.5% of it.

  ``|length`` and ``|count`` of an undefined name stay ``template_render_error``: minijinja-py 3.1.0's own filters
  make it ``0`` under strict undefined too, so a template that names either filter is rendered a second time to find
  one, and the page keeps the first render's text. The template corpus pins it in a new case,
  ``dialect-undefined-length-is-an-error`` (546 cases). The second render is temporary: it goes once a minijinja-py
  release fixes `minijinja#1028 <https://github.com/mitsuhiko/minijinja/issues/1028>`__.

- A template context file ending in ``.toml`` (``[parse.template_contexts.<name>] file``) is
  read as TOML 1.1, through ub-project's ``loads_toml``, as ``ubproject.toml`` itself is: an
  inline table may span lines or end with a trailing comma, and a string may use the ``\e``
  and ``\xHH`` escapes. A file that does not parse is still ``template_context_invalid``,
  with the same wording around the parser's message. In the template corpus the four
  ``dx-toml-1-1-*`` cases, which expected TOML 1.0's refusal, now expect their renders
  (``1``, ``1``, ``4`` and ``A``) and no finding, and contract section 4.3 names TOML 1.1; a
  vendored copy of that corpus is due a refresh
  (`#2476 <https://github.com/useblocks/sphinx-needs/pull/2476>`__).

.. _`release:0.1.0`:

0.1.0
-----

:Released: 2026-11-04

The first release: define your own Sphinx directives without writing Python, in
``ubproject.toml`` or ``conf.py``. A directive preset is an existing directive under a name of
your own, with its options preset, or project-wide defaults for an existing one; a template
directive renders a Jinja template with its argument, options and body. With Sphinx-Needs
installed, which is optional, a preset may be based on a need type (Sphinx-Needs 9.2.0 or later,
which the ``needs`` extra installs) and every template sees the project's variant data as ``var``.

- The first release: directive presets (``[parse.directive_presets]``),
  declared template directives (``[parse.directive_templates]``) with template contexts
  (``[parse.template_contexts]``) and ``var``, and the ``ub-template`` directive
  (``[parse] ub_template_enabled``), read from ``ubproject.toml`` to the same contract ubCode implements.
- The same settings can be given in ``conf.py`` (``ub_directive_presets``, ``ub_directive_templates``,
  ``ub_template_contexts``, ``ub_template_enabled``); a key ``ubproject.toml`` sets wins whole, and
  ``-D ub_template_enabled=...`` wins over both. Only ``ubproject.toml`` is read by ubCode.
- A preset based on a need type needs sphinx-needs 9.2 or later: it takes exactly the options the need
  type's directive matches, read through sphinx-needs' public ``resolve_need_option``; with an older
  sphinx-needs it is refused (``directive_preset_unknown_base``).
- A ``needs`` extra installs a sphinx-needs that need-type presets work with (9.2 or later).
