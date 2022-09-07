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
configuration variable. The :ref:`needs_report_template` value is a path to the
`jinja2 <https://jinja.palletsprojects.com/en/2.11.x/templates/>`_ template file.
You can use the template file to customise the content generated  by ``needreport``.

|ex|

.. code-block:: rst

   .. needreport::
      :types:

|out|

.. needreport::
   :types:


Options
-------

.. _types:

types
~~~~~

Flag for adding information about the :ref:`needs_types` configuration parameter.
The flag does not require any values.

|ex|

.. code-block:: rst

   .. needreport::
      :types:

|out|

.. needreport::
   :types:


.. _links:

links
~~~~~

Flag for adding information about the :ref:`needs_extra_links` configuration parameter.
The flag does not require any values.

|ex|

.. code-block:: rst

   .. needreport::
      :links:

|out|

.. needreport::
   :links:


.. _options:

options
~~~~~~~

Flag for adding information about the :ref:`needs_extra_options` configuration parameter.
The flag does not require any values.

|ex|

.. code-block:: rst

   .. needreport::
      :options:

|out|

.. needreport::
   :options:

usage
~~~~~
Flag for adding information about all the ``need`` objects in the current project.
The flag does not require any values.

|ex|

.. code-block:: rst

   .. needreport::
      :usage:

|out|

.. needreport::
   :usage:
