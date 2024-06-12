:sd_hide_title:
:hide-toc:

Introduction
============

.. grid::
   :gutter: 2 3 3 3
   :margin: 4 4 1 2
   :class-container: architecture-bg
   :class-row: sd-w-100

   .. grid-item::
      :columns: 12 8 8 8
      :child-align: justify
      :class: sd-fs-3

      .. div:: sd-font-weight-bold
         
         Bringing Engineering-as-Code to the Sphinx framework.

      .. div:: sd-fs-5 sd-font-italic

         Combine Docs-as-Code with Application Lifecycle Management,
         to track requirements, specifications, test cases, and other engineering objects in your documentation.

      .. button-ref:: installation
         :ref-type: doc
         :outline:
         :color: primary
         :class: sd-rounded-pill sd-px-4 sd-fs-5 sd-mr-3

         Get Started

   .. grid-item::
      :columns: 12 4 4 4

      .. raw:: html
         :file: _static/flow_chart.svg

----------------

.. grid:: 1 1 2 2
   :gutter: 2

   .. grid-item-card:: :octicon:`checkbox;1.5em;sd-mr-1 fill-primary` Adaptable to your needs

      An extension for the `Python <https://python.org>`_ based `Sphinx <https://www.sphinx-doc.org>`_ documentation framework,
      enabling you to define, link, and analyse engineering objects within your documentation, specific to your project,
      such as features, requirements, specifications, test cases, ...

   .. grid-item-card:: :octicon:`shield-check;1.5em;sd-mr-1 fill-primary` Developed for safety

      Allows you to define the exact way of using and configuring need objects,
      to create documentation valid with `ISO 26262 <https://en.wikipedia.org/wiki/ISO_26262>`__,
      `DO-178B/C <https://en.wikipedia.org/wiki/DO-178C>`__ or any other safety standard.

   .. grid-item-card:: :octicon:`gear;1.5em;sd-mr-1 fill-primary` Highly customizable

      Extensive :ref:`configuration options <config>` allow you to adapt the extension to your specific needs,
      and the :ref:`built-in API <api>` allows other extensions to extend sphinx-needs for specific solutions.

   .. grid-item-card:: :octicon:`sync;1.5em;sd-mr-1 fill-primary` Integration with external sources

      Import and export mechanisms facilitate external synchronization with other tools,
      such as `JIRA <https://en.wikipedia.org/wiki/Jira_(software)>`__, :ref:`GitHub <github_service>`, or spreadsheets,
      allowing for embedding tickets, requirements and other information into your documentation.

   .. grid-item-card:: :octicon:`dependabot;1.5em;sd-mr-1 fill-primary` Automated data handling

      :ref:`dynamic_functions` allow you to handle complex data chains between needs,
      to load and set changeable data automatically during the documentation generation phase.

   .. grid-item-card:: :octicon:`workflow;1.5em;sd-mr-1 fill-primary` PlantUML integration

      Allows for the creation of specific objects for architecture elements, which can be reused and recombined
      in different flow diagrams and higher architecture elements, using `PlantUML <https://plantuml.com>`__.

----------------

In the last years, we have created additional information and extensions, which are based on or related to Sphinx-Needs:

.. grid:: 1 1 2 2
    :gutter: 2

    .. grid-item-card::
        :link: https://sphinx-needs.com
        :img-top: /_images/logos/sphinx-needs-logo-old.png
        :img-alt: Sphinx-Needs.com
        :class-card: border

        The website presents the essential Sphinx-Needs functions and related extensions.

        Also, it is a good entry point to understand the benefits and get an idea about the complete ecosystem of Sphinx-Needs.
        +++

        .. button-link:: https://sphinx-needs.com
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`globe;1em;sd-text-primary` Sphinx-Needs.com

    .. grid-item-card::
        :link: https://useblocks.com/sphinx-needs-enterprise/
        :img-top: /_images/logos/sphinx-needs-enterprise-card.png
        :img-alt: Sphinx-Needs Enterprise
        :class-card: border

        Synchronize Sphinx-Needs data with external, company internal systems like CodeBeamer, Jira or Azure Boards.

        Provides scripts to baseline data and makes CI usage easier.
        +++

        .. button-link:: http://useblocks.com/sphinx-needs-enterprise/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

    .. grid-item-card::
        :link: https://sphinx-test-reports.readthedocs.io/en/latest/
        :img-top: /_images/logos/sphinx-test-reports-logo.png
        :img-alt: Sphinx-Test-Reports
        :class-card: border

        Extension to import test results from XML files as **need** objects.

        Created **need** objects can be filtered and linked to specification objects.
        +++

        .. button-link:: https://sphinx-test-reports.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

    .. grid-item-card::
        :link: https://sphinx-collections.readthedocs.io/en/latest/
        :img-top: /_images/logos/sphinx_collections_logo.png
        :img-alt: Sphinx-Collections
        :class-card: border

        Extension to collect or generate files from different sources and include them in the Sphinx source folder.

        It supports sources like Git repositories, Jinja based files or symlinks.
        +++

        .. button-link:: https://sphinx-collections.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

    .. grid-item-card::
        :link: https://sphinx-bazel.readthedocs.io/en/latest/
        :img-top: /_images/logos/sphinx_bazel_logo.png
        :img-alt: Sphinx-Bazel
        :class-card: border

        Provides a Bazel domain in Sphinx documentation and allows the automated import of Bazel files and their documentation.
        +++

        .. button-link:: https://sphinx-bazel.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

----------------

Contents
--------

.. toctree::
   :caption: The Basics
   :maxdepth: 1

   Introduction <self>
   installation
   tutorial

.. toctree::
   :caption: Components
   :maxdepth: 1

   directives/index
   roles
   configuration
   builders

.. toctree::
   :caption: How-tos
   :maxdepth: 1

   filter
   dynamic_functions
   services/index
   layout_styles
   api
   utils

.. toctree::
   :caption: Development
   :maxdepth: 1

   support
   contributing
   changelog
