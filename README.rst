**Complete documentation**: http://sphinxcontrib-needs.readthedocs.io/en/latest/

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
::

    poetry add sphinxcontrib-needs


Using pip
---------
::

    pip install sphinxcontrib-needs

Using sources
-------------
::

    git clone https://github.com/useblocks/sphinxcontrib-needs
    cd sphinxcontrib-needs
    pip install .

Activation
----------

Add **sphinxcontrib.needs** to your extensions::

    extensions = ["sphinxcontrib.needs",]
