.. _api:

API
===

``Sphinx-Needs`` provides an open API for other sphinx-extensions to provide specific need-types, create needs or
make usage of the filter possibilities.

The API is designed to allow the injection of extra configuration. The overall manipulation (e.g remove need types) is
not supported to keep the final configuration transparent for the Sphinx project authors.

For some implementation ideas, take a look into the Sphinx extension
`Sphinx-Test-Reports <https://sphinx-test-reports.readthedocs.io/en/latest/>`_ and its
`source code <https://github.com/useblocks/sphinx-test-reports/blob/master/sphinxcontrib/test_reports/test_reports.py#L51>`_.

.. _api_configuration:

Configuration
-------------
.. automodule:: sphinxcontrib.needs.api.configuration
   :members:

Need
----
.. automodule:: sphinxcontrib.needs.api.need
   :members:


Exceptions
----------
.. automodule:: sphinxcontrib.needs.api.exceptions
   :members:
