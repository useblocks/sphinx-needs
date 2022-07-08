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
   open_needs

Use the directive :ref:`needservice` to execute a service and get need objects back.

.. code-block:: rst

   .. needservice:: <service_name>
      :<service_option>: ...
      :own_options: ...

Each service may have own options, which are used to configure the service itself.
Please take a look into the related service documentation for information about them.

You can always set all options, which are also available for all need objects.
So the ones defined by :ref:`needs_extra_options` and :ref:`needs_extra_links`.
These options will then be set for all needs created by the requested service.

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

Normally all services have a working default configuration and no extra configuration is needed for basic
tasks. However, if a service needs specific options or custom tasks are needed
(e.g. communicate with a specific company server), special configuration may be needed and the service may throw an
error or warning, if something is missing.

For available configuration options please take a look into the related service documentation.

needs_service_all_data
++++++++++++++++++++++
If a service returns data for an option, which was not registered by the service itself or the user via
:ref:`needs_extra_options`, this information is added to the content part.

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

For a complex example please of the GitHub service please take a look into its chapter :ref:`service_github_custom`.


Own services
------------
A custom service can be created by providing your own service-class, which must inherit from the ``BaseService`` class
and provide a function called ``request``.

The ``request`` function must return a list of dictionary objects, where each dictionary contains values for a need, which shall
be created.

Example of a basic service:

.. code-block:: python

    from sphinx_needs.services.base import BaseService

    class MyService(BaseService):

        def __init__(self, app, name, config, **kwargs):
            # Get a config value from service related part
            # of needs_services inside conf.py
            self.my_config = config.get('my_config', 'DEFAULT')

            # Custom init config, which is provided only once
            # during class initialisation
            custom_init =  kwargs.get('custom_init', False)

            super(GithubService, self).__init__()

        def request(self, options):
            # Get an option provided by the user in the directive call
            status = options.get('status', 'Unknown')

            data = [
                {
                    'title': 'My Issue 1',
                    'status': status,
                    'my_config': self.my_config
                },
                {
                    'title': 'My Issue 2',
                    'type': 'spec'
                }
            ]

            return data

        def debug(self, options):
            # Allows to send back data, which may be helpful for debugging.
            # debug_data needs do be serializable via json.dump.()
            debug_data = {'custom_debug': 'data'}
            return debug_data

**Configuration inside conf.py**:

.. code-block:: python

    from somewhere.my_services import MyService

    needs_services = {
        'my-service': {
            'class': MyService,
            'class_init': {
                'custom_init': True,
            },
            'my_config': 'Awesome',
        }
    }

**Using inside rst files**:

.. code-block:: rst

    .. needservice:: my-service
       :status: open

    .. needservice:: my-service
       :debug:

This would create 2 need objects with titles ``My Issue 1`` and ``My Issue 2``.

To get the debug output of the service, use the ``debug`` flag:

.. code-block:: rst

    .. needservice:: my-service
       :debug:

Sphinx-Needs uses the extension `Sphinx-Data-Viewer <https://sphinx-data-viewer.readthedocs.io>`_ to represent the
debug data in a nice and structured way.
