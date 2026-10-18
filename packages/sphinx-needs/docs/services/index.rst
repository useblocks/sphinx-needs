.. _services:

Services
========
.. versionadded:: 0.6.0

Services are used by **Sphinx-Needs** to get information from external services and create need objects based on this
information.
For example this could be issues from GitHub, requirements from Doors, tickets from Jira, rows from Excel, or whatever.

Up to now **Sphinx-Needs** provides the following services:

.. toctree::
   :maxdepth: 1

   github

Use the directive :ref:`needservice` to execute a service and get need objects back.

.. code-block:: rst

   .. needservice:: <service_name>
      :<service_option>: ...
      :own_options: ...

Each service may have options of its own, which tell the service what to request,
such as the GitHub services' ``query``.
They are options of the ``needservice`` directive naming that service, not need fields:
they are not set on the needs the service creates, and a ``needservice`` of another service does not accept them.
Please take a look into the related service documentation for information about them.

You can always set all fields, which are also available for all need objects.
So the ones defined by :ref:`needs_fields` and :ref:`needs_links`.
These options will then be set for all needs created by the requested service.
An option of the service wins over a field of the same name: on its ``needservice``, the option is the service's.

Most services also support adding additional content to the created needs.
Simply use the content part of ``.. needservice::`` and the content gets added and rendered for all
needs created by the service.

.. code-block:: rst

   .. needservice:: <service_name>
      :tags: awesome, nice, cool
      :status: open
      :author: me

      My **custom** content.

Configuration
-------------

needs_services
++++++++++++++
Stores all service related configuration options in a dictionary.

.. code-block:: python

    needs_services = {
        'service_name': {
            "option_1": "value",
            # ...
        }
    }

A service is available only once ``needs_services`` names it, the built-in GitHub services included
(an empty entry, such as ``{"github-issues": {}}``, will do): their options have defaults that work for basic tasks.
However, if a service needs specific options or custom tasks are needed
(e.g. communicate with a specific company server), special configuration may be needed and the service may throw an
error or warning, if something is missing.

For available configuration options please take a look into the related service documentation.

needs_service_all_data
++++++++++++++++++++++
If a service returns data for an option, which was not registered by the service itself or the user via
:ref:`needs_fields`, this information is added to the content part.

Set ``needs_service_all_data`` to ``False`` to hide this kind of information.

Multiple service instances
--------------------------
Sometimes it makes sense to have multiple service instances, which provide the same functionality but need a different
configuration, e.g. issues should be reported from GitHub cloud repositories and repositories from the company
internal GitHub Enterprise instance.

All you need to do is to set the Python service class, which must be mentioned under the key ``class`` in
``needs_services`` of your **conf.py** file.

.. code-block:: python

    from sphinx_needs.services.xy import NeededService

    needs_services = {
        'my-company-service': {
            'class': NeededService,
            'class_init': {
                # ...
            },
            # ...
        }
    }

Some services may need special configuration options to be initialised, these configs must be provided inside
``class_init``.

For a complex example of the GitHub service please take a look into its chapter :ref:`service_github_custom`.


Own services
------------
A custom service can be created by providing your own service-class, which must inherit from the ``BaseService`` class
and provide a function called ``request``.

The class declares two lists:

``options``
   The options of the :ref:`needservice` directive the service reads, beside the options of a need,
   such as a query string or a maximum amount.
   They are given to ``request``, and are not need fields.
``fields``
   The need fields the needs of the service carry, which are registered when the service is,
   as :ref:`needs_fields` registers a field.

The ``request`` function must return a list of dictionary objects, where each dictionary contains values for a need, which shall
be created.

Example of a basic service:

.. code-block:: python

    from sphinx_needs.services.base import BaseService

    class MyService(BaseService):
        # the options of the needservice directive the service reads
        options = ["max_items"]
        # the need fields its needs carry
        fields = ["origin"]

        def __init__(self, app, name, config, **kwargs):
            # Get a config value from service related part
            # of needs_services inside conf.py
            self.my_config = config.get("my_config", "DEFAULT")

            # Custom init config, which is provided only once
            # during class initialisation
            custom_init = kwargs.get("custom_init", False)

            super().__init__()

        def request(self, options):
            # Get the options provided by the user in the directive call
            status = options.get("status", "Unknown")
            max_items = int(options.get("max_items", 2))

            data = [
                {
                    "title": "My Issue 1",
                    "status": status,
                    "origin": self.my_config,
                },
                {
                    "title": "My Issue 2",
                    "type": "spec",
                    "origin": self.my_config,
                },
            ]

            return data[:max_items]

        def debug(self, options):
            # Allows to send back data, which may be helpful for debugging.
            # debug_data needs do be serializable via json.dump.()
            debug_data = {"custom_debug": "data"}
            return debug_data

**Configuration inside conf.py**:

.. code-block:: python

    from somewhere.my_services import MyService

    needs_services = {
        "my-service": {
            "class": MyService,
            "class_init": {
                "custom_init": True,
            },
            "my_config": "Awesome",
        }
    }

**Using inside rst files**:

.. code-block:: rst

    .. needservice:: my-service
       :status: open
       :max_items: 2

    .. needservice:: my-service
       :debug:

This would create 2 need objects with titles ``My Issue 1`` and ``My Issue 2``,
each with its ``origin`` field set to ``Awesome``.

To get the debug output of the service, use the ``debug`` flag:

.. code-block:: rst

    .. needservice:: my-service
       :debug:

Sphinx-Needs uses the extension `Sphinx-Data-Viewer <https://sphinx-data-viewer.readthedocs.io>`_ to represent the
debug data in a nice and structured way.

.. deprecated:: 9.1.0

   A service class that declares ``options`` but no ``fields`` of its own
   -- one written before ``fields`` existed, or one adding to the ``options`` of a class it derives from,
   such as ``GithubService`` --
   is read as it was written: its options (but ``type``) are registered as need fields too,
   and its registration gives one ``needs.deprecated`` warning.
   This is removed in sphinx-needs 10.0: declare ``fields`` (an empty list will do),
   and keep in ``options`` only what the service reads.
