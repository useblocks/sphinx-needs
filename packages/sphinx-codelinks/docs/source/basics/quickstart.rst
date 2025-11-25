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
   src_trace_config_from_toml = "src_trace.toml"

.. literalinclude:: ./../../src_trace.toml
   :caption: src_trace.toml
   :language: toml

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
