:hide-navigation:

Installation
============

Test reports come in two distributions, and each consumer installs the one it needs.

A documentation project needs the Sphinx extension, **sphinx-test-reports**. It brings the
documentation toolchain -- Sphinx, docutils and
`Sphinx-Needs <https://sphinx-needs.readthedocs.io/en/latest/>`_ -- and ub-test-reports
with it::

   pip install sphinx-test-reports

A build action that only runs the :ref:`test-reports command <cli>`, which turns test
results into a ``needs.json`` without a Sphinx build, installs **ub-test-reports**, which
has no Sphinx in it (its dependencies are ``lxml`` and ``ub-project``)::

   pip install ub-test-reports

A test runner that should write the XML shape the extension reads installs the
:ref:`pytest plugin <pytest_plugin>`, ub-test-reports' ``pytest`` extra, which adds pytest
and nothing of the documentation toolchain::

   pip install "ub-test-reports[pytest]"

ub-test-reports has its own version number and
`changelog <https://github.com/useblocks/sphinx-needs/blob/master/packages/ub-test-reports/docs/changelog.rst>`__.

.. versionchanged:: 2.0.0
   ``pip install sphinx-test-reports`` -- without an extra -- no longer
   installs Sphinx and Sphinx-Needs. A documentation project has to add the
   ``sphinx`` extra to its install line; a test runner or a build action that
   has no documentation toolchain no longer gets one.

.. versionchanged:: 3.0.0
   The converter, the pytest plugin and the parsers moved to their own distribution,
   ub-test-reports, and ``pip install sphinx-test-reports`` installs Sphinx, docutils and
   Sphinx-Needs again: they are dependencies of the extension, not an extra. A test runner
   or a build action that installed sphinx-test-reports for the command or the plugin
   installs ub-test-reports instead. The ``sphinx`` extra is accepted and ignored, and the
   ``pytest`` extra installs ``ub-test-reports[pytest]``, until 4.0.

The extension supports Sphinx 7.4 or later, docutils 0.21 or later and Sphinx-Needs 8.5
(``>=8.5.0,<9``); ``pip`` resolves those as it installs it, and the extension itself
refuses an older Sphinx when it loads.

After that the extension must be added to the ``conf.py`` file::

   extensions = ['sphinx_needs',
                 'sphinx_test_reports',
                 'sphinxcontrib.plantuml']

.. versionchanged:: 3.0.0
   The extension is ``sphinx_test_reports``. Before 3.0 it was
   ``sphinxcontrib.test_reports``, and that name still loads the extension
   until 4.0, with a warning of type ``test_reports.deprecated`` asking for
   the new one. A build run with ``-W`` fails on that warning: rename the entry, or add
   ``suppress_warnings = ["test_reports.deprecated"]`` to ``conf.py`` until you
   can. See the :doc:`changelog </changelog>` for the other old names.

Please note, ``Sphinx-Test-Report`` is based on the
`Sphinx-needs extension <https://sphinx-needs.readthedocs.io/en/latest/>`_.
Therefore it must also be added to the ``extensions`` list!

And same for `PlantUML <http://plantuml.com>`_, which is important to render flowcharts for filtered
test-cases.

More details can be found in the
`installation-guide <https://sphinx-needs.readthedocs.io/en/latest/installation.html>`_
of ``Sphinx-Needs``.
