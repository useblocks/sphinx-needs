.. _need:

need / req (or any other defined need type)
===========================================

Creates a **need** object with a specified type.
You can define the type using the correct directive, like ``.. req::`` or ``.. test::``.

.. rubric:: **Example**

.. code-block:: rst

    .. req:: User needs to login
       :id: ID123
       :status: open
       :tags: user;login
       :collapse: false

       Our users needs to get logged in via our login forms on **/login.php**.

.. rubric:: **Output**

.. req:: User needs to login
   :id: ID123
   :status: open
   :tags: user;login
   :collapse: false

   Our users needs to get logged in via our login forms on **/login.php**.

The code example above creates a new requirement, with a title, content, given id, a status and several tags.

All the options for the requirement directive ( ``req`` ) are optional,
but you must set a title as an argument (i.e. if you do not specify :ref:`needs_title_from_content` in the conf.py file).

.. note::

    By default, the above example works also with ``.. spec::``, ``.. impl::``, ``.. test::`` and all other need types,
    which are configured via :ref:`needs_types`.

Content area
------------

rst / md
~~~~~~~~
Content of a Sphinx-Needs objects can be any kind of content which can be handled by Sphinx.
This is by default rst-based text with support for all loaded extensions.

Markdown-Support is available by using the `MyST Parser <https://myst-parser.readthedocs.io/en/latest/>`_ extension.

plantuml
~~~~~~~~
A Sphinx-Need object can also be used to store a single PlantUML based diagram.

This kind of Need object can then be used by :ref:`needuml` to generate complex diagrams.

To use this content type, set ``content`` to ``plantuml`` in the :ref:`needs_types` configuration.

Options for Need Type
---------------------

.. _need_id:

id
~~
The given ID must match the regular expression (regex) value for the :ref:`needs_id_regex` parameter in **conf.py**.
The Sphinx build stops if the ID does not match the regex value.

If you do not specify the id option, we calculate a short hash value based on the title.
If you don’t change the title, the id will work for all upcoming documentation generations.

.. _need_status:

status
~~~~~~
A need can only have one status, and the :ref:`needs_statuses` configuration parameter may restrict its selection.


.. _need_tags:

tags
~~~~
You can give multiple tags by separating each with **;** symbol, like ``tag1;tag2;tag3``. White spaces get removed.

.. _need_links:

links
~~~~~
The ``links`` option can create a link to one or several other needs, no matter the need type.
All you must specify is the ID for the need.

You can easily set links to multiple needs by using **;** as a separator.

|ex|

.. code-block:: rst

   .. req:: Link example Target
      :id: REQ_LINK_1

      This is the target for a link. Itself has no link set.

   .. req:: Link example Source
      :links: REQ_LINK_1

      This sets a link to id ``REQ_LINK_1``.

|out|

.. req:: Link example Target
   :id: REQ_LINK_1

   This is the target for a link. Itself has no link set.

.. req:: Link example Source
   :links: REQ_LINK_1

   This sets a link to id ``REQ_LINK_1``.


.. _need_extra_links:

extra links
+++++++++++

By using :ref:`needs_extra_links <needs_extra_links>`, you can use the configured link-types to set additional **need** options.

|ex|

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

|out|

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
There is a **:hide:** option. If this is set (no value is needed), the need will not be printed in the
documentation. But you can use it with **need filters**.

.. _need_collapse:

collapse
~~~~~~~~
If set to **True**, the details section containing status, links or tags is not visible.
You can view the details by clicking on the forward arrow symbol near the need title.

If set to **False**, the need shows the details section.

Allowed values:

 * true; yes; 1
 * false; no; 0

Default: False

|ex|

.. code-block:: rst

   .. req:: Collapse is set to True
      :tags: collapse; example
      :collapse: True

      Only title and content are shown

   .. req:: Collapse is set to False
      :tags: collapse; example
      :collapse: False

      Title, tags, links and everything else is shown directly.

|out|

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

When this flag is provided on a need, a title will be derived
from the first sentence of the content.  If the title or content is not provided
then the build process will fail.

The derived title will respect the :ref:`needs_max_title_length` and provide an
elided title if needed.  By default there is no limit to the title length.

.. note::

   When using this setting ensure that the first sentence does not contain
   any special formatting you would not want in the title (bulleted lists, nested directives, etc.)

If a title is provided and the flag is present, then the provided title will
be used and a warning will be issued.

|ex|

.. code-block:: rst

    .. req::
       :title_from_content:

       The first sentence will be the title.  Anything after the first
       sentence will not be part of the title.

|out|

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

|ex|

.. code-block:: rst

   .. req:: My layout requirement 1
      :id: LAYOUT_1
      :tags: layout_example
      :layout: clean

      Some **content** of LAYOUT_1

|out|

.. req:: My layout requirement 1
   :id: LAYOUT_1
   :tags: layout_example
   :layout: clean

   Some **content** of LAYOUT_1

|ex|

.. code-block:: rst

   .. req:: My layout requirement 2
      :id: LAYOUT_2
      :tags: layout_example
      :layout: complete

      Some **content** of LAYOUT_2

|out|

.. req:: My layout requirement 2
   :id: LAYOUT_2
   :tags: layout_example
   :layout: complete

   Some **content** of LAYOUT_2

|ex|

.. code-block:: rst

   .. req:: My layout requirement 3
      :id: LAYOUT_3
      :tags: layout_example
      :layout: focus

      Some **content** of LAYOUT_3

|out|

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

