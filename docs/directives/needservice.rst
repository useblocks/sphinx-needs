.. _needservice:

needservice
===========
.. versionadded:: 0.6.0

**needservice** allows the import of data from external services like GitHub::

    .. needservice:: <service>
       :option: ...

       Extra content for each new need

In most cases the service fetches requested data from an external server and creates a need object for each
found data-element in the returned data.

These need objects can then be used and referenced as all other need objects, e.g. by filtering them via
:ref:`needtable`.

.. hint::

   For details about available services and their specific configuration please take a look into
   :ref:`services`.

Options
-------
**needservice** supports all options, which are also available for the :ref:`need` directive.
This include also all custom options defined by :ref:`needs_extra_options`.

Beside this, each service can define own options, which may be needed for the service to work correctly.
Please take a look into the related service documentation to find out what is needed.
For services provided by ``Sphinx-Needs`` please take a look into :ref:`services`.

.. code-block:: rst

    .. needservice:: <service>
       :option: ...
       :status: open
       :tags: awesome, nice
       :author: me

       Extra content for each new need

Content
-------
The content of **needservice** is used as content for all created need objects.

A service may deviate from this behavior and define its own usage.
For example by awaiting a json-string with a more complex configuration or by just ignoring the content.

Please take a look into the related service documentation for more information.

Example
-------
This example is using the ``github-issues`` service.
For details please take a look into its specific documentation under :ref:`github_service`.

The service queries ``GitHub`` for issues in the ``Sphinx-Needs`` repository, which have *node* and *latexpdf* in
their content.

.. code-block:: rst

    .. needservice:: github-issues
       :query: repo:useblocks/sphinxcontrib-needs node latexpdf
       :max_content_lines: 4
       :id_prefix: EXAMPLE_

Click the small arrow under the need id to see all meta data.

.. needservice:: github-issues
   :query: repo:useblocks/sphinxcontrib-needs node latexpdf
   :max_amount: 1
   :id_prefix: EXAMPLE_
   :max_content_lines: 4


