.. role:: underline
    :class: underline

.. only:: html

   .. image:: https://img.shields.io/pypi/dm/sphinxcontrib-needs.svg
       :target: https://pypi.python.org/pypi/sphinxcontrib-needs
       :alt: Downloads
   .. image:: https://img.shields.io/pypi/l/sphinxcontrib-needs.svg
       :target: https://pypi.python.org/pypi/sphinxcontrib-needs
       :alt: License
   .. image:: https://img.shields.io/pypi/pyversions/sphinxcontrib-needs.svg
       :target: https://pypi.python.org/pypi/sphinxcontrib-needs
       :alt: Supported versions
   .. image:: https://readthedocs.org/projects/sphinxcontrib-needs/badge/?version=latest
       :target: https://readthedocs.org/projects/sphinxcontrib-needs/
   .. image:: https://github.com/useblocks/sphinxcontrib-needs/actions/workflows/ci.yaml/badge.svg
       :target: https://github.com/useblocks/sphinxcontrib-needs/actions
       :alt: GitHub CI Action status
   .. image:: https://img.shields.io/pypi/v/sphinxcontrib-needs.svg
       :target: https://pypi.python.org/pypi/sphinxcontrib-needs
       :alt: PyPI Package latest release
   .. image:: https://img.shields.io/badge/code%20style-black-000000.svg
       :target: https://github.com/psf/black
       :alt: black code style

Requirements, Bugs, Test cases, ... inside Sphinx
=================================================

.. image:: _static/needs_logo_big.png
   :alt: Sphinx-Needs Logo
   :align: center
   :class: needs-logo-big

Sphinx-Needs allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via :ref:`configuration <needs_types>`.
For instance to support bugs, user stories or features.

Sphinx-Needs is an extension for the Python based documentation framework `Sphinx <https://www.sphinx-doc.org>`_,
which can be easily extended by different extensions to fulfill nearly any requirement of a software development team.

.. req:: What is a need
   :id: REQ_1
   :tags: introduction

   A need is a generic object, which can become everything you want for your sphinx documentation:
   A requirement, a test case, a user story, a bug, an employee, a product or anything else.

   But whatever you chose it shall be and how many of them you need, each need is handled the same way.

.. spec:: Content of each need
   :id: SPEC_1
   :tags: introduction, awesome, nice
   :status: open
   :links: REQ_1

   Each need contains:

   * a **title** (required)
   * an **unique id** (optional. Gets calculated based on title if not given)
   * a **description**, which supports fully rst and sphinx extensions (optional)
   * a **status** (optional)
   * several **tags** (optional)
   * several **links** to other needs (optional)
   * project specific options (optional, see :ref:`needs_extra_options`)
   * a **layout** (optional)
   * a **style** (optional)

.. feature:: Filtering needs
   :id: FEATURE_1
   :tags: introduction
   :links: SPEC_1

   Needs can be :ref:`easily filtered <filter>` and presented in :ref:`lists<needlist>`, :ref:`tables <needtable>`,
   :ref:`diagrams <needflow>` and :ref:`pie charts <needpie>`.

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

   For external synchronization (e.g. with JIRA, a spreadsheet, ...)
   the builder :ref:`needs_builder` is available to export all created needs to a single json file.
   And also importing needs from external files is supported by using :ref:`needimport`.

   .. code-block:: bash

      make html   # HTML output
      make needs  # needs.json containing all data

.. feature:: Connect to external services
   :id: FEATURE_3
   :tags: introduction
   :links: SPEC_1

   ``Sphinx-Needs`` can request issues and other data from external services like :ref:`GitHub <github_service>`.

   Embed tickets, requirements and other external information from specific services
   into your documentation by using :ref:`services`.

.. feature:: Automated data handling
   :id: FEATURE_4
   :tags: introduction
   :links: SPEC_1

   For complex data chains between needs, :ref:`dynamic_functions` can be used to load and set
   changeable data automatically during documentation generation phase.

.. feature:: Customizing everything
   :id: FEATURE_5
   :tags: introduction
   :links: SPEC_1
   :layout: complete
   :style: green

   ``Sphinx-needs`` allows to customize needs-types, needs-options, colors, layouts, ids, checks, ... .

   The pages :ref:`config` and :ref:`layouts_styles` are full of possibilities to adopt ``Sphinx-needs`` for your
   own processes and workflows.

.. feature:: API for other extensions
   :id: FEATURE_6
   :tags: introduction
   :links: SPEC_1

   The :ref:`api` allows other sphinx-extension to build specific solutions around and with ``Sphinx-Needs``.

   For instance `Sphinx-Test-Reports <https://sphinx-test-reports.readthedocs.io/en/latest/>`_ creates needs from
   test results and makes them searchable and linkable to other need-types.

