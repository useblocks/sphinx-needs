.. _api:

Python API
==========

**Sphinx-Needs** provides an open API for other Sphinx-extensions to provide specific need-types, create needs or
make usage of the filter possibilities.

The API allows the injection of extra configuration, but
does not support manipulation of it (e.g remove need types),
to keep the final configuration transparent for the Sphinx project authors.

.. _`api_configuration`:

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

Events
------

**Sphinx-Needs** registers two Sphinx events, which an extension connects to with
``app.connect(event_name, callback)``. Both are emitted once per build, in the main
process (also in a parallel build), when the needs are first requested after all
documents are read. Each callback is called as ``callback(app, needs)``, where ``needs``
is the mutable mapping of need ids to needs, :py:obj:`~sphinx_needs.data.NeedsMutable`.

``needs-before-post-processing``
   Emitted before the ``needextend`` directives are applied and before dynamic
   functions, links and constraints are resolved. This is the hook for an extension that
   writes into the needs: a ``needextend`` in a document is applied afterwards, and can
   override what the extension wrote.

``needs-before-sealing``
   Emitted after those steps, and before the needs become read-only. A callback sees
   the needs as the ``needextend`` directives left them, with dynamic functions, links
   and constraints resolved.

.. code-block:: python

   def default_status(app, needs):
       for need in needs.values():
           if need["type"] == "req" and not need["status"]:
               need["status"] = "draft"

   def setup(app):
       app.connect("needs-before-post-processing", default_status)


Exceptions
----------

.. automodule:: sphinx_needs.exceptions
   :members:

Data
----

.. automodule:: sphinx_needs.need_item
   :members: NeedItem, NeedLink, NeedPartItem, NeedItemSourceProtocol, NeedsContent, NeedPartData, NeedModification, NeedConstraintResults

.. automodule:: sphinx_needs.data
   :members: NeedsInfoType, NeedsInfoComputedType, NeedsSourceInfoType, NeedsMutable, NeedsPartType

Views
-----

These views are returned by certain functions, and injected into filters,
but should not be instantiated directly.

.. automodule:: sphinx_needs.views
   :members:
   :undoc-members:
   :special-members: __iter__, __getitem__, __len__

Schema
------

.. automodule:: sphinx_needs.needs_schema
   :members: FieldsSchema, FieldSchema, FieldFunctionArray, LinksFunctionArray,
             FieldLiteralValue, LinkSchema, LinkDisplayConfig, LinksLiteralValue, AllowedTypes

.. automodule:: sphinx_needs.schema.config
   :members: FieldStringSchemaType, FieldBooleanSchemaType,
             FieldIntegerSchemaType, FieldNumberSchemaType,
             FieldMultiValueSchemaType,
             LinkSchemaType, LinkItemSchemaType
