:hide-navigation:

Installation
============

The package has three consumers, and each installs a different part of it.

A documentation project needs the Sphinx extension, and with it the
documentation toolchain -- Sphinx and
`Sphinx-Needs <https://sphinx-needs.readthedocs.io/en/latest/>`_ -- which is
the ``sphinx`` extra of the package::

   pip install "sphinx-test-reports[sphinx]"

A test runner that should write the XML shape the extension reads installs the
:ref:`pytest plugin <pytest_plugin>` as the ``pytest`` extra, which adds pytest
and nothing of the documentation toolchain::

   pip install "sphinx-test-reports[pytest]"

A build action that only runs the :ref:`test-reports command <cli>`, which
turns test results into a ``needs.json`` without a Sphinx build, installs the
bare package, whose single dependency is ``lxml``::

   pip install sphinx-test-reports

.. versionchanged:: 2.0.0
   ``pip install sphinx-test-reports`` -- without an extra -- no longer
   installs Sphinx and Sphinx-Needs. A documentation project has to add the
   ``sphinx`` extra to its install line; a test runner or a build action that
   has no documentation toolchain no longer gets one.

The ``sphinx`` extra also states the supported versions: Sphinx 7.4 and
Sphinx-Needs 6.0.1 or later. An extra is opt-in, so a project that keeps
installing the bare package into an environment holding an older toolchain
would never be told by ``pip``; the extension therefore checks the installed
versions when Sphinx loads it and stops the build with a message naming the
install line above.

After that the extension must be added to the ``conf.py`` file::

   extensions = ['sphinx_needs',
                 'sphinx_test_reports',
                 'sphinxcontrib.plantuml']

.. versionchanged:: 3.0.0
   The extension is ``sphinx_test_reports``. Before 3.0 it was
   ``sphinxcontrib.test_reports``, and that name still loads the extension
   until 4.0, with a ``[test_reports.deprecated]`` warning asking for the new
   one. A build run with ``-W`` fails on that warning: rename the entry, or add
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
