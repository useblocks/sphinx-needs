.. _layouts_styles:

Layouts & Styles
================

**Sphinx-Needs** provides functions to manipulate the layout and the style of a need.

Layouts are defined by a preconfigured table grid and the data, which shall be shown inside specific grid cells.
Styles define mostly the color of a need.

Both features can be set directly during need-configuration or inside the sphinx **conf.py** file.

**Sphinx-Needs** provides some preconfigured, ready-to-use standard layouts:

   * clean
   * complete
   * focus

.. _layouts:

Layouts
-------
Layouts are using a predefined :ref:`grid system <grids>` and define which data shall be shown in which grid-cells.

There can be multiple layouts using the same :ref:`grid system <grids>`, but maybe showing different data.
E.g. a layout for bugs and one for specifications.

**Sphinx-Needs** comes with some predefined layouts.
But the user is free to create own layouts and use only them.

Most useful layouts are:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 20 60

   - * Layout
     * Used grid
     * Comment
   - * clean
     * :ref:`grid_simple`
     * The standard **Sphinx-Needs** layout
   - * complete
     * :ref:`grid_complex`
     * Divided head, meta, footer rows. Showing really all user-added data.
   - * focus
     * :ref:`grid_content`
     * Content focused layout. Showing content only. Nothing more.

**Examples**

.. req:: CLEAN layout
   :id: EX_CLEAN
   :status: open
   :tags: a, b, c, example
   :links: EX_COMPLETE, EX_FOCUS
   :layout: clean

   This is a need using **CLEAN layout**.

.. req:: COMPLETE layout
   :id: EX_COMPLETE
   :status: open
   :tags: a, b, c, example
   :links: EX_CLEAN, EX_FOCUS
   :layout: complete

   This is a need using **COMPLETE layout**.

.. req:: FOCUS layout
   :id: EX_FOCUS
   :status: open
   :tags: a, b, c, example
   :links: EX_COMPLETE, EX_CLEAN
   :layout: focus

   This is a need using **FOCUS layout**.
   The same meta is set as the two needs above.


There are also some *extensions* for the layouts above available:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 20 60

   - * Layout
     * Used grid
     * Comment
   - * clean_l
     * :ref:`grid_simple_side_left`
     * Like `clean` but with an extra side element on left side
   - * clean_r
     * :ref:`grid_simple_side_right`
     * Like `clean` but with an extra side element on right side
   - * clean_lp
     * :ref:`grid_simple_side_left_partial`
     * Like `clean` but with an extra, small side element on left side
   - * clean_rp
     * :ref:`grid_simple_side_right_partial`
     * Like `clean` but with an extra, small side element on right side
   - * focus_f
     * :ref:`grid_content_footer`
     * Adds a small footer below content with the need id.
   - * focus_l
     * :ref:`grid_content_side_left`
     * Adds a small footer to the left side of content, showing the need id.
   - * focus_r
     * :ref:`grid_content_side_right`
     * Adds a small footer to the right side of content, showing the need id.

The layouts ``clean_l``, ``clean_r``, ``clean_lp`` and ``clean_rp`` are using the value from the field ``image`` as
source for the image in the side element. This field must made available via :ref:`needs_extra_options`.
If you need another field as source, you must create your own layout.

**Examples**

.. req:: CLEAN_L layout
   :id: EX_CLEAN_L
   :status: open
   :tags: a, b, c, example
   :image: _images/needs_logo.png
   :layout: clean_l

   This is a need using **CLEAN_L layout**.

.. req:: CLEAN_R layout
   :id: EX_CLEAN_R
   :status: open
   :tags: a, b, c, example
   :image:  _images/needs_logo.png
   :layout: clean_r

   This is a need using **CLEAN_R layout**.

.. req:: CLEAN_LP layout
   :id: EX_CLEAN_LP
   :status: open
   :tags: a, b, c, example
   :image:  _images/needs_logo.png
   :layout: clean_lp

   This is a need using **CLEAN_LP layout**.

.. req:: CLEAN_RP layout
   :id: EX_CLEAN_RP
   :status: open
   :tags: a, b, c, example
   :image:  _images/needs_logo.png
   :layout: clean_rp

   This is a need using **CLEAN_RP layout**.

