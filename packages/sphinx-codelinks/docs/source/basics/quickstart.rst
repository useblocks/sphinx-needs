Quick Start
===========

.. video:: local_link.mp4
   :alt: local link
   :align: center

Three steps to quickly run ``CodeLinks`` to generate links to your source code:

- Configure Sphinx
- Add a one-line comment to your source code to define a ``Sphinx-Needs`` item.
- Use the ``src-trace`` directive in your documentation.

Sphinx Config
-------------

.. code-block:: python
   :caption: conf.py

   extensions = [
       'sphinx_needs',
       'sphinx_codelinks'
   ]

**Sphinx-CodeLinks** reads its configuration from an ``ubproject.toml`` file next to :file:`conf.py` by default (see :ref:`src_trace_config_from_toml`), so no further entry in :file:`conf.py` is needed:

.. code-block:: toml
   :caption: ubproject.toml

   # Configuration for source tracing project "src"
   [codelinks.projects.src]
   remote_url_pattern = "https://github.com/useblocks/sphinx-codelinks/blob/{commit}/{path}#L{line}"

   [codelinks.projects.src.source_discover]
   src_dir = "../tests/doc_test/minimum_config" # Relative path from this TOML file to the source directory

One-line comment
----------------

.. literalinclude:: ./../../../tests/doc_test/minimum_config/dummy_src.cpp
   :caption: dummy_src.cpp
   :language: cpp

Directive
---------

.. literalinclude:: ./../../../tests/doc_test/minimum_config/index.rst
   :caption: index.rst
   :language: rst

Example
-------

.. src-trace::
   :project: src

.. note:: **local-url** is not working on the website as it only supports local browse

Section :ref:`Directive <directive>` provides more advanced usage.
