.. _needimport:

needimport
==========
.. versionadded:: 0.1.33

``needimport`` allows the import of needs from a JSON file.

You can generate a valid file using the builder :ref:`needs_builder`, for example:

.. code-block:: rst

   .. needimport:: needs.json
      :id_prefix: imp_
      :version: 1.0
      :tags: imported;external
      :hide:
      :collapse:
      :filter: "test" in tags
      :template: template.rst
      :pre_template: pre_template.rst
      :post_template: post_template.rst
      :allow_type_coercion: true
      :parse_by_doctype: true

The directive argument can be one of the following formats:

- A remote URL from which to download the ``needs.json``:

  .. code-block:: rst

     .. needimport:: https://my_company.com/docs/remote-needs.json

- A local path relative to the containing document:

  .. code-block:: rst

     .. needimport:: needs.json

- A local path starting with ``/`` is relative to the Sphinx source directory:

  .. code-block:: rst

     .. needimport:: /path/to/needs.json

- For an absolute path on Linux/OSX, make sure to start with two ``//``:

  .. code-block:: rst

     .. needimport:: //absolute/path/to/needs.json

- For an absolute path on Windows, just use the normal drive letters with either forward or backward slashes:

  .. code-block:: rst

     .. needimport:: c:/absolute/path/to/needs.json

     .. needimport:: c:\absolute\path\to\needs.json

.. note::

   If you are rebuilding documentation incrementally (for example, when using ``sphinx-autobuild``), Sphinx  automatically detects changes to the *local* JSON files. However, with remote URLs, you must run a Sphinx build with the ``-E`` flag to rebuild the environment from scratch when the remote file changes.

Options
-------

id_prefix
~~~~~~~~~

You can set ``:id_prefix`` to add a prefix in front of all imported need ids.
This may be useful to avoid duplicated ids.

.. note::

    When using ``:id_prefix:``, we replace all ids used for links and inside descriptions,
    if the id belongs to an imported need.

version
~~~~~~~

You can specify a specific version for the import using the ``:version:`` option.
This version must exist inside the imported file.

If no version is given, we use the ``current_version`` attribute from the JSON file.
In most cases this should be the latest available version.

tags
~~~~

You can attach tags to existing tags of imported needs using the ``:tags:`` option
(as a comma-separated list).
This may be useful to mark easily imported needs and to create specialised filters for them.

ids
~~~

.. versionadded:: 3.1.0

You can use the ``:ids:`` option to import only the needs with the given ids
(as a comma-separated list).
This is useful if you want to import only a subset of the needs from the JSON file.

filter
~~~~~~

You can use the ``:filter:`` option to imports only the needs which pass the filter criteria.
This is a string that is evaluated as a Python expression,
it is less performant than the ``:ids:`` option, but more flexible.

Please read :ref:`filter` for more information.

hide
~~~~

You can use the ``:hide:`` option to set the **hide** tag for all imported needs.
So they are not rendered on the page.

collapse
~~~~~~~~

The ``:collapse:`` will hide the meta-data information by default, if set to ``True``.
See also :ref:`need_collapse` description of :ref:`need`.

.. note::

   Imported needs support :ref:`conditional links <need_conditional_links>`.
   Link strings in the JSON file can contain conditions,
   e.g. ``"links": ["REQ_001[status==\"open\"]"]``,
   and these conditions will be evaluated against the target needs during the build.

.. warning::

    * Imported needs may use different need types as the current project.
    * The sphinx project owner is responsible for a correct configuration for internal and external needs.
    * There is no automatic type transformation during an import.

allow_type_coercion
~~~~~~~~~~~~~~~~~~~

.. versionadded:: 6.1.1

Allows to enable or disable type coercion of fields for each need, and parsing of dynamic functions.
For example if the ``tags`` need field is provided as a string like ``"tag1,tag2,[[func()]]"``, it will be parsed only if this option is set to ``True``,
otherwise will fail.

This option defaults to ``True``.

.. _needimport_parse_by_doctype:

parse_by_doctype
~~~~~~~~~~~~~~~~

.. versionadded:: 9.0.0

Parses each imported need's content in the markup its ``doctype`` names, rather than in
the markup of the page the ``needimport`` is written in. A ``needs.json`` written by
Sphinx-Needs records, for every need, the suffix of the page it was written in, so
Markdown exported from a MyST page renders as Markdown in a reStructuredText page, and
reStructuredText exported from a reStructuredText page renders as such in a MyST page.
The suffix must be one this project's ``source_suffix`` maps to a reStructuredText or a
MyST parser (as for :ref:`content written in another markup <api_content_markup>`); a
need with no ``doctype``, or an empty one, is parsed in the page's markup. Either way, the
need keeps the ``doctype`` of its record, and the warnings raised while parsing its content
name the directive's line plus the line of the content they are on.

``:parse_by_doctype:`` alone (or ``true``) turns this on for one import, and
``:parse_by_doctype: false`` turns it off; without the option,
:ref:`needs_import_parse_by_doctype` decides.

A need rendered through a template -- its record's ``template``, or the ``:template:``
option -- is parsed in the page's markup, template and content together: the template is a
file of the importing project, written in its pages' markup. ``pre_template`` and
``post_template`` are always parsed in the page's markup. Content with ``jinja_content``
is rendered by Jinja first, and then parsed in its ``doctype``.

If this project cannot parse a ``doctype`` -- ``.md`` without myst-parser, or a suffix
that is not in ``source_suffix`` -- the content of those needs is parsed in the page's
markup and they are imported as before, and one ``needs.import_doctype`` warning per
directive names that ``doctype`` (none if none of those needs has content). Register the
suffix, set ``:parse_by_doctype: false``, or add ``"needs.import_doctype"`` to
``suppress_warnings``.

The imported content is not restricted: what :ref:`api_content_markup` says content from
another markup should not contain holds here too.

Customization
-------------

The following options can be set, which overwrite the related options in the imported need itself.
So you can decide what kind of layout or style to use during import.

* layout
* style
* template
* pre_template
* post_template

.. _needimport-keys:

Global keys
-----------
.. versionadded:: 4.2.0

The :ref:`needs_import_keys` configuration can be used to set global keys for use as the directive arguments.

For example:

.. code-block:: python

    needs_import_keys = {"my_key": "path/to/needs.json"}

Allows for the use of:

.. code-block:: restructuredtext

    .. needimport:: my_key