.. feature:: Developed for safe process executions
   :id: FEATURE_7
   :tags: introduction
   :links: SPEC_1

   ``Sphinx-needs`` allows to define the exact allowed way of using and configuring needs.

   Use :ref:`needs_statuses`, :ref:`needs_tags` or :ref:`needs_warnings` to check for not allowed configurations,
   e.g. wrong status names.

   Or force the usage of exactly defined need-ids by setting :ref:`needs_id_required` and :ref:`needs_id_regex`.

   See :ref:`config` for more options to get a sphinx documentation valid with ISO 26262, DO-178B/C or any other
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

      This is an awesome requirement and it includes a nice title,
      a given id, a tag and this text as description.

   .. spec:: Spec for a requirement
      :links: req_001
      :status: done
      :tags: important; main_example
      :collapse: false

      We haven't set an **ID** here, so sphinx-needs
      will generated one for us.

      But we have **set a link** to our first requirement and
      also a *status* is given.

      We also have set **collapse** to false, so that all
      meta-data is shown directly under the title.

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

   This is an awesome requirement and it includes a nice title,
   a given id, a tag and this text as description.

.. spec:: Spec for a requirement
   :links: req_001
   :status: done
   :tags: important; main_example
   :collapse: false

   We haven't set an **ID** here, so sphinxcontrib-needs
   will generated one for us.

   But we have **set a link** to our first requirement and
   also a *status* is given.

   We also have set **collapse** to false, so that all meta-data is shown directly under the title.

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
In the last years additional information and extensions have been created, which are based or related to Sphinx-Needs:

.. grid:: 2
    :gutter: 2

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinx-needs.com
        :img-top: /_static/sphinx-needs-card.png
        :class-card: border

        Sphinx-Needs.com
        ^^^^^^^^^^^^^^^^
        Webpage to present most important Sphinx-Needs functions and related extensions.

        Good entrypoint to understand the benefits and to get an idea about the complete ecosystem of Sphinx-Needs.
        +++

        .. button-link:: https://sphinx-needs.com
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`globe;1em;sd-text-primary` Sphinx-Needs.com

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinxcontrib-needs.readthedocs.io/en/latest/
        :img-top: /_static/sphinx-needs-card.png
        :class-card: border

        Sphinx-Needs
        ^^^^^^^^^^^^
        Base extension, which provides all of its functionality under the MIT license for free.

        Create, update, link, filter and present need objects like Requirements, Specifications, Bugs and much more.
        +++

        .. button-link:: https://sphinxcontrib-needs.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: http://useblocks.com/sphinx-needs-enterprise/
        :img-top: /_static/sphinx-needs-enterprise-card.png
        :class-card: border

        Sphinx-Needs Enterprise
        ^^^^^^^^^^^^^^^^^^^^^^^
        Synchronizes Sphinx-Needs data with external, company internal systems like CodeBeamer, Jira or Azure Boards.

        Provides scripts to baseline data and make CI usage easier.
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
        :img-top: /_static/sphinx-needs-card.png
        :class-card: border

        Sphinx-Test-Reports
        ^^^^^^^^^^^^^^^^^^^
        Extension to import test results from xml files as need objects.

        Created need objects can be filtered and e.g. linked to specification objects.
        +++

        .. button-link:: https://sphinx-test-reports.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs


Other Sphinx extensions
~~~~~~~~~~~~~~~~~~~~~~~
During the work with Sphinx-Needs in bigger, company internal projects, other Sphinx extensions have been created
to support the work in teams of the automotive industry:

.. grid:: 2
    :gutter: 2

    .. grid-item-card::
        :columns: 12 6 6 6
        :link: https://sphinx-collections.readthedocs.io/en/latest/
        :img-top: /_static/sphinx_collections_logo.png
        :class-card: border

        Sphinx Collections
        ^^^^^^^^^^^^^^^^^^
        Extension to collect or generate files from different sources and include them into the Sphinx source folder.

        Sources like git repositories, jinja based files or symlinks are supported.
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
        :img-top: /_static/sphinx_bazel_logo.png
        :class-card: border

        Sphinx Bazel
        ^^^^^^^^^^^^
        Provides a Bazel domain in Sphinx documentations and allows the automated import of Bazel files and their
        documentation.
        +++

        .. button-link:: https://sphinx-bazel.readthedocs.io/en/latest/
            :color: primary
            :outline:
            :align: center
            :expand:

            :octicon:`book;1em;sd-text-primary` Technical Docs


One more thing ...
------------------

The sphinx-needs logo was designed by `j4p4n <https://openclipart.org/detail/281179/engineers>`_.

.. toctree::
   :maxdepth: 2
   :hidden:

   installation
   directives/index
   roles
   configuration
   builders
   api

.. toctree::
   :maxdepth: 2
   :hidden:

   filter
   dynamic_functions
   services/index
   layout_styles
   examples/index
   performance/index

.. toctree::
   :maxdepth: 2
   :hidden:

   support
   contributing
   changelog





