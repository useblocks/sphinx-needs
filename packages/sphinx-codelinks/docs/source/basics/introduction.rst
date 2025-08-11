Introduction
============

``CodeLinks`` is a Sphinx extension that provides the ``src-trace`` directive to establish traceability between source code and :external+needs:doc:`Sphinx-Needs <index>` items.

At its core, ``CodeLinks`` uses a powerful ``Analyse`` to parse source code comments and extract valuable information. The ``Analyse`` can identify and extract three distinct types of content:

- **One-line need definitions**: Create new Sphinx-Needs directly from a single, :ref:`customized comment line <oneline>` in your source code.
- **Need ID references**: Link code to existing need items without creating new ones, perfect for tracing implementations to requirements.
- **Marked RST text**: Extract blocks of reStructuredText embedded within comments, allowing you to include rich documentation with associated metadata right next to your code.

``src-trace`` directive then consumes ``One-line need definitions`` to generate traceability between source code and your documentation.

The ``Analyse``, along with the ``SourceDiscovery`` module, also provides both a **Python API** for extensibility and a **CLI** for integration into CI/CD pipelines.
