This package contains the needs Sphinx extension.

It allows the definition of needs/requirements and the listing of defined needs in lists .

This extension provides the following directives:

 * *need*: Define a single need
 * *needlist*: Shows a list of defined needs. Can be filtered by status and tags


need
====

Example::

    .. need:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login

       Our users needs to get logged in via our login forms on **/login.php**.

This creates a new admonition, with a title, content, given id, a status and several tags.

All options are optional, only the title as argument must be given.

However, if no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

**Tags** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

There is an additional option **:hide:**, if this is set (no value is needed), the need will not be printed in
documentation.
But it will show up in need lists!

needlist
========

Example::

    .. needlist::
       :status: open;in_progress
       :tags: user; login
       :show_status:
       :show_tags:
       :show_filters:

This prints a list with all found needs, which match the filters for status and tags.

For **:status:** and **:tags:** values are separated by "**;**". The logic is as followed::

    status = (open OR in_progress) AND tags = (user OR login)

If **:show_status:** / **:show_tags:** is given, the related information will be shown after the name of the need.

To show the used filter under a list, set **:show_filters:**

conf.py
=======

Installation
------------

Using pip
~~~~~~~~~
::

    pip install sphinxcontrib-needs

Using sources
~~~~~~~~~~~~~
::

    git clone https://github.com/useblocks/sphinxcontrib-needs
    python setup.py install

Activation
----------

Add **sphinxcontrib.needs** to your extensions::

    extensions = ["sphinxcontrib.needs",]

Options
-------

need_include_needs
~~~~~~~~~~~~~~~~~~

Set this option on False, if no needs should be documented inside the generated documentation::

    need_include_needs = False

need_name
~~~~~~~~~

If a need is printed somewhere with its name, in front of the name the word "need" is added. Example:

Need **User needs to login** (ID123):

This word can be replaced by any other string like "Requirement", "Req." or even ""::

    need_name = "Req."

Missing functions
=================

* references to needs, like :ref:need-ID123
* need_updates, to update tags and status of a need on any other page

