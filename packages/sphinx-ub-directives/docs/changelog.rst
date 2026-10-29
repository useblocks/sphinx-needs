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
  ``-D`` wins over both. Only ``ubproject.toml`` is read by ubCode.
