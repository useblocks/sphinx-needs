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

.. _needumls_builder:

needumls
--------

The **needumls** builder saves each :ref:`needuml` generated plantuml code to a file, and stores all the files into a single folder during the build.
The file is created only if the option ``:save:`` from :ref:`needuml` is configured.

The build creates a folder called **needumls** inside the given build-folder, e.g. `_build/needumls`.

Usage
+++++

.. code-block:: bash

    make needumls

or

.. code-block:: bash

    sphinx-build -M needumls source_dir build_dir

.. hint::

    As an alternative, you can set the config option :ref:`needs_build_needumls` to export the needumls files during each build.

.. _needs_per_page_builder:

needs_per_page
--------------
.. versionadded:: 1.4.0

The **needs_per_page** builder exports all found needs with same ``docname`` into separate ``json`` file.
If docname has slash like  ``directives/list2need``, the file will be located in folder called :ref:`needs_per_page_build_path`.
e.g. `needs_per_page/directives/list2need.json` .

Usage
+++++


.. code-block:: bash

    sphinx-build -b needs_per_page source_dir build_dir


Format with file name: configuration.json
++++++
.. code-block:: python

    {
    "needs": [
        {
            "xyz_123": {
                "docname": "configuration",
                "doctype": ".rst",
                "lineno": 203,
                "target_id": "xyz_123",
                "external_url": null,
                "content_id": "xyz_123",
                "type": "req",
                "type_name": "Requirement",
                "type_prefix": "R_",
                "type_color": "#BFD8D2",
                "type_style": "node",
                "status": "open",
                "tags": [],
                "constraints": [],
                "constraints_passed": null,
                "constraints_results": {},
                "id": "xyz_123",
                "title": "My requirement with custom options",
                "full_title": "My requirement with custom options",
                "content": "Some content",
                "collapse": null,
                "arch": {},
                "style": null,
                "layout": "",
                "template": null,
                "pre_template": null,
                "post_template": null,
                "hide": false,
                "delete": null,
                "jinja_content": null,
                "parts": {},
                "is_part": false,
                "is_need": true,
                "is_external": false,
                "external_css": "external_link",
                "is_modified": false,
                "modifications": 0,
                "my_extra_option": "A new option",
                "another_option": "filter_me",
                "author": "",
                "comment": "",
                "amount": "",
                "hours": "",
                "image": "",
                "config": "",
                "github": "",
                "value": "",
                "unit": "",
                "query": "",
                "specific": "",
                "max_amount": "",
                "max_content_lines": "",
                "id_prefix": "",
                "user": "",
                "created_at": "",
                "updated_at": "",
                "closed_at": "",
                "service": "",
                "url": "",
                "avatar": "",
                "params": "",
                "prefix": "",
                "url_postfix": "",
                "hidden": "",
                "duration": "",
                "completion": "",
                "has_dead_links": "",
                "has_forbidden_dead_links": "",
                "links": [],
                "links_back": [],
                "parent_needs": [],
                "parent_needs_back": [],
                "blocks": [],
                "blocks_back": [],
                "tests": [],
                "tests_back": [],
                "checks": [],
                "checks_back": [],
                "triggers": [],
                "triggers_back": [],
                "starts_with": [],
                "starts_with_back": [],
                "starts_after": [],
                "starts_after_back": [],
                "ends_with": [],
                "ends_with_back": [],
                "sections": [
                    "needs_extra_options",
                    "Options",
                    "Configuration"
                ],
                "section_name": "needs_extra_options",
                "signature": "",
                "parent_need": "",
                "id_parent": "xyz_123",
                "id_complete": "xyz_123"
            }
        },
        {
            "EXTRA_REQ_001": {
                "docname": "configuration",
                "doctype": ".rst",
                "lineno": 371,
                "target_id": "EXTRA_REQ_001",
                "external_url": null,
                "content_id": "EXTRA_REQ_001",
                "type": "req",
                "type_name": "Requirement",
                "type_prefix": "R_",
                "type_color": "#BFD8D2",
                "type_style": "node",
                "status": null,
                "tags": [],
                "constraints": [],
                "constraints_passed": null,
                "constraints_results": {},
                "id": "EXTRA_REQ_001",
                "title": "My requirement",
                "full_title": "My requirement",
                "content": "",
                "collapse": null,
                "arch": {},
                "style": null,
                "layout": "",
                "template": null,
                "pre_template": null,
                "post_template": null,
                "hide": false,
                "delete": null,
                "jinja_content": null,
                "parts": {},
                "is_part": false,
                "is_need": true,
                "is_external": false,
                "external_css": "external_link",
                "is_modified": false,
                "modifications": 0,
                "my_extra_option": "",
                "another_option": "",
                "author": "",
                "comment": "",
                "amount": "",
                "hours": "",
                "image": "",
                "config": "",
                "github": "",
                "value": "",
                "unit": "",
                "query": "",
                "specific": "",
                "max_amount": "",
                "max_content_lines": "",
                "id_prefix": "",
                "user": "",
                "created_at": "",
                "updated_at": "",
                "closed_at": "",
                "service": "",
                "url": "",
                "avatar": "",
                "params": "",
                "prefix": "",
                "url_postfix": "",
                "hidden": "",
                "duration": "",
                "completion": "",
                "has_dead_links": "",
                "has_forbidden_dead_links": "",
                "links": [],
                "links_back": [],
                "parent_needs": [],
                "parent_needs_back": [],
                "blocks": [],
                "blocks_back": [],
                "tests": [],
                "tests_back": [],
                "checks": [],
                "checks_back": [
                    "EXTRA_TEST_001"
                ],
                "triggers": [],
                "triggers_back": [],
                "starts_with": [],
                "starts_with_back": [],
                "starts_after": [],
                "starts_after_back": [],
                "ends_with": [],
                "ends_with_back": [],
                "sections": [
                    "needs_extra_links",
                    "Options",
                    "Configuration"
                ],
                "section_name": "needs_extra_links",
                "signature": "",
                "parent_need": "",
                "id_parent": "EXTRA_REQ_001",
                "id_complete": "EXTRA_REQ_001"
            }
        }
    ]
}
