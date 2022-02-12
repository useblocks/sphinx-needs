Installation
============

Using poetry
------------
::

    poetry add sphinxcontrib-needs[all]

Using pip
---------
::

    pip install sphinxcontrib-needs[all]

Using sources
-------------
::

    git clone https://github.com/useblocks/sphinxcontrib-needs
    cd sphinxcontrib-needs
    pip install .[all]
    # or
    poetry install --extras all


Activation
----------

For final activation, please add `sphinxcontrib.needs` to the project's extension list of your **conf.py** file::

   extensions = ["sphinxcontrib.needs",]

For the full configuration, please read :ref:`config`.

.. _install_matplotlib_numpy:

Matplotlib/NumPy support
----------------

:ref:`needpie` and :ref:`needbar` uses `Matplotlib <https://matplotlib.org>`_ and `Numpy <https://numpy.org>`_ for generating graphs.

The recommended install method (via `sphinxcontrib-needs[all]`) downloads
matplotlib by default as well as all other optional extras.

If you don't use the graphs feature, it's possible to install the lighter
`sphinxcontrib-needs` without optional dependencies.

.. _install_plantuml:

PlantUML support
----------------

:ref:`needflow` uses `PlantUML <http://plantuml.com>`_ and the
Sphinx-extension `sphinxcontrib-plantuml <https://pypi.org/project/sphinxcontrib-plantuml/>`_ for generating the flows.

Both must be available and correctly configured to work.

Install PlantUML
~~~~~~~~~~~~~~~~

#. Download the latest version of the plantuml.jar file:
   http://sourceforge.net/projects/plantuml/files/plantuml.jar/download
#. Inside your docs folder create a folder called ``utils`` and copy ``plantuml.jar`` into it.
#. Install sphinx support: ``pip install sphinxcontrib-plantuml``.
#. Add ``sphinxcontrib.plantuml`` to the sphinx extension list in ``conf.py``::

      extensions = ['sphinxcontrib.plantuml',
                    'sphinxcontrib.needs']

#. Configure plantuml in conf.py::

      on_rtd = os.environ.get('READTHEDOCS') == 'True'
      if on_rtd:
          plantuml = 'java -Djava.awt.headless=true -jar /usr/share/plantuml/plantuml.jar'
      else:
          plantuml = 'java -jar %s' % os.path.join(os.path.dirname(__file__), "utils", "plantuml.jar"))

      plantuml_output_format = 'png'

The final configuration contains already a setup for building and deploying the documentation on
`ReadTheDocs <https://readthedocs.org/>`_.

ReadTheDocs provides ``plantuml.jar`` already on their system, so there is no need to store it inside your
source version control system.


Using docker
------------

Sphinx-Needs got also dockerized by Till Witt.

See https://github.com/tlwt/sphinxneeds-docker for actual documentation and hints how to use it.
