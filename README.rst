**Complete documentation**: http://sphinx-needs.readthedocs.io/en/latest/

**Attention**: ``sphinxcontrib-needs`` got renamed to ``sphinx-needs``. This affects also the URLs for documentation and repository:

* Docs: https://sphinx-needs.readthedocs.io/en/latest/
* Repo: https://github.com/useblocks/sphinx-needs


Introduction
============

``Sphinx-Needs`` allows the definition, linking and filtering of class-like need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via configuration (for instance to support bugs or user stories).

A default requirement need looks like:

.. image:: https://raw.githubusercontent.com/useblocks/sphinxcontrib-needs/master/docs/_images/need_1.png
   :align: center

Layout and style of needs can be highly customized, so that a need can also look like:

.. image:: https://raw.githubusercontent.com/useblocks/sphinxcontrib-needs/master/docs/_images/need_2.png
   :align: center

Take a look into our `Examples <https://sphinxcontrib-needs.readthedocs.io/en/latest/examples/index.html>`_ for more
pictures and ideas how to use ``Sphinx-Needs``.

For filtering and analyzing needs, ``Sphinx-Needs`` provides different, powerful possibilities:

.. list-table::
   :header-rows: 1
   :widths: 46,14,40

   - * `needtable <https://sphinxcontrib-needs.readthedocs.io/en/latest/directives/needtable.html>`_
     * `needflow <https://sphinxcontrib-needs.readthedocs.io/en/latest/directives/needflow.html>`_
     * `needpie <https://sphinxcontrib-needs.readthedocs.io/en/latest/directives/needpie.html>`_
   - * .. image:: https://raw.githubusercontent.com/useblocks/sphinxcontrib-needs/master/docs/_images/needtable_1.png
     * .. image:: https://raw.githubusercontent.com/useblocks/sphinxcontrib-needs/master/docs/_images/needflow_1.png
     * .. image:: https://raw.githubusercontent.com/useblocks/sphinxcontrib-needs/master/docs/_images/needpie_1.png

Installation
============

Using poetry
------------

.. code-block:: bash

    poetry add sphinx-needs

Using pip
---------

.. code-block:: bash

    pip install sphinx-needs

If you wish to also use the plotting features of sphinx-needs (see ``needbar`` and ``needpie``), you need to also install ``matplotlib``, which is available *via* the ``plotting`` extra:

.. code-block:: bash

    pip install sphinx-needs[plotting]

.. note::

   Prior version **1.0.1** the package was named ``sphinxcontrib-needs``.

Using sources
-------------

.. code-block:: bash

    git clone https://github.com/useblocks/sphinx-needs
    cd sphinx-needs
    pip install .
    # or
    poetry install


Activation
----------

For final activation, please add `sphinx_needs` to the project's extension list of your **conf.py** file.

.. code-block:: python

   extensions = ["sphinx_needs",]

.. note::

   Prior version **1.0.1** the extensions was called ``sphinxcontrib.needs``.

