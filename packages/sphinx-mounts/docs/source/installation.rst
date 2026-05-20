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

Supported versions:

- Python 3.12 and later
- Sphinx 7.4, 8.x, 9.x
