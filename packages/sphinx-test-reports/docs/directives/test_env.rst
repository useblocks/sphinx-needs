.. _test-env:

test-env
========

Adds a table with information about the used test environment.
This can be operating system, used python version, installed package and much more.

This information needs to be provided via json-file. Currently **sphinx-test-reports** supports the output of
`tox-env-report <https://tox-envreport.readthedocs.io/en/latest/>`_ only.

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

The give name should exist in the given ``json-file``.

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
