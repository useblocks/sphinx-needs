Introduction
============

``CodeLinks`` is a sphinx extension that provides a directive ``src-trace``
to trace the :external+needs:doc:`Sphinx-Needs <index>` need items defined in source files.

Instead of putting RST syntax in the comment, the need definition in source code is simplified to one-liner only,
so that users can just write their `customized one-line comment <oneline>`_ to have the traceability
from the link between source code and documentation.

The provided directive leverages the other two modules ``SourceDiscovery`` and ``VirtualDocs``,
which are also packed in the extension,
to discover source files and create the virtual documents for ``src-trace`` to consume.

Both ``SourceDiscovery`` and ``VirtualDocs`` provide the followings for the developers :

- **Python API** to extend other further use cases.
- **CLI** to have atomic steps in CI/CD pipelines.
