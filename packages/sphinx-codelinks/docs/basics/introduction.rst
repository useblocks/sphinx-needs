Introduction
============

``CodeLinks`` is a versatile utility that enables fast source code tracing and connects it to
the :external+needs:doc:`Sphinx-Needs <index>` ecosystem.

It has multiple components:

- source code analyzer for multiple programming languages and comment styles
- generator for various output formats that contain the extracted markers or needs
- Sphinx extension that integrates ``CodeLinks`` with Sphinx-Needs
- CLI application to drive the analysis and generation process

The configuration for ``CodeLinks`` is done via a TOML file, which can be used
for both the :ref:`Sphinx extension <configuration>` and the :ref:`CLI application <cli>`.

The configuration determines how markers and languages are ingested and how the Sphinx extension should behave.

At its core, ``CodeLinks`` parses the source code structure and extracts source markers.
Source markers can be special comments or language-specific constructs like docstrings for Python.

``CodeLinks`` supports 3 distinct marker types:

- :ref:`One-line need definitions <oneline>`: Create new Sphinx-Needs directly from a single customized comment line
  in your source code.
- **Need ID references**: Link code to existing need items without creating new ones, perfect for tracing implementations to requirements.
- **Marked RST text**: Extract blocks of reStructuredText embedded within comments, allowing you to include rich documentation with associated metadata right next to your code.

When used in a Sphinx context, a new :ref:`directive` creates items at the location where it is placed (for a subset
of the analyzed files/folders).

For use cases where ``CodeLinks`` should not integrate with Sphinx, but rather generate output files, the
:ref:`cli` can be used. Currently it can write out ``needextend`` directives for the need ID reference comment style.
Other output files are planned such as full need items as RST or needs.json.

The availability of most commands as :ref:`cli` also helps integrate ``CodeLinks`` into build systems and CI/CD pipelines.
Focus is put on performance, portability and caching of processing steps.
