.. _need:

need/ req (or any other defined need type)
==========================================

Creates a need with specified type. The type is defined by using the correct directive, like
``.. req::`` or ``.. test::``.


.. code-block:: rst

    .. req:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login
       :collapse: false

       Our users needs to get logged in via our login forms on **/login.php**.

.. req:: User needs to login
   :id: ID123
   :status: open
   :tags: user;login
   :collapse: false

   Our users needs to get logged in via our login forms on **/login.php**.

This creates a new requirement, with a title, content, given id, a status and several tags.

All options are optional, only the title as argument must be given (if :ref:`needs_title_from_content` is not set).

.. note::

    By default the above example works also with `.. spec::`, `.. impl::`, `.. test::` and all other need types,
    which are configured via :ref:`need_types`.

Options
-------

Supported options:

* :ref:`need_id`
* :ref:`need_status`
* :ref:`need_tags`
* :ref:`need_links`
* :ref:`need_hide`
* :ref:`need_collapse`
* :ref:`need_layout`
* :ref:`need_style`
* :ref:`need_template`

.. _need_id:

id
~~
The given ID must match the regular expression of config parameter :ref:`needs_id_regex`.
If it does not match, the build stops.

If no **id** is given, a short hash value is calculated based on the title. If the title gets not changed, the
id will be stable for all upcoming documentation generations.

.. _need_status:

status
~~~~~~
A need can only have one status and its selection may be restricted by config parameter :ref:`needs_statuses`.


.. _need_tags:

tags
~~~~
**Tags** must be separated by "**;**", like tag1; tag2;tag3. Whitespaces get removed.

.. _need_links:

links
~~~~~
**links** can be used to create a link to one or several other needs, no matter what kind of type they are.
All you need is the related ID.

You can easily set links to multiple needs by using ";" as separator.

.. code-block:: rst

   .. req:: Link example Target
      :id: REQ_LINK_1

      This is the target for a link. Itself has no link set.

   .. req:: Link example Source
      :links: REQ_LINK_1

      This sets a link to id ``REQ_LINK_1``.

.. req:: Link example Target
   :id: REQ_LINK_1

   This is the target for a link. Itself has no link set.

.. req:: Link example Source
   :links: REQ_LINK_1

   This sets a link to id ``REQ_LINK_1``.


.. _need_extra_links:

extra links
+++++++++++

By using :ref:`needs_extra_links` you can use the configured link-types to set additional on other options.

.. code-block:: python

   # conf.py
   needs_extra_links = [
      {
         "option": "blocks",
         "incoming": "is blocked by",
      },
      {
         "option": "tests",
         "incoming": "is tested by",
         "copy": False,
         "color": "#00AA00"
      }
   ]

.. code-block:: rst

   .. req:: test me
      :id: test_req

      A requirement, which needs to be tested

   .. test:: test a requirement
      :id: test_001
      :tests: test_req

      Perform some tests


.. req:: test me
   :id: test_req
   :collapse: false

   A requirement, which needs to be tested

.. test:: test a requirement
   :id: test_001
   :tests: test_req
   :collapse: false

   Perform some tests


.. _need_hide:

hide
~~~~
There is an option **:hide:**, if this is set (no value is needed), the need will not be printed in
documentation. But it will show up in need filters!

.. _need_collapse:

collapse
~~~~~~~~
If set to **True**, details like status, links or tags are collapsed and viewable only after a click on the need title.

If set to **False**, details are shown directly.

If not set, the config parameter :ref:`needs_collapse_details` decides about the behavior.

Allowed values:

 * true; yes; 1
 * false; no; 0


.. code-block:: rst

   .. req:: Collapse is set to True
      :tags: collapse; example
      :collapse: True

      Only title and content are shown

   .. req:: Collapse is set to False
      :tags: collapse; example
      :collapse: False

      Title, tags, links and everything else is shown directly.

.. req:: Collapse is set to True
   :tags: collapse; example
   :collapse: True

   Only title and content are shown

.. req:: Collapse is set to False
   :tags: collapse; example
   :collapse: False

   Title, tags, links and everything else is shown directly.


.. _title_from_content:

title_from_content
~~~~~~~~~~~~~~~~~~

.. versionadded:: 0.2.3

When this flag is provided on an individual need, a title will be derived
from the first sentence of the content.  If not title and no content is provided
then the build process will fail.

The derived title will respect the :ref:`needs_max_title_length` and provide an
ellided title if needed.  By default there is no limit to the title length.

When using this setting be sure to exercise caution that special formatting
that you would not want in the title (bulleted lists, nested directives, etc.)
do not appear in the first sentence.

If a title is provided and the flag is present, then the provided title will
be used and a warning will be issued.

Example::

    .. req::
        :title_from_content:

        The first sentence will be the title.  Anything after the first
        sentence will not be part of the title.

The resulting requirement would have the title derived from the first
sentence of the requirement.

.. req::
    :title_from_content:

    The first sentence will be the title.  Anything after the first
    sentence will not be part of the title.

.. _need_layout:

layout
~~~~~~

.. versionadded:: 0.4.1

``layout`` can be used to set a specific grid and content mapping.

