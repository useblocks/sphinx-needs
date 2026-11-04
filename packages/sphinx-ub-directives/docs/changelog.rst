.. _changelog:

Changelog
=========

Unreleased
----------

- A template context file ending in ``.toml`` (``[parse.template_contexts.<name>] file``) is
  read as TOML 1.1, through ub-project's ``loads_toml``, as ``ubproject.toml`` itself is: an
  inline table may span lines or end with a trailing comma, and a string may use the ``\e``
  and ``\xHH`` escapes. A file that does not parse is still ``template_context_invalid``,
  with the same wording around the parser's message. In the template corpus the four
  ``dx-toml-1-1-*`` cases, which expected TOML 1.0's refusal, now expect their renders
  (``1``, ``1``, ``4`` and ``A``) and no finding, and contract section 4.3 names TOML 1.1; a
  vendored copy of that corpus is due a refresh.

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
