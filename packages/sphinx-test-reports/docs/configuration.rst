:hide-navigation:

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

   ['test-file', 'testfile', 'test-file', 'TF_', '#ffffff', 'node']

All of the following arguments must be set:

1. **directive name**
2. **need directive name**
3. **need print name**
4. **need id prefix**
5. **need color**
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

   ['test-suite', 'testsuite', 'test-suite', 'TS_', '#cccccc', 'node']

Please read :ref:`tr_file` for more details.

.. _tr_case:

tr_case
-------

``tr_case`` allows to specify a custom directive name and need-configuration for ``test-case``.

Instead of using ``.. test-case::`` you may want to use ``.. test-run::``.

By default ``tr_case`` is set to::

   ['test-case', 'testcase', 'test-case', 'TC_', '#999999', 'node']

Please read :ref:`tr_file` for more details.

tr_report_template
------------------

``tr_report_template`` allows to specify a custom template for testcase visualisation. Provide a relative path
(from conf.py) or provide an absolute path to your template.

**A simple example with a scrambled order:**

.. literalinclude:: ./custom_test_report_template.txt
   :language: rst

.. _tr_suite_id_length:

tr_suite_id_length
------------------
.. versionadded:: 1.0.1

Defines the length of the calculated ID for test suites.

This may be needed, if a junit-xml files contains many test suites.

Default: **3**

.. _tr_case_id_length:

tr_case_id_length
------------------
.. versionadded:: 1.0.1

Defines the length of the calculated ID for test cases.

This may be needed, if a junit-xml files contains many test cases.

Default: **5**


.. _tr_extra_options:

tr_extra_options
----------------
.. versionadded:: 1.2.0 

Defines extra options you can use in `test-file` `test-case` and `test-suite`.
These options also have to be registered in either needs_extra_options or needs_extra_links.

**Example**

.. code-block:: python

   # In conf.py
   tr_extra_options = ['more_info', 'related_to', 'priority']
   
   # Define as regular options
   needs_extra_options = ['more_info', 'priority']
   
You can then use these options in your directives:

.. code-block:: rst

   .. test-file:: Enhanced test data
      :file: path/to/test_data.xml
      :id: TESTFILE_EXTRA
      :more_info: This is additional information about the test
      :priority: high

   This test file contains enhanced metadata using custom extra options.

.. _tr_import_encoding:

tr_import_encoding
------------------
.. versionadded:: 1.0.3

Defines the encoding for imported files, e.g. in custom templates.

Default: **utf8**

.. _tr_json_mapping:

tr_json_mapping
---------------
.. versionadded:: 1.0.3

Takes a mapping configuration, which defines how to map the JSON structure to the internal structure used by
``Sphinx-Test-Reports``.

``tr_json_mapping`` is a dictionary, where the first key is a name for the configuration.
The name is currently just a placeholder and the first config is used for all JSON imports.

Two mappings must be configured as dictionary, one for ``testsuite`` and one for the nested ``testcase``.

The key of this dictionary elements is the **internal** name and fix.

The value is a tuple, containing a **selector list** and a **default value**, if the selector does not find any data.

The **selector** is a list, where each entry is representing one level of the data structure.
If the entry is a string, it is used as a key for a dict. If it is a integer number, it is taken as position
of a list.

**JSON example**

.. code-block:: python

   {
       "level_1": {
           "level_2": [
               {"value": "Hello!"}
               {"value": "Bye Bye!"}
           ]
       }
   }

Given the above JSON example, the following "selector" will address the value ``Bye Bye!``::

   ["level_1", "level_2", 1, "value"]


**Example config**

This example contains **all** internal elements and a mapping as example.
For ``testsuite`` the value ``testcases`` defines the location of nested testcases.

An example of a JSON file, which supports the below configuration, can be seen in :ref:`json_example`.

.. code-block:: python

   tr_json_mapping = {
      "json_config_1": {
         "testsuite": {
            "name":        (["name"], "unknown"),
            "tests":       (["tests"], "unknown"),
            "errors":      (["errors"], "unknown"),
            "failures":    (["failures"], "unknown"),
            "skips":       (["skips"], "unknown"),
            "passed":      (["passed"], "unknown"),
            "time":        (["time"], "unknown"),
            "testcases":   (["testcase"], "unknown"),
         },
         "testcase": {
            "name":        (["name"], "unknown"),
            "classname":   (["classname"], "unknown"),
            "file":        (["file"], "unknown"),
            "line":        (["line"], "unknown"),
            "time":        (["time"], "unknown"),
            "result":      (["result"], "unknown"),
            "type":        (["type"], "unknown"),
            "text":        (["text"], "unknown"),
            "message":     (["message"], "unknown"),
            "system-out":  (["system-out"], "unknown"),
         }
      }
   }


