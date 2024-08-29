.. _api:

Python API
==========

**Sphinx-Needs** provides an open API for other Sphinx-extensions to provide specific need-types, create needs or
make usage of the filter possibilities.

The API allows the injection of extra configuration into it. The API does not support the overall manipulation (e.g remove need types)
to keep the final configuration transparent for the Sphinx project authors.

For some implementation ideas, take a look into the Sphinx extension
`Sphinx-Test-Reports <https://sphinx-test-reports.readthedocs.io/en/latest/>`_ and its
`source code <https://github.com/useblocks/sphinx-test-reports/blob/master/sphinxcontrib/test_reports/test_reports.py>`_.

.. _api_configuration:

Configuration
-------------
.. automodule:: sphinx_needs.api.configuration
   :members:

Need
----
.. automodule:: sphinx_needs.api.need
   :members:


Exceptions
----------
.. automodule:: sphinx_needs.api.exceptions
   :members:

Data
----

.. automodule:: sphinx_needs.data
   :members: NeedsInfoType, NeedsView
