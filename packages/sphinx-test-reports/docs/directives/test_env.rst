test-env
============

This directive adds a table which shows tox-envreport.json, user can control output of this directive by adding specific options,
please see below example

How to use Example
------------------

.. code-block:: rst

	.. test-env: my/path/to/tox-envreport.json
		:env: py35, flake8
		:data: name, host, installed_packages

If ``:raw:`` flag is set all data is filtered according to ``:env:`` then ``:data:`` and shown in raw format
If any environment or data option is not present, it will throw a warning.

Supported Parameters for ``:data:``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- name
- host
- installed_packages
- path
- platform
- reportversion
- setup
- test
- toxversion

Example output
-------------------

.. test-env:: ../tests/data/tox-report.json
	:data: name, host, installed_packages , ,asd
	:env: py35, flake8, , ads,	
	:raw:
