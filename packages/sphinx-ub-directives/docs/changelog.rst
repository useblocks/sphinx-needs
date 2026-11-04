.. _changelog:

Changelog
=========

Unreleased
----------

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
- Templates render with minijinja 3 (``minijinja>=3.0.5,<4``), the series ubCode renders with; the template
  corpus both tools are held to is recorded against 3.0.5.
