.. _builders:

Builders
========

.. _needs_builder:

needs
-----
.. versionadded:: 0.1.30

The **needs** builder exports all found needs and selected filter results to a single json file.

The build creates a folder called **needs** and a file called **needs.json** inside the given build-folder.

Usage
+++++

.. code-block:: bash

    sphinx-build -b needs source_dir build_dir


.. hint::

   As an alternative, you can set the :ref:`needs_build_json` parameter in **conf.py** to create a ``needs.json`` file directly during the build
   of another output format like ``html``.

History data
++++++++++++

The builder stores the needs under a version taken from your **conf.py**.

If a **needs.json** is imported (see :ref:`needs_file`) and you raise the documentation version, the new version is stored beside the old
version(s) inside the **needs.json**.

.. hint::
   If you generate and store/archive (e.g. in git) the **needs.json** file
   every time you raise your documentation version, you will get a nice history data.

.. _needs_builder_format:

Format
++++++

As well as the ``needs`` data, each version in the **needs.json** file carries a ``creator`` (the program and version that wrote it) and the ``needs_schema``.
This is a JSON schema for the data structure of a single need,
and also includes a ``field_type`` for each field, to denote the source of the field,
that can be one of: ``core``, ``links``, ``backlinks``, ``extra``.
A field, core or extra, is written as the project declares it for all need types together (a need type's own declaration is not written),
a :ref:`needs_fields` entry narrowing a core field included:
its type (with ``null`` where it is nullable), its item type and its default, but not its other constraints, such as an ``enum``.
A link type is written with its default links as a need holding them writes its links --
sorted and deduplicated, each with its condition under :ref:`needs_json_include_link_conditions` (the default) and without it otherwise:
the literal ``default`` of its :ref:`needs_links` entry
(a default a dynamic function or a variant computes is written ``[]``, as is a derived link type's,
but for one derived by type alone, whose default is the links of a need type without a rule).

How a needs.json is read is specified once, in the `needs.json exchange contract <https://github.com/useblocks/sphinx-needs/blob/master/packages/ub-needs-exchange/design/exchange-contract.md>`__ of the ``ub-needs-exchange`` library, through which :ref:`needimport` and :ref:`needs_external_needs` read it (ubCode is to vendor the contract's conformance corpus, and to be held to it); :ref:`needs_file` still reads the file with Python's ``json`` module, and moves to the library with the writer.

See also :ref:`needs_json_exclude_fields`, :ref:`needs_json_remove_defaults`, :ref:`needs_reproducible_json`, and :ref:`needs_json_include_link_conditions` for more options on modifying the content of the ``needs.json`` file.

.. note:: ``needs_defaults_removed`` is a flag that is set to ``true`` if the defaults are removed from the needs. If it is missing or set to ``false``, the defaults are not removed.

.. code-block:: python

    {
    "created": "2017-07-03T11:54:42.433876",
    "current_version": "1.5",
    "project": "needs test docs",
    "versions": {
        "1.0": {
            "created": "2017-07-03T11:54:42.433868",
            "needs_schema": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "properties": {
                    "id": {
                        "description": "ID of the data.",
                        "field_type": "core",
                        "type": "string"
                    },
                    "type": {
                        "description": "Type of the need.",
                        "field_type": "core",
                        "type": "string"
                    },
                    "links": {
                        "description": "Link field",
                        "field_type": "links",
                        "items": {
                            "type": "string"
                        },
                        "type": "array",
                        "default": []
                    },
                    "status": {
                        "description": "Status of the need.",
                        "field_type": "core",
                        "type": [
                            "string",
                            "null"
                        ],
                        "default": null
                    },
                    ...
                }
            },
            "needs_defaults_removed": true,
            "needs": {
                "IMPL_01": {
                    "id": "IMPL_01",
                    "type": "impl",
                    "links": ["OWN_ID_123"],
                    ...
                },
                ...
            }
        },
        "1.5": {
            "created": "2017-07-03T16:10:31.633425",
            "needs_schema": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "properties": {
                    "id": {
                        "description": "ID of the data.",
                        "field_type": "core",
                        "type": "string"
                    },
                    "type": {
                        "description": "Type of the need.",
                        "field_type": "core",
                        "type": "string"
                    },
                    "links": {
                        "description": "Link field",
                        "field_type": "links",
                        "items": {
                            "type": "string"
                        },
                        "type": "array",
                        "default": []
                    },
                    "status": {
                        "description": "Status of the need.",
                        "field_type": "core",
                        "type": [
                            "string",
                            "null"
                        ],
                        "default": null
                    },
                    ...
                }
            },
            "needs_defaults_removed": true,
            "needs": {
                "IMPL_01": {
                    "id": "IMPL_01",
                    "type": "impl",
                    "links": ["OWN_ID_123"],
                    "status": "closed",
                    ...
                },
                ...
            }
        }
    }

.. _needs_builder_format_2a1:

needs.json format 2a1 (draft)
+++++++++++++++++++++++++++++

.. versionadded:: 9.3.0

.. attention:: **Experimental**: a file in this format is readable only by the release that wrote it.

With :ref:`needs_json_format_version` set to ``"2a1"``, the builders write the first draft of format version 2.
Each build that writes one says, in one ``needs.beta`` warning, that the format is experimental.
It is specified in the `needs.json 2a1 draft contract <https://github.com/useblocks/sphinx-needs/blob/master/packages/ub-needs-exchange/design/v2a1-draft.md>`__
of the ``ub-needs-exchange`` library. In short:

- the document says what it is with a ``format_version``, and has no ``versions``: one file is one snapshot of a
  project, whose ``project`` names it and its version;
- the needs are a list of records, in the order of their ids, each with the sections ``id``, ``type``, ``fields``
  (the core fields a need's author sets, and every field its need type declares, with its value: a default and
  ``null`` too, since the file carries no schema), ``links`` (a bare id, or ``{"id", "part", "condition"}`` where a
  part or a condition is given; no back links), ``content`` (its text, ``doctype`` and parts) and ``source``;
- ``source`` is the list of places the need's text came through, innermost first: the lines of its directive in the
  file it is written in, each file it was included through, the needs.json it was imported from, the docstring or
  the service it came from, and the page it is placed on, with the sections it is in. Where a hop has no ``origin``,
  it is the writing project's;
- nothing computed is written: no back links, no ``is_*``, ``type_*``, ``constraints_*`` or ``section_name``, and none
  of the location keys of format 1 (``docname``, ``lineno``, ``sections``, ...), which a reader projects from the
  source.

An abridged example (the real record also carries ``layout``, ``style`` and ``constraints``, and every other field
of its need type, ``null`` where it is not set):

.. code-block:: json

    {
      "format_version": "2a1",
      "project": {"name": "up", "version": "1.0"},
      "creator": {"program": "sphinx_needs", "version": "9.3.0"},
      "created": "2026-11-05T21:04:13.381102",
      "needs": [
        {
          "id": "REQ_2",
          "type": "req",
          "fields": {"title": "The second", "status": null, "tags": [], "asil": "QM"},
          "links": {
            "links": [{"id": "REQ_1", "part": "p1"}, {"id": "REQ_3", "condition": "status == \"open\""}],
            "parent_needs": []
          },
          "content": {"text": "Links to a part and, under a condition, to a need.", "doctype": ".rst"},
          "source": [
            {
              "kind": "page",
              "physical": {"root": "srcdir", "path": "index.rst", "start_line": 22, "end_line": 26},
              "semantic": [{"kind": "section", "name": "Up"}, {"kind": "section", "name": "Requirements"}],
              "document": "index",
              "language": ".rst"
            }
          ]
        }
      ]
    }

:ref:`needimport` and :ref:`needs_external_needs` read a 2a1 file as they read a file of format 1, whatever
:ref:`needs_json_format_version` says, and keep each need's source: the hops its record carries come before the
ones this build adds (the needs.json it was read from, the page of the ``needimport``), and a re-export writes them
all, in that order, so a need's source grows with each project it passes through. A hop the file gives no ``origin``
is given the name of the project that wrote the file (its ``project.name``; where the file names none, the file as
the reader names it: its path relative to the source directory -- a ``needimport``'s file and an external source's
``json_path`` alike, whatever the configuration spells -- or its URL as written); an ``origin`` the file states is
kept. What an imported or external need
answers about where it is from -- ``docname``, ``lineno``, ``sections``, ``section_name``, ``signature``,
``is_import``, ``is_external``, ``external_url`` and ``c.source`` in a filter -- is what the same need read from a
format-1 file answers: the hops of the other project are kept, not read. An external need's ``external_url`` is
built from the page its record places it on.

A record of a 2a1 file is not a record of format 1, though, and what is read of the record itself differs: a
``needimport`` ``:filter:`` and an external source's ``target_url`` template see its ``id``, ``type``, every
field and link type, ``content``, ``doctype`` and ``parts``, and, from the page it is placed on, ``docname``,
``sections``, ``section_name`` and ``signature``. They do not see ``lineno``, ``lineno_content``,
``is_import``, ``is_external``, ``external_url``, ``type_name`` or any other key the configuration derives, the
back links, or any other computed key (``is_need``, ``parent_need``, ``constraints_passed``, ...): a filter over
one of them fails, and a template renders it empty.

Older readers do not read it. Sphinx-Needs 9.1.0 and 9.2.0 refuse the file with one warning per reader, which names
the file and says that it is of format version ``"2a1"`` and that the reader reads format version 1 only;
Sphinx-Needs 9.0.0 refuses it with one warning per reader that its ``'versions' is missing or not an object``; ubCode
refuses it in the same way. Sphinx-Needs 8.5.0 aborts the build on it: external needs with
``NeedsExternalException: No version defined``, a ``needimport`` with ``CorruptedNeedsFile: Key 'current_version'
missing or corrupted``.

.. _needumls_builder:

needumls
--------

The **needumls** builder saves each :ref:`needuml` generated plantuml code to a file, and stores all the files into a single folder during the build.
The file is created only if the option ``:save:`` from :ref:`needuml` is configured.

Each file is written to the builder's output folder, under the path its ``:save:`` option gives.
Note that ``make needumls`` and ``sphinx-build -M needumls`` place that output folder in a subfolder named **needumls**
of the build folder you name, e.g. ``_build/needumls``, as they do for every builder;
``sphinx-build -b needumls`` writes straight into the output folder you name.

.. note::

   The builder writes only the diagrams the current build re-rendered.
   A document Sphinx did not have to re-read is not re-rendered, so its ``:save:`` file is left exactly as it was —
   which means that pointing the builder at an output folder whose ``.doctrees`` is already up to date writes nothing at all
   (the log says ``Skipping needuml file ...`` for each one).
   Use a fresh output folder, or pass ``-E`` to re-read everything, to regenerate every file.

Usage
+++++

.. code-block:: bash

    make needumls

or

.. code-block:: bash

    sphinx-build -M needumls source_dir build_dir

.. hint::

    As an alternative, you can set the config option :ref:`needs_build_needumls` to export the needumls files during each build.


.. _needs_id_builder:

needs_id
--------
.. versionadded:: 2.0.0

The **needs_id** builder exports all found needs and selected filter results to a set json files of each need with the name is ``id`` of need.

The build creates a folder called :ref:``needs_build_json_per_id_path`` and all file json of each need inside the given build-folder.

Usage
+++++

.. code-block:: bash

    sphinx-build -b needs_id source_dir build_dir
