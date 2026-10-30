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

.. autoclass:: sphinx_needs.functions.functions.Reads

Need
----

.. autofunction:: sphinx_needs.api.need.create_need

.. automodule:: sphinx_needs.api.need
   :members:
   :exclude-members: create_need

.. _api_migrating_add_need:

Migrating from ``add_need``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. deprecated:: 9.2.0

   :func:`~sphinx_needs.api.need.add_need` is deprecated, and is removed in 10.0. Each
   call is one Python ``DeprecationWarning`` at the calling line (not a Sphinx warning, so
   a ``-W`` build of a project using an extension that still calls it is not failed by
   it).

:func:`~sphinx_needs.api.need.create_need` takes the need's location as one
:class:`~sphinx_needs.need_item.NeedItemSource`, and its field values and links as two
mappings, kept apart from its own arguments, so no name a project gives a field meets one
of them. In a directive the source is ``NeedItemSource.from_directive(self)``:

.. code-block:: python

   # before
   from sphinx.util.docutils import SphinxDirective

   from sphinx_needs.api import add_need


   class ReqDirective(SphinxDirective):
       def run(self):
           return add_need(
               self.env.app, self.state, self.env.docname, self.lineno,
               "req", self.arguments[0],
               id=self.options.get("id"), status="open", priority="high", links="REQ_0",
           )

.. code-block:: python

   # after
   from sphinx.util.docutils import SphinxDirective

   from sphinx_needs.api import NeedItemSource, create_need


   class ReqDirective(SphinxDirective):
       def run(self):
           need, nodes = create_need(
               self.env.app, self.state, NeedItemSource.from_directive(self),
               "req", self.arguments[0],
               id=self.options.get("id"),
               fields={"status": "open", "priority": "high"},
               links={"links": "REQ_0"},
           )
           return nodes

``from_directive`` works for any docutils ``Directive``, not only a ``SphinxDirective``.
With it, ``need["lineno"]`` is the line the directive is written on, which differs from
``self.lineno`` where ``rst_prolog``, an include or generated input shifts the parser's
count; to keep the old number exactly, use
``NeedItemSource.on_page(self.env.docname, lineno=self.lineno)``, which is the source
``add_need`` built. ``on_page`` gives the need its page and the line the caller passes,
nothing more, so it is the source wherever the caller chooses the line: the directive's own
parser line, as ``add_need`` took it (every need sphinx-codelinks' ``src-trace`` creates sits
at its directive's parser line), or the lines a directive's data names. It works in a docutils
``Directive`` and in a nested parse alike, and is also the ``need_source`` to give
``generate_need``.
``from_directive`` and ``on_page`` are stable, as the class's name is; the hops they build,
and ``NeedItemSource``'s general constructor with its keywords (``hops``, ``lineno``,
``lineno_content``, ``parser_lineno``, ``is_import``), are provisional: they may change
without a deprecation, until needs.json carries them (see the provisional note under "Data",
below). The constructor is for sphinx-needs' own producers and advanced use.

A need placed on a page is created with a parser state, through ``create_need`` as through
``add_need``: an event handler or a role, which has none, cannot create one, and without a
state only an external need can be created (``add_external_need``). Where ``add_need``
refused that with an ``AssertionError``, ``create_need`` raises ``ValueError``.

