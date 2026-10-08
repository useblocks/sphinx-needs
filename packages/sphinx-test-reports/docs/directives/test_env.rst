.. _test-env:

test-env
========

Adds a table with information about the used test environment.
This can be operating system, used python version, installed package and much more.

This information needs to be provided via json-file. Currently **sphinx-test-reports** supports the output of
`tox-env-report <https://tox-envreport.readthedocs.io/en/latest/>`_ only.

Each environment is a section of its own, titled with the environment's name,
one level below the section the directive stands in.
It has an id and a permalink, and ``.. contents::`` and the sidebar list it like any other section
(a directive inside a list item makes sections inside that item, which ``.. contents::`` and the sidebar do not list).
Text written after the directive in the same section follows the last generated section -- in a PDF (LaTeX) it is part of it --
so write the directive at the end of its section, or give the text that follows a heading of its own.

The file is read as UTF-8, with or without a byte-order mark (what Windows editors and PowerShell's ``Out-File`` write),
whatever the machine's locale.
A file that does not exist, is not UTF-8 or is not valid JSON is a ``test_reports.report_missing`` / ``test_reports.report_unreadable`` warning
located on the directive, and an error box with the same text takes the place of the sections;
the build goes on (see :ref:`tr_warnings`).

The file must be a JSON object of environments, each an object of variables.
A file that is anything else (an array, a string, a number) shows nothing,
with a ``test_reports.env_shape`` warning and the error box;
an environment whose value is not an object is skipped with a ``test_reports.env_shape`` warning naming it,
and the other environments are shown.

A variable's value is shown as the file spells it:
a string as it is (an empty string is an empty cell),
``true``, ``false``, ``null`` and numbers in their JSON spelling,
an array or an object as an indented JSON block.

tox based workflow
------------------

#. Use `tox <https://tox.readthedocs.io/>`_ for running your tests on different environments.
#. Install `tox-env-report <https://tox-envreport.readthedocs.io/en/latest/>`_.
#. Run your tests with tox
#. Locate generated file ``tox-envreport.json`` in your ``.tox`` folder
#. Use this file like ``.. test-env:: ../.tox/tox-envreport.json``

Options
-------

.. contents::
   :local:

data
~~~~

Use ``:data:`` to  define which data shall be printed out.

``:data:`` must contain a comma separated list and the requested data is the element key, which got stored in the
related dictionary of the requested environment.

Sub-keys like ``python.version`` are currently not supported.

Blank elements are ignored, and a variable named twice is shown once.
A ``:data:`` that names no variable at all (``:data: ,``) shows every variable, as no ``:data:`` does.
A variable that a shown environment lacks is ONE ``test_reports.env_key_not_present`` warning per directive:
``option 'x' is not present in JSON file`` when no shown environment holds it,
else ``option 'x' is not present in 'flake8, pylint' environment file``, naming the environments that lack it.

**Example**

.. code-block:: rst

   .. test-env:: ../.tox/tox-envreport.json
      :data: hostname, python, toxversion

Example of supported parameters (if using `tox-env-report <https://tox-envreport.readthedocs.io/en/latest/>`_):

* name
* host
* installed_packages
* path
* platform
* reportversion
* setup
* test
* toxversion

env
~~~

Prints out only the data of the given environment. ``:env:`` must be a comma separated list of environment names.

The give name should exist in the given ``json-file``;
a name it does not hold is a ``test_reports.env_not_present`` warning (``environment 'py27' is not present in JSON file``),
and the other environments are shown.
Blank elements are ignored, and an environment named twice is shown once.

**Example**

.. code-block:: rst

   .. test-env:: ../.tox/tox-envreport.json
      :env: py27, py35, flake8

raw
~~~

``:raw:`` is a flag and if it is set, the output is a text interpretation of the json data.

Other options like ``:data:`` and ``:env:`` can still be used to filter the output.

**Example**

.. code-block:: rst

   .. test-env:: ../.tox/tox-envreport.json
      :raw:

Examples
--------

Default output
~~~~~~~~~~~~~~

.. code-block:: rst

   .. test-env: my/path/to/tox-envreport-short.json
      :env: py27
      :data: name, host, installed_packages

.. test-env:: ../tests/doc_test/utils/tox-report-short.json
   :data: name, host, installed_packages
   :env: py27

Raw output
~~~~~~~~~~

.. code-block:: rst

   .. test-env: my/path/to/tox-envreport-short.json
      :raw:
      :env: py27
      :data: name, host, installed_packages

.. test-env:: ../tests/doc_test/utils/tox-report-short.json
   :raw:
   :data: name, host, installed_packages
   :env: py27
