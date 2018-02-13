.. _needimport:

needimport
==========
.. versionadded:: 0.1.33

Allows the import of needs from a json file.

The builder :ref:`needs_builder` should be used to generate a valid file.

The directive **.. needimport::** can be used in all rst-documents. Simply write::

   .. needimport:: needs.json
      :id_prefix: imp_
      :version: 1.0
      :tags: imported;external
      :hide:
      :filter: "test" in tags

The directive needs an absolute or relative path as argument.
If the path is relative, an absolute path gets calculated with the folder of the **conf.py** as basedir.

**:id_prefix:** can be used to add a prefix in front of all imported need ids.
This may be useful to avoid duplicated ids.

.. note:: when using **:id_prefix:** also all ids used for links and inside descriptions get replaced,
          if the id belongs to an imported need.

**:version:** allows to specify a specific version for the import. This version must exist inside the imported file.
If no version is given, the **current_version** attribute from the json file is used.
In most cases this should be the latest available version.

**:tags:** are attached to the already existing ones of imported needs. This may be useful to mark easily imported
needs and to create specialised filters for them.

**:filter** imports needs only, which pass the filter criteria. Please read the :ref:`filter` documentation of the
**needfilter** directive for more.

**:hide:** can be used to set the **:hide:** tag for all imported needs. So they do not show up but are available
in :ref:`needfilter`.

.. warning:: Imported needs may use different need types as the current project.
             The sphinx project owner is responsible for a correct configuration for internal and external needs.
             There is no automatic typ transformation during an import.


