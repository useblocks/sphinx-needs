Requirements, Bugs, Test cases, ... Management inside Sphinx
============================================================

This package contains the needs Sphinx extension.

It allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via configuration (for instance to support bugs or user stories).

.. toctree::
   :maxdepth: 2

   installation
   directives
   roles
   configuration
   examples
   changelog

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

You can create filterable overviews of defined needs by using the needfilter directive::

    .. needfiler::
       :status: open;in_progress
       :tags: tests; test; test_case;
       :layout: table

One more thing ...
------------------

This extensions also activates the usage of jinja statements inside your rst files.
The statements get executed before sphinx starts handling their content.

The idea and code is coming from
`Eric Holscher <http://ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/>`_.

It was integrated for dynamic error handling, if needed libraries like PlantUML are not available
(for instance on readthedocs.io).







