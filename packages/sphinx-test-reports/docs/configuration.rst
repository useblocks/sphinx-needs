Configuration
=============
The following options can be set inside the ``conf.py`` file of your Sphinx project.

.. contents::
   :local:

tr_rootdir
----------
``tr_rootdir`` takes a path, which is used as *root dir* for all provided file paths in other directives.

By default ``tr_rootdir`` contains the configuration folder of your Sphinx project (The one with ``conf.py`` in it).

.. _tr_file:

tr_file
-------
``tr_file`` allows to specify a custom directive name and need-configuration for ``test-file``.

Instead of using ``.. test-file::`` you may want to use ``.. test-path::``.

It may get also important to solve directive name conflicts with other Sphinx extensions.

By default ``tr_file`` is set to::

   ['test-file', 'testfile', 'Test-File', 'TF_', '#ffffff', 'node']

All of the following arguments must be set:

1. **directive name**
2. **need directive name**
3. **need print name**
4. **need id prefix**
5. **need collor**
6. **need plantuml style**

The parameters **2-6** are used to configure the underlying Sphinx-needs.
See it's
`documentation about needs_types <https://sphinx-needs.readthedocs.io/en/latest/configuration.html#needs-types>`_
for more details.

.. _tr_suite:

tr_suite
--------

``tr_suite`` allows to specify a custom directive name and need-configuration for ``test-suite``.

Instead of using ``.. test-suite::`` you may want to use ``.. test-container::``.

By default ``tr_suite`` is set to::

   ['test-suite', 'testsuite', 'Test-Suite', 'TS_', '#cccccc', 'node']

Please read :ref:`tr_file` for more details.

.. _tr_case:

tr_case
-------

``tr_case`` allows to specify a custom directive name and need-configuration for ``test-case``.

Instead of using ``.. test-case::`` you may want to use ``.. test-run::``.

By default ``tr_case`` is set to::

   ['test-case', 'testcase', 'Test-Case', 'TC_', '#999999', 'node']

Please read :ref:`tr_file` for more details.

tr_report_template
------------------

``tr_report_template`` allows to specify a custom template for testcase visualisation. Provide a relative path
(from conf.py) or provide an absolute path to your template.

**A simple example with a scrambled order:**

.. literalinclude:: ./custom_test_report_template.txt
   :language: rst