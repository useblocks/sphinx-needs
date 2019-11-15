pytest
======

The data is coming from a pytest-run on the tests of the sphinx project.

| Test suite: :need_count:`'pytest_sphinx' in tags and type=='testsuite'`
| Test cases: :need_count:`'pytest_sphinx' in tags and type=='testcase'`
| Failed test cases: :need_count:`'pytest_sphinx' in tags and 'failure' == result and type=='testcase'`
| Skipped test cases: :need_count:`'pytest_sphinx' in tags and 'skipped' == result and type=='testcase'`

**Failed test cases**:

.. needtable::
   :filter: 'pytest_sphinx' in tags and 'failure' == result
   :columns: id, title, result
   :style: table
   :style_row: tr_[[copy('result')]]

**Skipped test cases**:

.. needtable::
   :filter: 'pytest_sphinx' in tags and 'skipped' == result
   :columns: id, title, result
   :style: table
   :style_row: tr_[[copy('result')]]

Imported data
-------------

.. test-file:: pytest Sphinx data
   :id: SPHINX
   :tags: pytest_sphinx
   :file: ../tests/data/pytest_sphinx_data.xml
   :auto_suites:
   :auto_cases:
