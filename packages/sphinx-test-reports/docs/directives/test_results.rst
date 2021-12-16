.. _test-results:

test-results
============

This directive adds a results table of a given junit xml file to the current page.

.. code-block:: rst

	.. test-results:: my/path/to/test.xml


.. test-results:: ../tests/data/xml_data.xml

.. test-results:: ../tests/data/pytest_data.xml

.. test-results:: ../tests/data/nose_data.xml


.. note::

	Each test framework, like pytest or nosetest, generates a little different junit-xml file with more or less data.
	If a specific data is not available in the given xml-file, sphinx-test-reports fills the information with
	``unknown`` for strings or ``-1`` for numbers.
