Requirements, Bugs, Test cases, ... Management inside Sphinx
============================================================

This package contains the needs Sphinx extension.

It allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via configuration (for instance to support bugs or user stories).

What is a need?
---------------

A need is a generic object, which can become everything you want for your sphinx documentation:
A requirement, a test case, a user story, a bug, an employee, a product or anything else.

But whatever you chose it shall be and how many of them you need, each need is handled the same way.

Each need can contain:

* a **title** (required)
* an **unique id** (optional. Gets calculated based on title if not given)
* a **description**, which supports fully rst and sphinx extensions (optional)
* a **status** (optional)
* several **tags** (optional)
* several **links** to other needs (optional)


Example
-------

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


Content
-------

.. toctree::
   :maxdepth: 2

   installation
   directives
   roles
   configuration
   examples
   changelog

One more thing ...
------------------

This extensions also activates the usage of jinja statements inside your rst files.
The statements get executed before sphinx starts handling their content.

The idea and code is coming from
`Eric Holscher <http://ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/>`_.

It was integrated for dynamic error handling, if needed libraries like PlantUML are not available
(for instance on readthedocs.io).







