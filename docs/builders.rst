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

.. _filter_export:

Exporting filters
+++++++++++++++++

.. versionadded:: 0.3.11

The results and filter configuration of a filter based directive, like :ref:`needlist`, :ref:`needtable`
or :ref:`needflow` gets exported, if the option :ref:`export_id` is used in the related directive.

This allows to export specified filter results only.


|ex|:

.. code-block:: rst

   .. needtable::
      :status: open
      :filter: "test" in tags
      :export_id: filter_01


Format
++++++

.. code-block:: python

    {
    "created": "2017-07-03T11:54:42.433876",
    "current_version": "1.5",
    "project": "needs test docs",
    "versions": {
        "1.0": {
            "created": "2017-07-03T11:54:42.433868",
            "filters": {
               "FILTER_1": {
                 "amount": 1,
                 "export_id": "FILTER_1",
                 "filter": "",
                 "result": [
                     "IMPL_01",
                 ],
                 "status": [],
                 "tags": "",
                 "types": []
            },
            "needs": {
                "IMPL_01": {
                    "description": "Incoming links of this spec: :need_incoming:`IMPL_01`.",
                    "id": "IMPL_01",
                    "links": [
                        "OWN_ID_123"
                    ],
                    "sections": [
                        "Examples"
                    ],
                    "status": null,
                    "tags": [],
                    "title": "Implementation for specification",
                    "type": "impl",
                    "type_name": "Implementation"
                }
            }
        },
        "1.5": {
            "created": "2017-07-03T16:10:31.633425",
            "filters": {
               "FILTER_1": {
                 "amount": 1,
                 "export_id": "FILTER_1",
                 "filter": "",
                 "result": [
                     "IMPL_01",
                 ],
                 "status": [],
                 "tags": "",
                 "types": []
            },
            "needs": {
                "IMPL_01": {
                    "description": "Incoming links",
                    "id": "IMPL_01",
                    "links": [
                        "OWN_ID_123"
                    ],
                    "sections": [
                        "Examples"
                    ],
                    "status": "closed",
                    "tags": ["links","update"],
                    "title": "Implementation for specification",
                    "type": "impl",
                    "type_name": "Implementation"
                }
            }
        }
    }

