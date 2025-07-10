.. _roadmap:

Roadmap
=======

Other Comment styles
--------------------

Currently, only ``C/C++`` comment style is supported.
The other comment styles for different programming languages are planed, such as:

- Python
- Rust
- YAML
- SyML

Nested .gitignore
-----------------

``CodeLinks`` respects ``.gitignore`` file, but if the .gitignore files are nested, it's not supported.
Respecting nested ``.gitignore`` in the context of the git repositories is planned.

Flexible way to define Sphinx-Needs need items in source code
-------------------------------------------------------------

The only way to define ``Sphinx-Needs`` need items is through ``one-line comment style``.
Raw RST text and multi-lines comments style are planned to support

Export needs.json
-----------------

To facilitate CI workflow and enhance the portability of ``need items`` defined in source code,
we plan to have the feature to export the needs defined in source code to a JSON file.
