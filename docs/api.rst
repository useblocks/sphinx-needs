.. _api:

Python API
==========

**Sphinx-Needs** provides an open API for other Sphinx-extensions to provide specific need-types, create needs or
make usage of the filter possibilities.

The API allows the injection of extra configuration, but
does not support manipulation of it (e.g remove need types),
to keep the final configuration transparent for the Sphinx project authors.

.. _api_configuration:

Configuration
-------------

.. automodule:: sphinx_needs.api.configuration
   :members:

.. autoclass:: sphinx_needs.functions.functions.DynamicFunction
   :members: __name__,__call__

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
   :members: NeedsInfoType, NeedsMutable, NeedsPartType

Views
-----

These views are returned by certain functions, and injected into filters,
but should not be instantiated directly.

.. automodule:: sphinx_needs.views
   :members:
   :undoc-members:
   :special-members: __iter__, __getitem__, __len__