``add_need``'s other arguments:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - ``add_need``
     - ``create_need``
   * - ``docname``, ``lineno``
     - ``source=NeedItemSource.from_directive(self)``; for a line the caller gives
       (``add_need``'s ``self.lineno``), ``NeedItemSource.on_page(docname, lineno=lineno)``
   * - ``lineno_content``
     - ``from_directive`` sets it (the provisional constructor takes ``lineno_content=``)
   * - ``need_source``
     - ``source``
   * - ``status``, ``tags``, ``constraints``, ``hide``, ``collapse``, ``style``,
       ``layout``, ``template``, ``pre_template``, ``post_template``, and every field
     - ``fields={...}``
   * - every link type
     - ``links={...}``
   * - ``id``, ``content``, ``doctype``, ``jinja_content``, ``full_title``,
       ``allow_type_coercion``
     - the same keyword
   * - ``is_external``, ``external_url``, ``external_css``
     - :func:`~sphinx_needs.api.need.add_external_need`, which is not deprecated (an
       ``external`` hop as ``create_need``'s source, with ``state=None``, is the
       provisional hop type, and takes no ``external_css``)
   * - ``is_import``
     - ``NeedItemSource(..., is_import=True)`` (the provisional constructor), or
       :func:`~sphinx_needs.api.need.ingest_need_record` for a needs.json-style record
   * - ``parts``, ``arch``, ``sections``, ``signature``
     - none: for a need on the page they are computed from its content and the page (a
       record's ``parts`` and ``arch`` through
       :func:`~sphinx_needs.api.need.ingest_need_record`); an external need ``add_need``
       made kept them as given, which neither ``create_need`` nor ``add_external_need``
       takes
   * - the deprecated ``links_string``, ``hide_tags``, ``hide_status``, ``delete``,
       ``constraints_passed``
     - none (``add_need`` drops them, with a warning)
   * - the return value, ``list[nodes.Node]``
     - ``(need, nodes)``: the need as recorded, and the nodes

The five source classes of 9.1.0, ``NeedItemSourceUnknown``, ``NeedItemSourceDirective``,
``NeedItemSourceService``, ``NeedItemSourceExternal`` and ``NeedItemSourceImport``, are
deprecated names of :mod:`sphinx_needs.need_item` until 10.0: each is a function taking its
class's keywords and returning the ``NeedItemSource`` with the legacy keys that class gave,
and reading one is a ``DeprecationWarning``. ``NeedItemSourceUnknown(docname=docname,
lineno=lineno)`` is ``NeedItemSource.on_page(docname, lineno=lineno)``.

.. _api_content_markup:

Content written in another markup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An extension that creates needs whose text was written somewhere else -- a comment in a
source file, an imported file -- in a markup that is not the page's passes
``MarkupContent(text, markup=..., source=...)`` as the ``content`` of
:func:`~sphinx_needs.api.need.create_need` (:func:`~sphinx_needs.api.need.add_need` takes
the same ``content``). ``markup`` is the source suffix of that markup
(``".rst"``, ``".md"``, or any suffix ``source_suffix`` maps to a reStructuredText or MyST
parser): the content is parsed by that parser, whatever the page's parser, and the need
records the suffix as its ``doctype``. With ``source=(path, first_line)``, the warnings
raised while parsing the content, and those for references in it that do not resolve,
name ``path`` and the line the content came from rather than the page -- through
``sphinx.util.docutils.switch_source_input``, the same mechanism ``sphinx.ext.autodoc`` uses
to report a docstring's lines at the Python file. ``create_need`` takes no other argument
for this, and takes the fields and links as mappings, so no field or link name is reserved.
:func:`~sphinx_needs.api.need.ingest_need_record` creates a need from a needs.json-style
record, and is the path :ref:`needimport` itself takes for each need it imports; with
:ref:`needs_import_parse_by_doctype` or its ``:parse_by_doctype:`` option set, needimport
passes a record's ``doctype`` as the content's markup when the project parses it and the
need is not rendered through a template.

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

A field with a :ref:`derive <needs_derive>` rule cannot be set from a callback, a
:ref:`filter function <filter_func>` or a :ref:`dynamic function <dynamic_functions>`: it holds
what its rule computes, and ``need[name] = value`` raises ``KeyError``.


Exceptions
----------

.. automodule:: sphinx_needs.exceptions
   :members:

Data
----

.. automodule:: sphinx_needs.need_item
   :members: NeedItem, NeedLink, NeedPartItem, NeedItemSource, NeedItemSourceProtocol, NeedsContent, NeedPartData, NeedModification, NeedConstraintResults

.. note::

   **Stable**: ``NeedItemSource``'s name, ``NeedItemSource.from_directive`` and ``NeedItemSource.on_page``, and
   reading a source through ``NeedItemSourceProtocol`` (``dict_repr``). **Provisional**: ``NeedItemSource``'s general
   constructor and its keywords (``hops``, ``lineno``, ``lineno_content``, ``parser_lineno``, ``is_import``), the
   stored legacy facts a later release turns into projections, for sphinx-needs' own producers and advanced use; and
   the hops, below.

   **Provisional**: a :class:`~sphinx_needs.need_item.NeedItemSource` has ``hops``, where the need's text came from,
   innermost first; the hop types, ``NeedSourceHop``, ``NeedSourcePhysical`` and ``NeedSourceSemantic``, are
   importable from ``sphinx_needs.api``. The first hop is the innermost place sphinx-needs knows the need came through: for a need
   directive or ``list2need``, the file the need is written in (an included file's own, in an include; the module,
   for an autodoc docstring); for an imported need, the ``needs.json`` it was read from (where the exporting project
   wrote the need is not a hop yet); for a service, the service that made it, then the file of the ``needservice``
   directive; for an external need, its page on the other site, its only hop. A need created
   through ``add_need`` or ``NeedItemSource.on_page`` has its page with no path, and no hops without a document
   (``NeedItemSource.from_directive`` records the directive's file and lines, as a need directive does). The last hop with a ``document`` is
   the page the need is placed on (an external need has none), and carries its sections and the domain objects it
   is written in, outermost first. A hop has a line
   range only where the file, read from disk, holds the need's text there: in reStructuredText every line of the
   directive equals the file's line (whole lines, after a block quote's or a table cell's border, and the bullets of
   the list item the directive opens); in MyST the line opens the directive's fence with its name and title.
   Elsewhere the hop has no line. A recorded line can still be wrong only where the file holds an identical copy of
   the need's text at the line the parser claims: through an included slice (``:start-after:``, ``:start-line:``)
   after an example of the directive, or a MyST need nested at once inside an identical twin (same name, same
   title). Every path is POSIX and relative to its hop's root: the source directory (``"srcdir"``, with ``..`` for a
   file outside it), or, where ``root`` is ``None``, the producer's own root, which this build does not know, the path
   as the producer gives it (a test report's test file, relative to the test run's root). A hop's ``semantic`` is
   ``None`` where it is not determined, or where nothing finer than the file is known. The shape may
   change in a minor release, without a deprecation, until it reaches ``needs.json``; ``NeedItemSourceProtocol`` does
   not include it, so read it with ``getattr(need.source, "hops", ())``. Nothing a filter, a table or ``needs.json``
   shows depends on it.

   A hop's ``language`` is what its text is written in, by the kind of hop: for a ``page`` hop, the page's suffix
   its parser keys on (``.rst``, ``.md``); for a ``file`` hop, the file's own suffix (``.rst``, ``.json``; an
   included ``inc.rst.txt`` records ``.txt``, whichever parser reads it); for a ``code`` hop, the language's name
   (``python``, ``cpp``, ...). The ``code`` hop of a docstring autodoc reads still records its file's suffix
   (``.py``), until sphinx-codelinks' code hops land and move it.

.. autoclass:: sphinx_needs.api.NeedSourceHop
   :members:

.. autoclass:: sphinx_needs.api.NeedSourcePhysical
   :members:

.. autoclass:: sphinx_needs.api.NeedSourceSemantic
   :members:

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
   :members: FieldsSchema, TypeFieldsSchema, FieldShape, LinkShape, FieldSchema,
             FieldFunctionArray, LinksFunctionArray, FieldLiteralValue, LinkSchema,
             LinkDisplayConfig, LinkTargetTypes, LinksLiteralValue, BackLinksSchema,
             AllowedTypes, narrowing_problems

.. automodule:: sphinx_needs.derive
   :members: DeriveRule, DeriveJoin, DeriveInvalid, DeriveCall

.. automodule:: sphinx_needs.schema.config
   :members: FieldStringSchemaType, FieldBooleanSchemaType,
             FieldIntegerSchemaType, FieldNumberSchemaType,
             FieldMultiValueSchemaType,
             LinkSchemaType, LinkItemSchemaType
