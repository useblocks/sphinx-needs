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

.. _api_content_markup:

Content written in another markup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An extension that creates needs whose text was written somewhere else -- a comment in a
source file, an imported file -- in a markup that is not the page's passes
``MarkupContent(text, markup=..., source=...)`` as the ``content`` of
:func:`~sphinx_needs.api.need.add_need`. ``markup`` is the source suffix of that markup
(``".rst"``, ``".md"``, or any suffix ``source_suffix`` maps to a reStructuredText or MyST
parser): the content is parsed by that parser, whatever the page's parser, and the need
records the suffix as its ``doctype``. With ``source=(path, first_line)``, the warnings
raised while parsing the content, and those for references in it that do not resolve,
name ``path`` and the line the content came from rather than the page -- through
``sphinx.util.docutils.switch_source_input``, the same mechanism ``sphinx.ext.autodoc`` uses
to report a docstring's lines at the Python file. ``add_need`` takes no other argument for
this, so no field or link name is reserved.
:func:`~sphinx_needs.api.need.ingest_need_record` creates a need from a needs.json-style
record, and is the path :ref:`needimport` itself takes for each need it imports.

.. autoclass:: sphinx_needs.api.MarkupContent

The content is parsed into the page it is rendered on, so a label defined in it belongs to
that page and other pages reference it there. The warnings myst-parser logs itself, such as
an unknown directive or role in Markdown content, name the page with the content's line;
with myst-parser 4 their file is the content's path with ``.rst`` appended. In a
reStructuredText page, MyST content's ``[text](#anchor)`` links are not resolved and a
missing anchor is not reported; use the ``{ref}`` and ``{need}`` roles, which work in both.

What such content should not contain
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This version parses the content as the page would parse it, and refuses none of the
following; a later version will, as ubCode's reader already does:

- directives that read files (``include``, ``literalinclude``, ``csv-table`` with
  ``:file:``, ``raw`` with ``:file:``), and images and other references to files by a
  relative path: Sphinx's ``include``, ``literalinclude`` and images, and everything in
  MyST content, resolve against the page, while ``csv-table :file:`` and ``raw :file:``
  in reStructuredText content resolve against the content's file;
- ``raw``, and raw HTML in Markdown;
- need or ``needimport`` directives: the needs they create are recorded against the page;
- anything relying on the page's substitutions or ``rst_prolog``: it works, but the same
  text means something else on another page.

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
