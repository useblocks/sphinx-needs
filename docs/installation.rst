Installation
============

Using poetry
------------

.. code-block:: bash

    poetry add sphinx-needs[all]

Using pip
---------

.. code-block:: bash

    pip install sphinx-needs[all]

.. note::

   Prior version **1.0.1** the package was named ``sphinxcontrib-needs``.

Using sources
-------------

.. code-block:: bash

    git clone https://github.com/useblocks/sphinx-needs
    cd sphinx-needs
    pip install .[all]
    # or
    poetry install --extras all


Activation
----------

For final activation, please add `sphinx_needs` to the project's extension list of your **conf.py** file.

.. code-block:: python

   extensions = ["sphinx_needs",]

For the full configuration, please read :ref:`config`.

.. note::

   Prior version **1.0.1** the extensions was called ``sphinxcontrib.needs``.

.. _install_matplotlib_numpy:

Matplotlib/NumPy support
------------------------

:ref:`needpie` and :ref:`needbar` uses `Matplotlib <https://matplotlib.org>`_ and `Numpy <https://numpy.org>`_ for generating graphs.

The recommended install method (via `sphinx-needs[all]`) downloads matplotlib by
default. If you don't use these graph-related features, it's possible to install
the lighter `sphinx-needs` package without optional dependencies.

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