The class-attribute can then be selected with **CSS** to specify the layout of the need.

**Examples**

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

By using :ref:`dynamic_functions`, the value of ``style`` can be automatically
derived from the values of other need options.

Here ``style`` is set to ``[[copy('status')]]``,
which leads to the CSS class ``needs_style_open`` if the ``status`` option is set to ``open``.

**Examples**

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

By setting ``template``, the content of the need gets replaced by the content of the specified template.

``Sphinx-Needs`` templates support the `Jinja <https://jinja.palletsprojects.com/>`_ templating language
and give access to all need data, including the original content.

The template name must be equal to the filename in the ``Sphinx-Needs`` template folder, without the file extension.
For example, if the filename is ``my_template.need``, you can reference it like this: ``:template: my_template``.
``Sphinx-Needs`` templates must have the file extension ``.need``.

You can specify the location of all template files by configuring the :ref:`needs_template_folder`, which is by
default ``needs_templates/``, in the **conf.py** file.

You can have several templates, but can set only one for a need.

|ex|

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

|out|

.. spec:: My specification
   :status: open
   :links: FEATURE_1, FEATURE_2
   :id: TEMPL_SPEC
   :tags: example, template
   :template: spec_template

   This is my **specification** content.

You can find a list of need-value names in the documentation for :ref:`filter_string` or by using
the ``debug`` :ref:`layout <layouts>`.

You can automatically assign templates to specific needs by using :ref:`needs_global_options`.

.. _multiline_option:

Multiline options
+++++++++++++++++
In Sphinx, options support multi-line content, which you can interpret like other RST input in Sphinx-Needs templates.

But there is one important constraint: Don’t use empty lines, as we use them in defining the content end.
Instead, you can use ``__`` (two underscores) to define the content end and can use ``|`` to force line breaks.

|ex|

*Need*
::

    .. req:: A really strange example
       :id: multiline_1234
       :status:
         | First line
         | Second line
         | Followed by an empty line
         __
         A list example:
         __
         * take *this*
         * and **this**
         __
         __
         __
         3 new lines, but 1 is shown only
         __
         Included directives
         __
         .. req:: test req
            :id: abc_432
            __
            This works!
            __
            An image: wow
            __
            .. image:: /_images/needs_logo.png
               :width: 20%
         __
         .. image:: /_images/needs_logo.png
            :width: 30%
       :template: content

*Template*

.. literalinclude:: /needs_templates/content.need

|out|

.. req:: A really strange example
   :id: multiline_1234
   :status:
     | First line
     | Second line
     | Followed by an empty line
     __
     A list example:
     __
     * take *this*
     * and **this**
     __
     __
     __
     3 new lines, but 1 is shown only
     __
     Included directives
     __
     .. req:: test req
        :id: abc_432
        __
        This works!
        __
        An image: wow
        __
        .. image:: /_images/needs_logo.png
           :width: 20%
     __
     .. image:: /_images/needs_logo.png
        :width: 30%
   :template: content

.. _need_pre_template:

pre_template
~~~~~~~~~~~~

.. versionadded:: 0.5.4

Adds specific content from a template *before* a **need**.
For example, you can use it to set a section name before each **need**.

|ex|

*Template:* spec_pre_template.need

.. literalinclude:: /needs_templates/spec_pre_template.need

*Need*

.. code-block:: rst

   .. spec:: My specification
      :id: TEMPL_PRE_SPEC
      :tags: example, template
      :pre_template: spec_pre_template

      This is my **specification** content.

|out|

.. spec:: My specification
   :id: TEMPL_PRE_SPEC
   :tags: example, template
   :pre_template: spec_pre_template

   This is my **specification** content.

.. _need_post_template:

post_template
~~~~~~~~~~~~~

.. versionadded:: 0.5.4

Adds specific content from a template *after* a **need**.
You can use it to show some need-specific analytics, like dependency diagrams or table of linked needs.

|ex|

*Template:* spec_post_template.need

.. literalinclude:: /needs_templates/spec_post_template.need

*Need*

.. code-block:: rst

   .. spec:: My specification
      :id: TEMPL_POST_SPEC
      :tags: example, template
      :links: FEATURE_1, FEATURE_2
      :post_template: spec_post_template

      This is my **specification** content.

|out|

.. spec:: My specification
   :id: TEMPL_POST_SPEC
   :tags: example, template
   :links: FEATURE_1, FEATURE_2
   :post_template: spec_post_template

   This is my **specification** content.


.. _need_duration:

duration
~~~~~~~~

.. versionadded:: 0.5.5

Track the duration of a need.

The need allows any value but the :ref:`needgantt` directive uses and interprets it as days by default.


.. _need_completion:

completion
~~~~~~~~~~

.. versionadded:: 0.5.5

Track the completion of a need.

The need allows any value but the :ref:`needgantt` directive uses and interprets it as percentage by default.


Customized Options
------------------

Sphinx-Needs supports the definition and filtering of customized options for needs.

You can read :ref:`needs_extra_options` for detailed information and examples.


Removed Options
---------------

.. note::

    To remove options from the ``Sphinx-Needs`` output in ``versions >= 0.5.0``, you must provide your own layout,
    which does not include these options. See :ref:`layouts_styles` for more information.

.. _need_hide_status:

hide_status
~~~~~~~~~~~
*removed: 0.5.0*

Hide the status information of a need.

.. _need_hide_tags:

hide_tags
~~~~~~~~~
*removed: 0.5.0*

Hide the tags of a need.
