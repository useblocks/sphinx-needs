This package contains the needs Sphinx extension.

It allows the definition of needs and specification and their listing.

This extension provides the following directives:

 * **need**: Define a single need
 * **needlist**: Shows a list of defined needs. Can be filtered by status and tags
 * **spec**: Define a specification and link it to several needs
 * **speclist**: Shows a list of defined specifications (incl. linked needs). Can be filters by status and tags


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

conf.py
=======

Activation
----------

Add **sphinxcontrib.needs** to your extensions::

    extensions = ["sphinxcontrib.needs",]

Options
-------

All options starts with the prefix **needs_** for this extension.

needs_include_needs
~~~~~~~~~~~~~~~~~~~
Set this option on False, if no needs should be documented inside the generated documentation.

Default: **True**::

    needs_include_needs = False

needs_include_specs
~~~~~~~~~~~~~~~~~~~
Set this option on False, if no specifications should be documented inside the generated documentation.

Default: **True**::

    needs_include_specs = False

needs_need_name
~~~~~~~~~~~~~~~
If a need is printed somewhere with its name, in front of the name the word "Need" is added. Example:

Need **User needs to login** (ID123):

This word can be replaced by any other string like "Requirement", "Req." or even "".

Default: **Need**::

    needs_need_name = "Req."

needs_spec_name
~~~~~~~~~~~~~~~
If a spec is printed somewhere with its name, in front of the name the word "Specification" is added. Example:

Specification **Using flask-security** (ID567):

This word can be replaced by any other string like "Spec.", "Implementation" or even "".

Default: **Specification**::

    needs_spec_name = "Implementation"

needs_id_prefix_needs / needs_id_prefix_specs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Each need or specification gets an unique ID during documentation generation.

In most cases you should define IDs by the option **id** inside the directive by your own.
If this is not the case, a hash is used as ID, which is based on the related title (Example: A5CJFF).

**needs_id_prefix_needs** and **needs_id_prefix_specs** allows you to set a prefix in front of this hash value. (E.g.
NeedA5CJFF)

Default needs_id_prefix_needs: **""** (Empty)

Default needs_id_prefix_specs: **""** (Empty)::

    needs_id_prefix_needs = "Ne"
    needs_id_prefix_specs = "Spec"

needs_id_length
~~~~~~~~~~~~~~~
This option defines the length of an automated generated ID (the length of the prefix does not count).

Default: **5**::

    needs_id_length = 3

needs_specs_show_needlist
~~~~~~~~~~~~~~~~~~~~~~~~~
By default a specifications shows the linked needs as a single line. Example: *needs: ID123; AB54D; MYID7*.

By using the option **:show_needlist:** you can activate a table view of needs (including need id and need title)
inside a **speclist::** directive.

The **needs_specs_show_needlist** option allows you to activate this table view by default for all specification lists.

Default: **False**::

    needs_specs_show_needlist = True


Directives
==========

need
----

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
documentation. But it will show up in need lists!

You can also use **:hide_status:** and **:hide_tags:** ti hide the related information for this need.

needlist
========

Example::

    .. needlist::
       :status: open;in_progress
       :tags: user; login
       :show_status:
       :show_tags:
       :show_filters:
       :sort_by: id

This prints a list with all found needs, which match the filters for status and tags.

For **:status:** and **:tags:** values are separated by "**;**". The logic is as followed::

    status = (open OR in_progress) AND tags = (user OR login)

If **:show_status:** / **:show_tags:** is given, the related information will be shown after the name of the need.

To show the used filters under a list, set **:show_filters:**

The showed list is unsorted as long as the parameter **:sort_by::** is not used.
Valid options for **:sort_by:** are **id** and **status**.

spec
====

Example::

    .. spec:: Use flask-security for user handling
       :id: SPEC001
       :status: done
       :tags: user;login;flask
       :needs: ID123; NEED567
       :show_needlist:

       We implement flask-security to get a secured way of handling user related functions like logins.

This creates a new admonition, with a title, content, given id, a status, several tags and linked need IDs.

All options are optional, only the title as argument must be given.

However, if no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

**tags** and **needs** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

You can use **:hide:**, to hide the complete output of the specification. But it will still show up inside lists
generated by the **speclist::** directive.

**:hide_tags:**, **:hide_status:** and **:hide_needs:** will hide the related information.

Use **:show_needlist:** if you like to get a table of linked needs, which includes their IDs and titles.

