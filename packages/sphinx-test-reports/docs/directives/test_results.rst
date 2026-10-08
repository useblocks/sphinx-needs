.. _test-results:

test-results
============

This directive adds a results table of a given junit xml file to the current page.

.. code-block:: rst

	.. test-results:: my/path/to/test.xml

Each suite of the file is a section of its own, titled with the suite's name,
one level below the section the directive stands in.
It has an id and a permalink, and ``.. contents::`` and the sidebar list it like any other section
(a directive inside a list item makes sections inside that item, which ``.. contents::`` and the sidebar do not list).
A suite that holds suites of its own (``<testsuite>`` inside ``<testsuite>``) shows its own counters, its time and the table of its own cases,
then a section of the same kind for each suite nested in it, inside its own section, at every depth.
Text written after the directive in the same section follows the last generated section -- in a PDF (LaTeX) it is part of it --
so write the directive at the end of its section, or give the text that follows a heading of its own;
that is why the note on this page stands above the examples.
The examples below stand in this page's top section, so each suite is one of its subsections;
the last one is a nested report.

A report that does not exist, or that cannot be read -- it is not well-formed XML, a numeric attribute is not a number,
or it is a ``.json`` file, which ``test-results`` does not read --
is a ``test_reports.report_missing`` / ``test_reports.report_unreadable`` warning located on the directive,
and an error box with the same text takes the place of the sections; the build goes on (see :ref:`tr_warnings`).
The directive takes no options:
an option written under it is docutils' ``unknown option`` error, as for any directive.

.. note::

	Each test framework, like pytest or nosetest, generates a little different junit-xml file with more or less data.
	If a specific data is not available in the given xml-file, sphinx-test-reports fills the information with
	``unknown`` for strings or ``-1`` for numbers.

.. test-results:: ../tests/doc_test/utils/xml_data.xml

.. test-results:: ../tests/doc_test/utils/pytest_data.xml

.. test-results:: ../tests/doc_test/utils/nose_data.xml

.. test-results:: ../tests/doc_test/utils/pytest_nested_example.xml
