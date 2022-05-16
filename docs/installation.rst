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
    # or
    poetry install


Activation
----------

For final activation, please add `sphinx_needs` to the project's extension list of your **conf.py** file::

   extensions = ["sphinx_needs",]

For the full configuration, please read :ref:`config`.

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
                    'sphinx_needs']

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


Using Docker
------------

Sphinx-Needs is also available as a Docker Image.

See :ref:`docker` for the documentation and hints how to use it.
