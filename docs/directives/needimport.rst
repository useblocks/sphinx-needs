.. _needimport:

needimport
==========
.. versionadded:: 0.1.33

``needimport`` allows the import of needs from a JSON file.

You can generate a valid file using the builder :ref:`needs_builder`.

|ex|

.. code-block:: rst

   .. needimport:: needs.json
      :id_prefix: imp_
      :version: 1.0
      :tags: imported;external
      :hide:
      :collapse: True
      :filter: "test" in tags
      :template: template.rst
      :pre_template: pre_template.rst
      :post_template: post_template.rst

The directive needs an absolute or relative path as argument.
If the path is relative, we derive an absolute path based on the location of the document being compiled.

The directive also supports URL as argument to download ``needs.json`` from remote.

|ex|

.. code-block:: rst

   .. needimport:: https://my_company.com/docs/remote-needs.json

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

You can attach tags to existing tags of imported needs using the ``:tags:`` option.
This may be useful to mark easily imported needs and to create specialised filters for them.

filter
~~~~~~

You can use the ``:filter:`` option to imports only the needs which pass the filter criteria.

Please read :ref:`filter` for more information.

hide
~~~~

You can use the ``:hide:`` option to set the **hide** tag for all imported needs.
So they do not show up but are available in :ref:`needfilter`.

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