.. req:: FOCUS_F layout
   :id: EX_FOCUS_F
   :status: open
   :tags: a, b, c, example
   :layout: focus_f

   This is a need using **FOCUS_F layout**.

.. req:: FOCUS_L layout
   :id: EX_FOCUS_L
   :status: open
   :tags: a, b, c, example
   :layout: focus_l

   This is a need using **FOCUS_L layout**.

.. req:: FOCUS_R layout
   :id: EX_FOCUS_R
   :status: open
   :tags: a, b, c, example
   :layout: focus_r

   This is a need using **FOCUS_R layout**.


Special layouts:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 20 60

   - * Layout
     * Used grid
     * Comment
   - * debug
     * :ref:`grid_content_footer`
     * Shows **all** meta data (also internal ones).
       Useful do see what data is available for a need and which can be used in :ref:`filter_string`.

**Examples**

.. req:: DEBUG layout
   :id: EX_DEBUG
   :status: open
   :tags: a, b, c, example
   :layout: debug

   This is a need using **DEBUG layout**.

Using layouts
~~~~~~~~~~~~~
There are two ways of setting a layout for a need:

Set it globally via :ref:`needs_default_layout` in your **conf.py** file::

   # conf.py
   needs_default_layout = 'complete'

Or set it locally for each need by using :ref:`need_layout` option::

   .. req:: My requirement
      :layout: complete


.. _own_layouts:

Defining own layouts
~~~~~~~~~~~~~~~~~~~~
Own layouts can be defined by using the the config parameter :ref:`needs_layouts` in your **conf.py** file.

``needs_layouts`` must be a dictionary and each key represents a layout. A layout must define the used grid-system and
a layout-structure. Example::

    needs_layouts = {
        'my_layout': {
            'grid': 'simple',
            'layout': {
                'head': ['my custom head']
                'meta': [ 'my first meta line',
                          'my second meta line']
            }
        }
    }

The ``layout-structure`` must also be a dictionary, where each key reference an area in the used grid system.
By default these can be: `head`, `meta`, `footer` and more.
If the layout-structure is using a not supported key by the current grid-system, the entry gets ignored.
E.g. grid ``simple`` is not supporting ``footer`` area.

The values of a specific layout-structure area definition must be a list, where each entry must be a string and
represents a single line in the later need representation.
This line can contain :ref:`layout_functions`, which care about getting need-data or adding links.

.. note::

   **Sphinx-Needs** provides some default layouts. These layouts can **not** be overwritten.
   See :ref:`layout list <layouts>` for more information.

.. note::

   The ``content`` area of a grid can not be overwritten. It is always there and can't be changed or replaced.


.. _layout_line:

Layout line
+++++++++++
A layout line may look like this::

   **style**: my_<<meta('status')>>_style

This line contains:

   * a rst text, which supports common inline roles (bold, italic):
     ``**style**: _my_``
   * a layout function, which gets executed and returns a string:
     ``<<meta('status')>>``
   * another rst text:
     ``_style``

When executed, the line will result in the following for a status like ``open``:

**style**:  my_open_style

You can combine as many :ref:`layout_functions` and text elements as you want for a line.

