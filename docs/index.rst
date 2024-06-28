:sd_hide_title:
:hide-toc:

.. role:: underline
    :class: underline

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

Outline
-------

Sphinx-Needs is an extension for the `Python <https://python.org>`_ based documentation framework `Sphinx <https://www.sphinx-doc.org>`_,
which you can simply extend by different extensions to fulfill nearly any requirement of a software development team.

Sphinx-Needs allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

You can easily customize the list above via :ref:`configuration <needs_types>`.
For instance, you can customize the need objects to support bugs, user stories or features.

.. req:: What is a need
   :id: REQ_1
   :tags: introduction


   A **need** is a generic object which can become anything you want for your Sphinx documentation:
   a requirement, a test case, a user story, a bug, an employee, a product, or anything else.

   But regardless of whatever you choose it to be and how many of them you require, we handle each **need** object the same way.

.. spec:: Content of each need
   :id: SPEC_1
   :tags: introduction, awesome, nice
   :status: open
   :links: REQ_1

   Each need contains:

   * a **title** (required)
   * an **unique id** (optional) - gets generated based on the title if not given
   * a **description** (optional) - supports rst and sphinx extensions fully
   * a **status** (optional)
   * several **tags** (optional)
   * several **links** to other needs (optional)
   * project specific options (optional) - see :ref:`needs_extra_options`
   * a **layout** (optional)
   * a **style** (optional)

.. feature:: Filtering needs
   :id: FEATURE_1
   :tags: introduction
   :links: SPEC_1

   We can easily :ref:`filter <filter>` **needs** and present them as :ref:`lists <needlist>`, :ref:`tables <needtable>`,
   :ref:`diagrams <needflow>`, and :ref:`pie charts <needpie>`.


**Table example**

.. needtable::
   :tags: introduction
   :style: table
   :columns: id, title, outgoing

**Diagram example**

.. needflow::
   :tags: introduction

.. feature:: Ex/Importing needs
   :id: FEATURE_2
   :tags: introduction
   :links: SPEC_1

   For external synchronization (e.g. with JIRA, a spreadsheet,…),
   the :ref:`needs builder <needs_builder>` can help export all created **needs** to a single *JSON* file.

   Also, there is support for importing needs from external files, which you can do by using the :ref:`needimport` directive.

   .. code-block:: bash

      make html   # HTML output
      make needs  # needs.json containing all data

.. feature:: Connect to external services
   :id: FEATURE_3
   :tags: introduction
   :links: SPEC_1

   **Sphinx-Needs** can request issues and other data from external services like :ref:`GitHub <github_service>`.

   Embed tickets, requirements and other external information from specific services
   into your documentation by using :ref:`services`.

.. feature:: Automated data handling
   :id: FEATURE_4
   :tags: introduction
   :links: SPEC_1

   To handle complex data chains between **needs**, you can use :ref:`dynamic_functions`
   to load and set changeable data automatically during the documentation generation phase.


.. feature:: Customizing everything
   :id: FEATURE_5
   :tags: introduction
   :links: SPEC_1
   :layout: complete
   :style: green

   **Sphinx-Needs** allows customizing needs-types, needs-options, colors, layouts, IDs, checks, ....

   The pages :ref:`config` and :ref:`layouts_styles` contains instructions on how to adopt **Sphinx-Needs** for your
   processes and workflows.

.. feature:: API for other extensions
   :id: FEATURE_6
   :tags: introduction
   :links: SPEC_1

   The :ref:`api` allows other Sphinx-extensions to build specific solutions around and with **Sphinx-Needs**.

   For instance, `Sphinx-Test-Reports <https://sphinx-test-reports.readthedocs.io/en/latest/>`_ create **needs** from
   test results and make them searchable and linkable to other need-types.

.. feature:: Supports PlantUML for reusable Architecture elements
   :id: FEATURE_7
   :tags: introduction
   :links: SPEC_1

   Sphinx-Needs allows to create specific objects for architecture elements, which can be reused  and recombined
   in different flows and also higher architecture elements. Based on `PlantUML <https://plantuml.com>`__.

   Take a look into the :ref:`needuml` directive to get an impression how powerful this mechanism is.


