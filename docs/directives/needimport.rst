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

.. warning::

    * Imported needs may use different need types as the current project.
    * The sphinx project owner is responsible for a correct configuration for internal and external needs.
    * There is no automatic type transformation during an import.

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
