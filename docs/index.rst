Requirements, Bugs, Test cases, ... inside Sphinx
=================================================

.. image:: _static/needs_logo_big.png

Sphinx-Needs allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via :ref:`configuration <need_types>` (for instance to support bugs or user stories).

What is a need?
---------------

A need is a generic object, which can become everything you want for your sphinx documentation:
A requirement, a test case, a user story, a bug, an employee, a product or anything else.

But whatever you chose it shall be and how many of them you need, each need is handled the same way.

Each need contains:

* a **title** (required)
* an **unique id** (optional. Gets calculated based on title if not given)
* a **description**, which supports fully rst and sphinx extensions (optional)
* a **status** (optional)
* several **tags** (optional)
* several **links** to other needs (optional)

Needs can be :ref:`easily filtered <needfilter>` and presented in lists, tables and diagrams.

For external synchronization (e.g. with JIRA, a spreadsheet, ...)
the builder :ref:`needs_builder` is available to export all created needs to a single json file.
And also importing needs from external files is supported by using :ref:`needimport`.

Example
-------

For more complex examples, please visit :ref:`examples`.

Input
~~~~~

.. code-block:: rst

   **Some data**

   .. req:: My first requirement
      :id: req_001
      :tags: example

      This is an awesome requirement and it includes a nice title,
      a given id, a tag and this text as description.

   .. spec:: Spec for a requirement
      :links: req_001
      :status: done
      :tags: important; example

      We haven't set an **ID** here, so sphinxcontrib-needs
      will generated one for us.

      But we have **set a link** to our first requirement and
      also a *status* is given.

   **Some text**

   Wohooo, we have created :need:`req_001`,
   which is linked by :need_incoming:`req_001`.

   **A filter**

   .. needfilter::
      :tags: example
      :layout: table

Result
~~~~~~

**Some data**

.. req:: My first requirement
   :id: req_001
   :tags: example

   This is an awesome requirement and it includes a nice title,
   a given id, a tag and this text as description.

.. spec:: Spec for a requirement
   :links: req_001
   :status: done
   :tags: important; example

   We haven't set an **ID** here, so sphinxcontrib-needs
   will generated one for us.

   But we have **set a link** to our first requirement and
   also a *status* is given.

**Some text**

Wohooo, we have created :need:`req_001`,
which is linked by :need_incoming:`req_001`.

**A filter**

.. needfilter::
  :tags: example
  :show_filters:
  :layout: table

Motivation
----------

This sphinx extension is based on the needs of a software development team inside
a german automotive company.

The project team was searching for a small and practical way of managing requirements and more to
fulfill the parameters of the `ISO 26262 <https://en.wikipedia.org/wiki/ISO_26262>`_
standard for safety critical software.

One more thing ...
------------------

The sphinx-needs logo was designed by `j4p4n <https://openclipart.org/detail/281179/engineers>`_.

Content
-------

.. toctree::
   :maxdepth: 2

   installation
   directives
   roles
   configuration
   builders
   styles
   examples
   changelog
   license
   contributors





