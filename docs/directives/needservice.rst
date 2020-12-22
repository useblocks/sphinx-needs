.. _needservice:

needservice
===========
.. versionadded:: 0.6.0

**needservice** allows the import of data from external services like Jira or github::

    .. needservice:: github
       :query: repo:useblocks/sphinx-needs


.. needservice:: github
   :query: repo:useblocks/sphinxcontrib-needs

   test

The service is responsible for fetching all needed data based on the given options and return a list of
need configurations. This is used by **Sphinx-Needs** to create a single need-object for each found need configuration.

These need objects can then be used and referenced as all other need objects, e.g. by filtering them via
:ref:`needtable`.

For details about available services and their specific configuration please take a look into :ref:`services`.

Options
-------
**needservice** supports all options, which are also available for the :ref:`need` directive.
This include also all custom options defined by :ref:`needs_extra_options`.

Beside this, each service can define own options, which may be needed for the service to work correctly.
Please take a look into the related service documentation to find out what is needed.
For services provided by ``Sphinx-Needs`` please take a look into :ref:`services`.

Content
-------
The content of **needservice** is used as content for all created need objects.

A service may deviate from this behavior and define its own usage.
For example by awaiting a json-string with a more complex configuration or by just ignoring the content.

Please take a look into the related service documentation for more information.

