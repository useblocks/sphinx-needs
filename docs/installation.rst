.. _installation:

Installation
============

.. .. only:: html

..    .. image:: https://img.shields.io/pypi/dm/sphinx-needs.svg
..        :target: https://pypi.python.org/pypi/sphinx-needs
..        :alt: Downloads
..    .. image:: https://img.shields.io/pypi/l/sphinx-needs.svg
..        :target: https://pypi.python.org/pypi/sphinx-needs
..        :alt: License
..    .. image:: https://img.shields.io/pypi/pyversions/sphinx-needs.svg
..        :target: https://pypi.python.org/pypi/sphinx-needs
..        :alt: Supported versions
..    .. image:: https://readthedocs.org/projects/sphinx-needs/badge/?version=latest
..        :target: https://readthedocs.org/projects/sphinx-needs/
..        :alt: ReadTheDocs
..    .. image:: https://github.com/useblocks/sphinx-needs/actions/workflows/ci.yaml/badge.svg
..        :target: https://github.com/useblocks/sphinx-needs/actions
..        :alt: GitHub CI Action status
..    .. image:: https://img.shields.io/pypi/v/sphinx-needs.svg
..        :target: https://pypi.python.org/pypi/sphinx-needs
..        :alt: PyPI Package latest release

Using pip
---------

.. code-block:: bash

    pip install sphinx-needs

If you wish to also use the plotting features of sphinx-needs (see :ref:`needbar` and :ref:`needpie`), you need to also install ``matplotlib``, which is available *via* the ``plotting`` extra:

.. code-block:: bash

    pip install sphinx-needs[plotting]

.. note::

   Prior to version **1.0.1** the package was named ``sphinxcontrib-needs``.

Using sources
-------------

.. code-block:: bash

    git clone https://github.com/useblocks/sphinx-needs
    cd sphinx-needs
    pip install .


Activation
----------

For final activation, please add ``sphinx_needs`` to the project's extension list of your **conf.py** file.

.. code-block:: python

   extensions = ["sphinx_needs",]

For the full configuration, please read :ref:`config`.

.. _install_theme:

HTML Theme support
------------------

To represent needs and data tables within HTML builds,
``sphinx-needs`` injects some CSS styles into the pages.

This CSS is designed to be generally compatible with common Sphinx themes,
but may require some adjustments depending on the theme you use.
In particular, `CSS Variables`_ are used to specify the coloring of most components.
The default values are as follows (see also :ref:`needs_css`):

.. dropdown:: Default CSS Variables
    :icon: paintbrush

    .. literalinclude:: ../sphinx_needs/css/themes/modern.css
        :language: css

These variables can be overridden by adding your own CSS file to the Sphinx project
(see `this how-to`_).

For examples of how to adjust the CSS, this documentation is configured to build against multiple themes using the following CSS:

.. dropdown:: furo
    :icon: paintbrush

    .. literalinclude:: _static/_css/furo.css
        :language: css
        :start-after: /* doc config start */
        :end-before: /* doc config end */

.. dropdown:: pydata-sphinx-theme
    :icon: paintbrush

    .. literalinclude:: _static/_css/pydata_sphinx_theme.css
        :language: css
        :start-after: /* doc config start */
        :end-before: /* doc config end */

.. dropdown:: sphinx-rtd-theme
    :icon: paintbrush

    .. literalinclude:: _static/_css/sphinx_rtd_theme.css
        :language: css

.. dropdown:: sphinx-immaterial
    :icon: paintbrush

    .. literalinclude:: _static/_css/sphinx_immaterial.css
        :language: css
        :start-after: /* doc config start */
        :end-before: /* doc config end */

.. _CSS Variables: https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties
.. _this how-to: https://docs.readthedocs.io/en/stable/guides/adding-custom-css.html

.. _install_plantuml:

PlantUML support
----------------

:ref:`needflow` uses `PlantUML <http://plantuml.com>`_ and the
Sphinx-extension `sphinxcontrib-plantuml <https://pypi.org/project/sphinxcontrib-plantuml/>`_ for generating the flows.

Both must be available and correctly configured to work.


Install PlantUML
~~~~~~~~~~~~~~~~

1. Download the latest version of the plantuml.jar file:
   http://sourceforge.net/projects/plantuml/files/plantuml.jar/download
2. Make a new folder called ``utils`` inside your docs folder. Copy the ``plantuml.jar`` file into the ``utils`` folder.
3. Install the plantuml sphinx extension: ``pip install sphinxcontrib-plantuml``.
4. Add ``sphinxcontrib.plantuml`` to the sphinx extension list in ``conf.py``

.. code-block:: python

      extensions = ['sphinxcontrib.plantuml',
                    'sphinx_needs']


5. Configure plantuml in ``conf.py``

.. code-block:: python

  on_rtd = os.environ.get('READTHEDOCS') == 'True'
  if on_rtd:
      plantuml = 'java -Djava.awt.headless=true -jar /usr/share/plantuml/plantuml.jar'
  else:
      plantuml = 'java -jar %s' % os.path.join(os.path.dirname(__file__), "utils", "plantuml.jar"))

      plantuml_output_format = 'png'

The final configuration contains already a setup for building and deploying the documentation on
`ReadTheDocs <https://readthedocs.org/>`_.

ReadTheDocs provides ``plantuml.jar`` already on their system, so do not store it inside your source version control system.


Using Docker
------------

Sphinx-Needs is also available as a Docker Image.

See :ref:`docker` for the documentation and hints how to use it.

.. _ide:
.. _ide_vscode:

VS Code Extension
-----------------

The VS Code extension `ubCode <https://marketplace.visualstudio.com/items?itemName=useblocks.ubcode>`_ provides 
support for Sphinx-Needs.
See more details in the `Documentation <https://docs.useblocks.com/ubcode/>`_.
