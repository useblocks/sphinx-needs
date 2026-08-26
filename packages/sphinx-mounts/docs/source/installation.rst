Installation
============

Install from PyPI:

.. code-block:: bash

   pip install sphinx-mounts

Enable the extension in your ``conf.py``:

.. code-block:: python

   extensions = ["sphinx_mounts"]

Then describe your mounts declaratively in ``ubproject.toml`` next to
``conf.py``. See :doc:`configuration` for the schema.

sphinx-mounts is also the Sphinx-side reader for the shared
``ubproject.toml`` keys that decide which files are in the build for the
current variant: :ref:`[[source.variant_sources]] <variant-sources>`, which
narrows a file set by glob, and :ref:`if on a mount entry <mount-gating>`,
which gates a whole mounted bundle. A project with **no mounts at all** can
install sphinx-mounts purely for the first, to have ``sphinx-build`` narrow
its document set per variant exactly as `ubCode`_ does.

Supported versions:

- Python 3.12 and later
- Sphinx 7.4, 8.x, 9.x
