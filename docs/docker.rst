.. _docker:

Sphinx-Needs Docker Image
=========================

Base Docker Image for Sphinx-Needs.

Status
------

+-----------+----------------------------------------------------------+
| Registry  | Status                                                   |
+===========+==========================================================+
| ``useblocks/sphinxneeds:latest`` |                                                          |
+-----------+----------------------------------------------------------+
| ``useblocks/sphinxneeds-latexpdf:latest`` |                                                          |
+-----------+----------------------------------------------------------+

Image Variants
--------------

The sphinxneeds images come in two flavors, each designed for a specific
use case containing sphinx-needs. 

``sphinxneeds:<version>``
~~~~~~~~~~~~~~~~~~~~~~~~~

This is the defacto image (size ~ 350M). If you are unsure about what
your needs are, you probably want to use this one. It is designed to be
used both as a throw away container (mount your source code and start
the container to start your app), as well as the base to build other
images off of.

**NOTE** The image does not include latex packages and therefore does
not support PDF generation. Please use the latex-pdf version below for
such usecases.

Included Tools
^^^^^^^^^^^^^^

The image is based on the `sphinx
image <https://hub.docker.com/r/sphinxdoc/sphinx>`__ and includes the
following tools.

+------------------------+
| Tools                  |
+========================+
| python-slim            |
+------------------------+
| sphinx                 |
+------------------------+
| sphinxcontrib-needs    |
+------------------------+
| sphinxcontrib-plantuml |
+------------------------+
| graphviz               |
+------------------------+
| jre                    |
+------------------------+

``sphinxneeds-latexpdf:<version>``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This image includes all the tools in the ``sphinxneeds:latest`` image
and additionally pdf generation tools. The image is approx ~ 1.5GB
large.


Included Tools
^^^^^^^^^^^^^^

The image is based on the `sphinx latexpdf
image <https://hub.docker.com/r/sphinxdoc/sphinx-latexpdf>`__ and
includes the following tools.

+------------------------+
| Tools                  |
+========================+
| python-slim            |
+------------------------+
| sphinx                 |
+------------------------+
| sphinxcontrib-needs    |
+------------------------+
| sphinxcontrib-plantuml |
+------------------------+
| graphviz               |
+------------------------+
| jre                    |
+------------------------+
| latexmk                |
+------------------------+
| texlive                |
+------------------------+

Getting Started
---------------

Prerequisites
~~~~~~~~~~~~~

Prerequisites
~~~~~~~~~~~~~

To use the image, to install and configure `Docker <https://www.docker.com/>`__  


Pulling the Image from Docker Hub
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


The image can be pulled by

::

   docker pull useblocks/sphinxneeds:latest

or

::

   docker pull useblocks/sphinxneeds-latexpdf:latest

A specific version can be pulled with a version tag.

For example,

::

   docker pull useblocks/sphinxneeds:0.7.8


Build The Image Locally
~~~~~~~~~~~~~~~~~~~~~~~

| To build the image locally, execute the following.
  ``bash ./build_docker.sh``
| **Note:** The script allows to choose between html and pdf version and
  the Sphinx-Needs version to be installed.

Usage
-----

The main use case of the image is to use in as the base-image for
sphinx-needs in pipelines.

Linux
~~~~~

.. code:: bash

   docker run --rm -it -v $(pwd):/sphinxneeds useblocks/sphinxneeds:latest <build-command>

Windows (cmd)
~~~~~~~~~~~~~

.. code:: bash

   docker run --rm -it -v %cd%:/sphinxneeds useblocks/sphinxneeds:latest <build-command>

Windows (Powershell)
~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   docker run --rm -it -v ${PWD}:/sphinxneeds useblocks/sphinxneeds:latest <build-command>

``<build-command>``\ s to be used are

Generate HTML
~~~~~~~~~~~~~

.. code:: bash

       make html

For example,

.. code:: bash

   docker run --rm -it -v $(pwd):/sphinxneeds useblocks/sphinxneeds:latest make html

Generate PDF
~~~~~~~~~~~~

.. code:: bash

       make latexpdf

The generated docs can be found in the ``docs/_build/`` folder.

To enter a shell, execute:


Linux
~~~~~

.. code:: bash

   docker run --rm -it -v $(pwd):/sphinxneeds useblocks/sphinxneeds:latest bash


Windows (cmd)
~~~~~~~~~~~~~

.. code:: bash

   docker run --rm -it -v %cd%:/sphinxneeds useblocks/sphinxneeds:latest bash


Windows (Powershell)
~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   docker run --rm -it -v ${PWD}:/sphinxneeds useblocks/sphinxneeds:latest bash

Once inside the docker container shell, execute a ``<build-command>``