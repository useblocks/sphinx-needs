.. _needreport:

needreport
==========

.. versionadded:: 1.0.1

**needreport** documents the following configurations from **conf.py**:

* :ref:`Types <needs_types>`
* :ref:`Links <needs_extra_links>`
* :ref:`Options <needs_extra_options>`

and it also adds some needs metrics using the `usage`_ option.

To use the ``needreport`` directive, you need to set the :ref:`needs_report_template`
configuration variable. If you do not set the :ref:`needs_report_template`
configuration variable, the plugin uses the default needs report template.

The :ref:`needs_report_template` value is a path to the
`jinja2 <https://jinja.palletsprojects.com/en/2.11.x/templates/>`_ template file.
You can use the template file to customise the content generated  by ``needreport``.

.. note::

   The default needs report template is set to use ``dropdown`` directives for containing each configuration type, which requires the ``dropdown`` directive to be available in your Sphinx environment. If you do not have the ``dropdown`` directive available, you can use the following configuration to set the default needs report template to use ``admonition`` directives instead:

   .. code-block:: python

      needs_render_context = {
         "report_directive": "admonition",
      }

.. need-example::

   .. needreport::
      :types:


Options
-------

.. _types:

types
~~~~~

Flag for adding information about the :ref:`needs_types` configuration parameter.
The flag does not require any values.

.. need-example::

   .. needreport::
      :types:


.. _links:

links
~~~~~

Flag for adding information about the :ref:`needs_extra_links` configuration parameter.
The flag does not require any values.

.. need-example::

   .. needreport::
      :links:


.. _options:

options
~~~~~~~

Flag for adding information about the :ref:`needs_extra_options` configuration parameter.
The flag does not require any values.

.. need-example::

   .. needreport::
      :options:

usage
~~~~~
Flag for adding information about all the ``need`` objects in the current project.
The flag does not require any values.

.. need-example::

   .. needreport::
      :usage:
