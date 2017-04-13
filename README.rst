*Complete, rendered documentation*: http://sphinxcontrib-needs.readthedocs.io/en/latest/

This package contains the needs Sphinx extension.

It allows the definition, linking and filtering of need-objects, which are by default:

* requirements
* specifications
* implementations
* test cases.

This list can be easily customized via configuration (for instance to support bugs or user stories).

Example
-------

For the rendered output and more documentation, please visit http://sphinxcontrib-needs.readthedocs.io/en/latest/

.. code-block:: rst

    .. req:: My first requirement
       :status: open
       :tags: requirement; test; awesome

       This is my **first** requirement!!
       .. note:: It's awesome :)

    .. spec:: Specification of a requirement
       :id: OWN_ID_123

    .. impl:: Implementation for specification
       :id: impl_01
       :links: OWN_ID_123

    .. test:: Test for XY
       :status: implemented
       :tags: test; user_interface; python27
       :links: OWN_ID_123; impl_01

       This test checks the implementation of :ref:`impl_01` for spec :ref:`OWN_ID_123` inside a
       Python 2.7 environment.

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

Installation
============

Using pip
---------
::

    pip install sphinxcontrib-needs

Using sources
-------------
::

    git clone https://github.com/useblocks/sphinxcontrib-needs
    python setup.py install

Activation
----------

Add **sphinxcontrib.needs** to your extensions::

    extensions = ["sphinxcontrib.needs",]
