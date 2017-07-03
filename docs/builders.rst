.. _builders:

Builders
========

.. _needs_builder:

needs
-----
.. versionadded:: 0.1.30

The **needs** builder exports all found needs to a single json file.

By default, the used file is called **needs.json** and is stored beside your conf.py file.
This can be changed by setting :ref:`needs_file`.

Usage
+++++

.. code-block:: bash

    sphinx-build -b needs source_dir build_dir

History data
++++++++++++

The builder stores the needs under a version, which is taken from your conf.py.

If a **needs.json** already exists and you raise the documentation version, the new version is stored beside the old
version(s) inside the **needs.json**.

.. hint::
   If you generate and store/archive (e.g. in git) the **needs.json** file
   every time you raise your documentation version, you will get nice history data.

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
            "needs": {
                "IMPL_01": {
                    "description": "Incoming links of this spec: :need_incoming:`IMPL_01`.",
                    "id": "IMPL_01",
                    "links": [
                        "OWN_ID_123"
                    ],
                    "status": null,
                    "tags": [],
                    "title": "Implementation for specification",
                    "type": "impl",
                    "type_name": "Implementation"
                }
            }
        }
        "1.5": {
            "created": "2017-07-03T16:10:31.633425",
            "needs": {
                "IMPL_01": {
                    "description": "Incoming links",
                    "id": "IMPL_01",
                    "links": [
                        "OWN_ID_123"
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