.. code-block:: rst

   .. req:: My layout requirement 1
      :id: LAYOUT_1
      :tags: layout_example
      :layout: clean

      Some **content** of LAYOUT_1

.. req:: My layout requirement 1
   :id: LAYOUT_1
   :tags: layout_example
   :layout: clean

   Some **content** of LAYOUT_1

.. code-block:: rst

   .. req:: My layout requirement 2
      :id: LAYOUT_2
      :tags: layout_example
      :layout: complete

      Some **content** of LAYOUT_2

.. req:: My layout requirement 2
   :id: LAYOUT_2
   :tags: layout_example
   :layout: complete

   Some **content** of LAYOUT_2

.. code-block:: rst

   .. req:: My layout requirement 3
      :id: LAYOUT_3
      :tags: layout_example
      :layout: focus

      Some **content** of LAYOUT_3

.. req:: My layout requirement 3
   :id: LAYOUT_3
   :tags: layout_example
   :layout: focus

   Some **content** of LAYOUT_3

Please take a look into :ref:`layouts` for more information.


.. _need_style:

style
~~~~~

.. versionadded:: 0.4.1

``style`` can be used to set a specific class-attribute for the need representation.

The class-attribute can then be addressed by css to specify the layout of the need.

.. req:: My styled requirement
   :id: STYLE_001
   :tags: style_example
   :style: red

.. req:: Another styled requirement
   :id: STYLE_002
   :tags: style_example
   :style: blue

.. req:: Green is my color
   :id: STYLE_003
   :tags: style_example
   :style: green

.. req:: Yellow and blue border
   :id: STYLE_004
   :style: yellow, blue_border

.. code-block:: rst

   .. req:: My styled requirement
      :id: STYLE_001
      :tags: style_example
      :style: red

   .. req:: Another styled requirement
      :id: STYLE_002
      :tags: style_example
      :style: blue

   .. req:: Green is my color
      :id: STYLE_003
      :tags: style_example
      :style: green

   .. req:: Yellow and blue border
      :id: STYLE_004
      :style: yellow, blue_border

By using :ref:`dynamic_functions` the value of ``style`` can be automatically
combined with values from other need options.

Here ``style`` is set to ``[[copy('status')]]``,
which leads to the css class ``needs_style_open`` if style is set to ``open``.

.. req:: My automatically styled requirement
   :id: STYLE_005
   :status: implemented
   :tags: style_example
   :style: [[copy("status")]]

.. req:: My automatically styled requirement
   :id: STYLE_006
   :status: open
   :tags: style_example
   :style: [[copy("status")]]

.. code-block:: rst

   .. req:: My automatically styled requirement
      :id: STYLE_005
      :status: implemented
      :tags: style_example
      :style: [[copy(status)]]

   .. req:: My automatically styled requirement
      :id: STYLE_006
      :status: open
      :tags: style_example
      :style: [[copy(status)]]

.. _need_template:

template
~~~~~~~~

.. versionadded:: 0.5.2

By setting ``template`` the content of the need gets replaced by the content of the specified template.

``Sphinx-Needs`` templates support the template language `Jinja <https://jinja.palletsprojects.com/>`_
and gives access to all need data, including the original content.

The template name must be the same as a file name in the ``Sphinx-Needs`` template folder, without the file extension.
So a file named ``my_template.need`` must be referenced like this: ``:template: my_template``.
``Sphinx-Needs`` templates must always use the file extension ``.need``.

The location of all template files is specified by :ref:`needs_template_folder`, which is by
default ``needs_templates/``.

There can be several templates in parallel, but only one can be set for a need.

**Example**

*Template:* spec_template.need

.. literalinclude:: /needs_templates/spec_template.need

*Need*

.. code-block:: rst

   .. spec:: My specification
      :status: open
      :links: FEATURE_1, FEATURE_2
      :id: TEMPL_SPEC
      :tags: example, template
      :template: spec_template

      This is my **specification** content.

*Result*

.. spec:: My specification
   :status: open
   :links: FEATURE_1, FEATURE_2
   :id: TEMPL_SPEC
   :tags: example, template
   :template: spec_template

   This is my **specification** content.

A list of available need-value names can be found in the documentation of :ref:`filter_string` or by using
the ``debug`` :ref:`layout <layouts>`.

You can automatically assign templates to specific needs by using :ref:`needs_global_options`.


Customized Options
------------------

Sphinx-Needs supports the definition and filtering of customized options for needs.

Please see :ref:`needs_extra_options` for detailed information and examples.


Removed Options
---------------

.. _need_hide_status:

hide_status
~~~~~~~~~~~
*removed: 0.5.0*

.. note::

   To remove options from output in ``Sphinx-Needs`` version >= ``0.5.0`` you must provide your own layout, which
   does not include these options. See :ref:`layouts_styles` for more information.

You can also use **:hide_status:**  to hide status information for a need.

.. _need_hide_tags:

hide_tags
~~~~~~~~~
*removed: 0.5.0*

.. note::

   To remove options from output in ``Sphinx-Needs`` version >= ``0.5.0`` you must provide your own layout, which
   does not include these options. See :ref:`layouts_styles` for more information.

Or use **:hide_tags:** to hide the tags of a need.
