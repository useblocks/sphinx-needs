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

.. versionchanged:: 1.5.0
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
                 'sphinxcontrib.test_reports',
                 'sphinxcontrib.plantuml']

Please note, ``Sphinx-Test-Report`` is based on the
`Sphinx-needs extension <https://sphinx-needs.readthedocs.io/en/latest/>`_.
Therefore it must also be added to the ``extensions`` list!

And same for `PlantUML <http://plantuml.com>`_, which is important to render flowcharts for filtered
test-cases.

More details can be found in the
`installation-guide <https://sphinx-needs.readthedocs.io/en/latest/installation.html>`_
of ``Sphinx-Needs``.
