.. _styles:

Custom styles
=============

The layout and structure of needs can be highly customized.

There are three ways to do this:

* Define own jinja template for a need
* Provide a css file by using :ref:`needs_css`
* Set own css on sphinx level

Need jinja template
-------------------

Please see :ref:`needs_template` on the configuration page.

.. _styles_css:

Sphinx-needs CSS option
-----------------------

A css file can be set in the **conf.py** file by setting **needs_css**.
See :ref:`needs_css` on the configuration page for more information.

Sphinx-needs provides the following css styles:

**blank.css**

.. image:: _static/need_blank.png

**modern.css**

.. image:: _static/need_modern.png

**dark.css**

.. image:: _static/need_dark.png

blank.css
~~~~~~~~~
.. literalinclude:: ../sphinxcontrib/needs/css/blank.css

modern.css
~~~~~~~~~~
.. literalinclude:: ../sphinxcontrib/needs/css/modern.css

dark.css
~~~~~~~~
.. literalinclude:: ../sphinxcontrib/needs/css/dark.css

Own CSS file on sphinx level
----------------------------

If you want to use most of the sphinx-needs internal styles but only need some specific changes for single elements, you
can provide your own CSS file by register it inside your conf.py::

    def setup(app):
        app.add_stylesheet('css/my_custom.css')  # may also be an URL

.. hint::

    Do not name it **custom.css** if you are using `Read the docs <http://readthedocs.org>`_ as
    this name is already taken.

