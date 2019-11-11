API
===

``Sphinx-Needs`` provides an open API for other sphinx-extensions to provide specific need-types, create needs or
make usage of the filter possibilities.

The API is designed to allow the injection of extra configuration. The overall manipulation (e.g remove need types) is
not supported to keep the final configuration transparent for the sphinx-project-authors.

Configuration
-------------

.. automodule:: sphinxcontrib.needs.api.configuration
   :members:
