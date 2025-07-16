.. _changelog:

Changelog
=========

.. _release:0.1.2:

0.1.2
-----

:Released: 16.07.2025

Fixes
.....

- 🐛 Applying default configuration value when not given

  When a user does not specify certain configuration options, the extension will automatically use predefined default
  values, allowing users to get started quickly without needing to customize every option.
  Users can override these defaults by explicitly providing their own configuration values.

- 🐛 Fix local links for multi project configurations

  Local links between docs and one-line need definitions work correctly, when :ref:`src_dir <source_dir>` in multiple
  project configurations point at different locations.

.. _release:0.1.1:

0.1.1
-----

:Released: 11.07.2025

Initial release of ``Sphinx-CodeLinks``

This version features:

- ✨ Sphinx Directive ``src-trace``
- ✨ Virtual Docs and Source Discovery CLI
- ✨ One-line comment to define a ``Sphinx-Needs`` need item
