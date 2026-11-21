Dynamic functions
=================

Sphinx-Test-Reports provides dynamic functions for Sphinx-Needs.

Read chapter `Dynamic function <https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html>`_
from Sphinx-Needs documentation to know how to use them.


tr_link
---------
Links a need (e.g testcase) automatically to other needs, which have a specific value in a given option.

**Usage**::

   .. test-case:: My test case
      :id: TESTCASE_1
      :file: my_test_file.xml
      :suite: pytest
      :classname: sphinxcontrib.test_reports.test_reports
      :case: FLAKE8
      :links: [[tr_link("source_option", "target_option")]]

``tr_link`` needs the following arguments:

* **source_option**: Name of an option of the need it is used in, whose values are compared. E.g. ``classname``.
* **target_option**: Name of an option of every need, which is compared with them. E.g. ``title``.

The function reads the ``source_option`` of the need, where it is used.
Then it goes through **all** needs, that need included, and checks if the value of their ``target_option`` is equal
to the value of the ``source_option``.
If this is the case, their IDs get stored and finally returned.

``source_option`` can also reference an option with comma separated values.
In this case a comparison is performed for each value, which may lead to multiple links.
A need matched by several of the values is linked once for each, and the links come in the order the project holds
its needs. The page and ``needs.json`` show the list sorted, each link once; a derived field that copies or counts
the link field reads the list as returned.
A need's ``target_option`` is compared whole, so one holding comma separated values, a list or a number never
matches; a ``source_option`` holding a list, a number or a boolean fails the call (other than an empty list, ``0``
or ``false``, which link nothing).

Sphinx-Needs' built-in
`links_from_match <https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html#links-from-match>`_
links the same needs for the usage above, with the two arguments in the other order:
``[[links_from_match('title', 'classname', include_self=True)]]`` for ``[[tr_link('classname', 'title')]]``.
It also splits a need's ``target_option`` on ``,``, and fails the call on a number or boolean option.

**include_parts** (optional, ``False`` by default, and given by name: a third positional argument is ignored, as it
always was): with ``include_parts=True``, the
`need parts <https://sphinx-needs.readthedocs.io/en/latest/roles.html#need-part>`_ of every need are compared too.
A part's ``target_option`` is read as the part answers a filter: its own ``id`` (the part's id), ``id_complete``
(``<need id>.<part id>``) and ``content`` (its text), no ``parent_need``, and its need's value of every other option.
A part that matches is linked by its address, ``<need id>.<part id>``, after its need, in part-id order.
So ``[[tr_link('case_name', 'id_complete', include_parts=True)]]`` links the part a test's ``case_name`` names by its
address. Without it, only needs are compared.

``tr_link`` declares what it reads to Sphinx-Needs
(`Declaring what a function reads <https://sphinx-needs.readthedocs.io/en/latest/dynamic_functions.html#dynamic-functions-reads>`_):
the ``source_option`` of its own need, and the ``target_option`` of every need (and of its parts).
So Sphinx-Needs computes its links with its built-in functions, in order,
and a ``links_from_filter``, a derived ``links`` or ``union`` link type,
or any other built-in function reading those links holds them,
where a Sphinx-Needs that orders it after the built-in functions read them empty.
A ``target_option`` naming the link type the call fills is a cycle (``needs.derive_cycle``),
and a ``source_option`` or ``target_option`` computed after the link fields cannot be read while they are,
so the call is not run (``needs.derive_scope``).

**Example**::

   .. spec:: sphinxcontrib.test_reports.test_reports
      :id: TESTSPEC_001
      :status: open
      :tags: example, link_example

      This specification specifies the test case ``sphinxcontrib.test_reports.test_reports``.

   .. test-case:: Flake8 test case
      :id: TESTLINK_1
      :file: ../tests/doc_test/utils/pytest_data.xml
      :suite: pytest
      :classname: sphinxcontrib.test_reports.test_reports
      :case: FLAKE8
      :tags: example, link_example
      :links: [[tr_link('classname', 'title')]]

      A simple test case.
      We will set a link to the need, which has our classname as title.

   .. needflow::
      :tags: link_example

.. spec:: sphinxcontrib.test_reports.test_reports
   :id: TESTSPEC_001
   :status: open
   :tags: example, link_example

   This specification specifies the test case ``sphinxcontrib.test_reports.test_reports``.

.. test-case:: Flake8 test case
   :id: TESTLINK_1
   :file: ../tests/doc_test/utils/pytest_data.xml
   :suite: pytest
   :classname: sphinxcontrib.test_reports.test_reports
   :case: FLAKE8
   :tags: example, link_example
   :links: [[tr_link('classname', 'title')]]

   A simple test case.
   We will set a link to the need, which has our classname as title.

.. needflow::
   :tags: link_example
