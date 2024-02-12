.. _open_needs_service:



Open-Needs services
===================

The `Open-Needs <https://open-needs.org/>`__ service retrieves Need objects from a local or remote
`Open-Needs server <https://open-needs.org/open-needs-server/>`__ and
creates Sphinx-Needs objects during build time.
The service creates need objects for each element found by querying the Open-Needs REST-API based server.

The service name for Open-Needs service must be ``open-needs``.

Example of an imported open-needs:

.. code-block:: rst

   .. needservice:: open-needs
      :prefix: ONS_
      :params: skip=0;limit=10

Options
-------
The following options can be specified under ``.. needservice:: open-needs`` directive.

prefix
######
A string, which is taken as prefix for the need-id. E.g. ``ONS_IMPORT_`` –> ``ONS_IMPORT_003``.

**Default value**: ``ONS_NEEDS_``

params
######
A query string used to filter and organize the data retrieved from the ``open-needs`` service.
For example: The query string ``limit=10`` can be used as:

.. code-block:: rst

   .. needservice:: open-needs
      :params: limit=10

Multiple values in the query string must be separated by a comma(``,``) or a semicolon(``;``).
Example: ``:params: skip=1;limit=10``

**Default value**: ``skip=0,limit=100``

url
###
URL of the server. The final ``RESTful API`` address endpoint(`url_postfix <#url_postfix>`_) gets added automatically.
E.g.: ``http://127.0.0.1:9595`` or ``https://open-needs.org/``

**Default value**: http://127.0.0.1:9595

url_postfix
###########
The final address of the endpoint. E.g.: ``/api/needs/``

**Default value**: ``/api/needs/``

max_content_lines
#################
Maximum amount of lines from open-needs objects description/content to be used in need content.

Config
------
Most configuration needs to be done via the :ref:`needs_services` configuration in your **conf.py** file.

:ref:`needs_services` must contain a key with the service name, E.g. ``open-needs``

The following key-value configuration parameters can be set for the Open-Need services:

url
###
Open-Needs service instance url. Default: ``https://api.open-need.com/``

username
########
Username credentials used for login.

password
########
Password credentials used for login.

id_prefix
#########
Prefix string for the final need id.

mapping
#######
The field names of a service object do not often map to option names of Sphinx-Needs.
So **mapping** defines where a Sphinx-Needs option shall get its value inside the service data.

**mapping** must be a dictionary, where the key is the needs object name and the value is either a Jinja string such as ``is_{{status}}``
or a list/tuple, which defines the location of the value in the retrieved service data object.

.. _open_need_data:

.. dropdown:: Example of an Open-Needs service data object

   .. code-block::

      [
         {
           "key": "NEP_001",
           "type": "Requirement",
           "title": "Build rocket",
           "description": "We finally need to build our Neptune3000 rocket.",
           "format": "txt",
           "project_id": 1,
           "options": {
             "status": "done",
             "priority": "high",
             "costs": 3500000,
             "approved": 1,
             "lastname": "Duodu"
             "firstname": "Randy"
           },
           "references": {
             "links": [
               "NEP_001",
               "NEP_002"
             ]
           }
         },
      ]


**Example using a Jinja string as value for the Open-Needs service**

Goal: The need option ``author`` shall be set to the last and first names.

The last and first names information are stored in the retrieved :ref:`Open-Needs <open_need_data>` data
under ``lastname`` and ``firstname``.

The **mapping** entry for ``author`` would like this:


.. code-block:: python

    'mapping': {
        'author': "{{options.lastname}} {{options.firstname}}",
    }

.. note::

   When you use a Jinja string as value, you must ensure the field names of a service object does not contain spaces because that will raise a
   `Jinja Template Syntax Error <https://jinja.palletsprojects.com/en/3.1.x/api/#jinja2.TemplateSyntaxError>`_.
   For example: Instead of the field name being ``last name`` use ``last_name``.

**Example using a list/tuple as value for the Open-Needs service**

Goal: The need option ``author`` shall be set to the last name.

The **mapping** entry for ``author`` would like this:

.. code-block:: python

    'mapping': {
        'author': ["options", "lastname"],
    }

content
#######
Content takes a string, which gets interpreted as rst-code for the need-content area.
Jinja support is also available, so that service data is available and can be accessed like ``{{data.description}}``.

mappings_replaces
#################
There are use cases, where a value inside service data is not valid for a Sphinx-Needs options.
For instance: In the data retrieved from the Open-Needs server, ``type`` is named ``Requirement``, but Sphinx-Needs supports only ``req`` as value for type option.

**mappings_replaces** can replace strings defined by a regular expression with a new value. This replacement is performed for all mappings.

extra_data
##########
There may be information stored inside the :ref:`Open-Needs <open_need_data>` service data fields
which cannot be mapped to the Sphinx-Needs options, but is available inside the Need object.

This can be done by using ``extra_data``, which adds this kind of information to the end of the content of a need object.

The logic and syntax is the same as used by `mapping <#mapping>`_.


.. note::

   Some options can be overwritten by setting them directly in the need service directive:

   .. code-block:: rst

      .. needservice:: open-needs
         :url: http://127.0.0.1:9595
         :prefix: ONS_IMPORT
         :params: skip=0;limit=10

**Example configuration for conf.py**:

.. literalinclude:: /conf.py
   :language: python
   :lines: 329-346



Examples
--------
**Code**

.. code-block:: rst

   .. needservice:: open-needs
      :prefix: ONS_
      :params: skip=0;limit=10

   .. needtable::
      :filter: "ONS" in id

**Result**

.. hint::

   The below examples are just images, as no Open-Needs Server instance was available during documentation build.

.. image:: /_images/ons_example.png
   :align: center
   :width: 60%

.. image:: /_images/ons_table.png
   :align: center
   :width: 60%