.. feature:: Developed for safe process executions
   :id: FEATURE_8
   :tags: introduction
   :links: SPEC_1

   **Sphinx-Needs** allows you to define the exact way of using and configuring **needs** objects.

   Use :ref:`needs_statuses`, :ref:`needs_tags` or :ref:`needs_warnings` to check for configurations not allowed,
   e.g. wrong status names.

   Or force the usage of specifically defined need-ids by setting :ref:`needs_id_required` and :ref:`needs_id_regex`.

   See :ref:`config` for more options to get a Sphinx documentation valid with ISO 26262, DO-178B/C or any other
   safety standard.


Example
-------

For more complex examples, please visit :ref:`examples`.

Input
~~~~~

.. code-block:: rst

   **Some data**

   .. req:: My first requirement
      :id: req_001
      :tags: main_example

      This need is a requirement, and it includes a title, an ID, a tag and this text as a description.

   .. spec:: Spec for a requirement
      :links: req_001
      :status: done
      :tags: important; main_example
      :collapse: false

      We didn't set the **ID** option here, so **Sphinx-Needs** will generate one for us.

      But we have set a **link** to our previous requirement and have set the **status** option.

      Also, we have enabled **collapse** to false to show all meta-data directly under the title.

   **Some text**

   Wohooo, we have created :need:`req_001`,
   which is linked by :need_incoming:`req_001`.

   **Some filters**

   Simple list:

   .. needlist::
     :tags: main_example

   Simple table:

   .. needtable::
     :tags: main_example
     :style: table

   A more powerful table
   (based on `DataTables <https://datatables.net/>`_):

   .. needtable::
     :tags: main_example
     :style: datatables


Result
~~~~~~

**Some data**

.. req:: My first requirement
   :id: req_001
   :tags: main_example

   This need is a requirement, and it includes a title, an ID, a tag and this text as a description.


.. spec:: Spec for a requirement
   :links: req_001
   :status: done
   :tags: important; main_example
   :collapse: false

   We didn't set the ``:id:`` option here, so **Sphinx-Needs** will generate one for us.

   But we have set a **link** to our previous requirement and have set the **status** option.

   Also, we have enabled **collapse** to false to show all meta-data directly under the title.

**Some text**

Wohooo, we have created :need:`req_001`,
which is linked by :need_incoming:`req_001`.

**Some filters**

:underline:`Simple list`:

.. needlist::
  :tags: main_example

:underline:`Simple table`:

.. needtable::
  :tags: main_example
  :style: table

:underline:`A more powerful table` (based on `DataTables <https://datatables.net/>`_):

.. needtable::
  :tags: main_example
  :style: datatables

Ecosystem
---------

In the last years, we have created additional information and extensions, which are based on or related to Sphinx-Needs:

.. grid:: 2
    :gutter: 2

    .. grid-item-card::
        :columns: 12 6 6 6
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
        :columns: 12 6 6 6
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
        :columns: 12 6 6 6
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


Other Sphinx extensions
~~~~~~~~~~~~~~~~~~~~~~~
During the use of Sphinx-Needs in popular companies’ internal projects,
we have created other Sphinx extensions to support the work of teams in the automotive industry:

.. grid:: 2
    :gutter: 2

    .. grid-item-card::
        :columns: 12 6 6 6
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
        :columns: 12 6 6 6
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

.. toctree::
   :caption: The Basics
   :maxdepth: 2
   :hidden:

   Introduction <self>
   installation
   tutorial

.. toctree::
   :caption: Reference
   :maxdepth: 2
   :hidden:

   directives/index
   roles
   configuration
   builders
   examples/index

.. toctree::
   :caption: Advanced
   :maxdepth: 2
   :hidden:

   api
   filter
   dynamic_functions
   services/index
   layout_styles
   utils

.. toctree::
   :caption: Development
   :maxdepth: 2
   :hidden:

   support
   contributing
   changelog