The head-line for the default Sphinx-Needs layout ``clean`` looks like this::

   <<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>  <<collapse_button("meta", collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>>

You are free to surround a layout function with a rst role. Like ``**<<meta("title")>>**`` to get a bold printed title.

Sometimes an argument for a layout function shall be based on a given need option. In this cases the option name
can be surrounded by ``{{ .. }}``.
As example, there may be an ``author`` option in a bug-need and you want to show a picture of the author in the grid
``simple_side_right_partial``.

The line for the ``side`` area could look like::

   '<<image("_images/{{author}}.png", align="center")>>'

.. spec:: My test spec
   :author: daniel
   :id: IMAGE_EXAMPLE
   :tags: example
   :status: open
   :layout: example
   :style: yellow, blue_border

   This example shows an image based on the ``author`` option.

   The used layout takes the value from ``author`` and puts some image-path related information around it.

Here is the complete used code

.. code-block:: python

   # conf.py
   # -------

   # Make the author option valid
   needs_extra_options = ["author"]

   # Define own layout
   needs_layouts = {
       'example': {
           'grid': 'simple_side_right_partial',
           'layout': {
               'head': ['**<<meta("title")>>** for *<<meta("author")>>*'],
               'meta': ['**status**: <<meta("status")>>',
                        '**author**: <<meta("author")>>'],
               'side': ['<<image("_images/{{author}}.png", align="center")>>']
           }
       }
   }

.. code-block:: restructuredtext

   rst-code of the above need
   --------------------------

   .. spec:: My test spec
      :author: daniel
      :status: open
      :layout: example
      :tags: example
      :style: yellow, blue_border

.. _layout_functions:

Layout functions
++++++++++++++++

To get custom data into your layout the usage of layout function is needed.
A layout function may look like ``<<meta(arg1, arg2, kwarg=data)>>``

Available layout functions are:

* :func:`meta <sphinx_needs.layout.LayoutHandler.meta>`
* :func:`meta_all <sphinx_needs.layout.LayoutHandler.meta_all>`
* :func:`meta_links <sphinx_needs.layout.LayoutHandler.meta_links>`
* :func:`meta_links_all <sphinx_needs.layout.LayoutHandler.meta_links_all>`
* :func:`meta_id <sphinx_needs.layout.LayoutHandler.meta_id>`
* :func:`image <sphinx_needs.layout.LayoutHandler.image>`
* :func:`link <sphinx_needs.layout.LayoutHandler.link>`
* :func:`permalink <sphinx_needs.layout.LayoutHandler.permalink>`
* :func:`collapse_button <sphinx_needs.layout.LayoutHandler.collapse_button>`

.. autofunction:: sphinx_needs.layout.LayoutHandler.meta(name, prefix=None, show_empty=False)

.. autofunction:: sphinx_needs.layout.LayoutHandler.meta_id()

.. autofunction:: sphinx_needs.layout.LayoutHandler.meta_all(prefix='', postfix='', exclude=None, no_links=False, defaults=True, show_empty=False)

.. autofunction:: sphinx_needs.layout.LayoutHandler.meta_links(name, incoming=False)

.. autofunction:: sphinx_needs.layout.LayoutHandler.meta_links_all(prefix='', postfix='', exclude=None)

.. autofunction:: sphinx_needs.layout.LayoutHandler.image(url, height=None, width=None, align=None, no_link=False, prefix="", is_external=False, img_class="")

.. autofunction:: sphinx_needs.layout.LayoutHandler.link(url, text=None, image_url=None, image_height=None, image_width=None, prefix="", is_dynamic=False)

.. autofunction:: sphinx_needs.layout.LayoutHandler.permalink(image_url=None, image_height=None, image_width=None, text=None, prefix="")

.. autofunction:: sphinx_needs.layout.LayoutHandler.collapse_button(target='meta', collapsed='Show', visible='Close', initial=False)

.. _styles:

Styles
------
Styles handle mostly colors for background, border and co. for a need.
Their definition is done in css files, so that **Sphinx-Needs** only cares about setting the correct class in HTML
output. This also means that styles do not have any impact to the need design in PDFs and other output formats.

Default styles are:

.. list-table::

   - * **green** or **implemented**
     * Green background
   - * **red** or **open**
     * Red background
   - * **yellow** or **in_progress**
     * Yellow background
   - * **blue**
     * Blue background
   - * **discreet**
     * Background color is only a little bit lighter/darker as the page background
   - * **green_border**
     * Green border, but normal background
   - * **red_border**
     * Red border, but normal background
   - * **yellow_border**
     * Yellow border, but normal background
   - * **blue_border**
     * Blue border, but normal background
   - * **red_bar**
     * 10 % of width red on right side, rest with normal background
   - * **orange_bar**
     * 10 % of width orange on right side, rest with normal background
   - * **yellow_bar**
     * 10 % of width yellow on right side, rest with normal background
   - * **green_bar**
     * 10 % of width green on right side, rest with normal background
   - * **blue_bar**
     * 10 % of width blue on right side, rest with normal background
   - * **discreet_border**
     * Border color is only a little bit lighter/darker as the page background
   - * **clean**
     * Removes all style information. Looks like normal text. Mostly used with layout **focus**.

**Examples**

.. req:: Green background
   :id: EX_STYLE_GREEN
   :tags: example
   :style: green

.. req:: Red background
   :id: EX_STYLE_RED
   :tags: example
   :style: red

.. req:: Yellow background
   :id: EX_STYLE_YELLOW
   :tags: example
   :style: yellow

.. req:: Blue background
   :id: EX_STYLE_BLUE
   :tags: example
   :style: blue

.. req:: Discreet background
   :id: EX_STYLE_DISCREET
   :tags: example
   :style: discreet

.. req:: Clean style
   :id: EX_STYLE_CLEAN
   :tags: example
   :style: clean

.. req:: Green border
   :id: EX_STYLE_GREEN_BORDER
   :tags: example
   :style: green_border

.. req:: Red border
   :id: EX_STYLE_RED_BORDER
   :tags: example
   :style: red_border

.. req:: Yellow border
   :id: EX_STYLE_YELLOW_BORDER
   :tags: example
   :style: yellow_border

.. req:: Blue border
   :id: EX_STYLE_BLUE_BORDER
   :tags: example
   :style: blue_border

.. req:: Red bar
   :id: EX_STYLE_RED_BAR
   :tags: example
   :style: red_bar

.. req:: Orange bar
   :id: EX_STYLE_ORANGE_BAR
   :tags: example
   :style: orange_bar

.. req:: Yellow bar
   :id: EX_STYLE_YELLOW_BAR
   :tags: example
   :style: yellow_bar

.. req:: Green bar
   :id: EX_STYLE_GREEN_BAR
   :tags: example
   :style: green_bar

.. req:: Blue bar
   :id: EX_STYLE_BLUE_BAR
   :tags: example
   :style: blue_bar

.. req:: Discreet border
   :id: EX_STYLE_DISCREET_BORDER
   :tags: example
   :style: discreet_border

Different styles can also be combined by setting a comma-separated string: ``yellow, red_border``.

.. req:: Yellow background + Red border
   :id: EX_STYLE_YELLOW_RED
   :tags: example
   :style: yellow, red_border

.. req:: Discreet view
   :id: EX_STYLE_DISCREET_COMBI
   :tags: example
   :style: discreet, discreet_border

Using styles
~~~~~~~~~~~~
There are two ways of setting a style for a need:

Set it globally via :ref:`needs_default_style` in your **conf.py** file::

   # conf.py
   needs_default_style = 'red'

Or set it locally for each need by using :ref:`need_style` option::

   .. req:: My requirement
      :style: red

By setting a style to ``None``, no style is set and the normal Sphinx-Needs style is used.

Own style configuration
~~~~~~~~~~~~~~~~~~~~~~~~

If you need to customize the css definitions, there are two ways of doing it:

* Provide a css file by using :ref:`needs_css`
* Set own css on sphinx level

.. _styles_css:

Sphinx-needs CSS option
+++++++++++++++++++++++

A css file can be set in the **conf.py** file by setting **needs_css**.
See :ref:`needs_css` on the configuration page for more information.

Sphinx-needs provides the following css styles:

**blank.css**

.. image:: /_images/need_blank.png

**modern.css**

.. image:: /_images/need_modern.png

**dark.css**

.. image:: /_images/need_dark.png

.. _own_css:

Own CSS file on sphinx level
++++++++++++++++++++++++++++

If you want to use most of the sphinx-needs internal styles but only need some specific changes for single elements, you
can provide your own CSS file by register it inside your conf.py::

    html_css_files = ['css/my_custom.css']  
    
See `html_css_files <https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-html_css_files>`_ for changing priority or media type.

.. hint::

    Do not name it **custom.css** if you are using `Read the docs <http://readthedocs.org>`_ as
    this name is already taken.

HTML output
-----------

For **html output** the used layout and style names are added as css-class to the need table object.
Beside this also the used grid system is added::

   <table class="need needs_grid_simple needs_layout_complex needs_style_blue docutils" id="SPEC_1">

The above line contains the following css classes:

* need: Each html table, which represents a ``need`` has the **need** class
* needs_grid_simple: Used grid system of the layout
* needs_layout_complex: Used layout
* needs_style_needs_blue: Used style

Please note, that the classes added by **Sphinx-Needs** always contain a prefix:
``needs_grid_``, ``needs_layout_``, ``needs_style_``.
So if a user defined layout has the name ``specification_layout``, the related css class is
``needs_layout_specification_layout``

.. _grids:

Grids
-----
The following grids are available.

Simple grids
~~~~~~~~~~~~

.. _grid_simple:

simple
++++++
This is the default layout used by **Sphinx-Needs**.

.. table::
   :class: needs_grid_example

   +---------+
   | head    |
   +---------+
   | meta    |
   +---------+
   | content |
   +---------+

.. _grid_simple_footer:

simple_footer
+++++++++++++

.. table::
   :class: needs_grid_example

   +---------+
   | head    |
   +---------+
   | meta    |
   +---------+
   | content |
   +---------+
   | footer  |
   +---------+

.. _grid_simple_side_left:

simple_side_left
++++++++++++++++

.. table::
   :class: needs_grid_example

   +------+---------+
   | side | head    |
   |      +---------+
   |      | meta    |
   |      +---------+
   |      | content |
   +------+---------+


.. _grid_simple_side_right:

simple_side_right
+++++++++++++++++

.. table::
   :class: needs_grid_example


   +---------+------+
   | head    | side |
   +---------+      |
   | meta    |      |
   +---------+      |
   | content |      |
   +---------+------+


.. _grid_simple_side_left_partial:

simple_side_left_partial
++++++++++++++++++++++++

.. table::
   :class: needs_grid_example

   +------+------+
   | side | head |
   |      +------+
   |      | meta |
   +------+------+
   | content     |
   +-------------+

.. _grid_simple_side_right_partial:

simple_side_right_partial
+++++++++++++++++++++++++

.. table::
   :class: needs_grid_example

   +------+------+
   | head | side |
   +------+      |
   | meta |      |
   +------+------+
   | content     |
   +-------------+

Complex grids
~~~~~~~~~~~~~

.. _grid_complex:

complex
+++++++

.. table::
   :class: needs_grid_example

   +-------------+--------+--------------+
   | head_left   | head   | head_right   |
   +-------------+----+---+--------------+
   | meta_left        | meta_right       |
   +------------------+------------------+
   | content                             |
   +-------------+--------+--------------+
   | footer_left | footer | footer_right |
   +-------------+--------+--------------+

Content focused grids
~~~~~~~~~~~~~~~~~~~~~

.. _grid_content:

content
+++++++

.. table::
   :class: needs_grid_example

   +---------+
   | content |
   +---------+

.. _grid_content_footer:

content_footer
++++++++++++++

.. table::
   :class: needs_grid_example

   +---------+
   | content |
   +---------+
   | footer  |
   +---------+

.. _grid_content_side_left:

content_side_left
+++++++++++++++++

.. table::
   :class: needs_grid_example

   +------+---------+
   | side | content |
   +------+---------+

.. _grid_content_side_right:

content_side_right
++++++++++++++++++

.. table::
   :class: needs_grid_example

   +---------+------+
   | content | side |
   +---------+------+

.. _grid_content_footer_side_left:

content_footer_side_left
++++++++++++++++++++++++

.. table::
   :class: needs_grid_example

   +--------+---------+
   | side   | content |
   |        +---------+
   |        | footer  |
   +--------+---------+

.. _grid_content_footer_side_right:

content_footer_side_right
+++++++++++++++++++++++++

.. table::
   :class: needs_grid_example

   +---------+------+
   | content | side |
   +---------+      |
   | footer  |      |
   +---------+------+

More Examples
-------------

.. need-example::

   .. req:: A normal requirement
      :id: EX_REQ_1
      :status: open

      This is how a normal requirement looks like

.. need-example::

   .. req:: A more complex and highlighted requirement
      :id: EX_REQ_2
      :status: open
      :tags: awesome, nice, great, example
      :links: EX_REQ_1
      :layout: complete
      :style: red_border

      More columns for better data structure and a red border.

.. need-example::

   .. req:: A focused requirement
      :id: EX_REQ_3
      :tags: example
      :status: open
      :style: clean
      :layout: focus_r

      This also a requirement, but we focus on content here.
      All meta-data is hidden, except the need-id.

.. need-example::

   .. req:: A custom requirement with picture
      :author: daniel
      :id: EX_REQ_4
      :tags: example
      :status: open
      :layout: example
      :style: yellow, blue_border

      This example uses the value from **author** to reference an image.
      See :ref:`layouts_styles` for the complete explanation.

.. need-example::

   .. req:: A requirement with a permalink
      :id: EX_REQ_5
      :tags: example
      :status: open
      :layout: permalink_example

      This is like a normal requirement looks like but additionally a permalink icon is shown next to the ID.
