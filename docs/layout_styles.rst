.. _layouts_styles:

Layouts & Styles
================

``Sphinx-Needs`` provides functions to manipulate the layout and the style of a need.

Layouts are defined by a preconfigured table grid and the data, which shall be shown inside specific grid cells.
Styles define mostly the color of a need.

Both features can be set directly during need-configuration or inside the sphinx ``conf.py`` file.

``Sphinx-Needs`` provides some preconfigured, ready-to-use standard layouts:

   * clean
   * complete
   * focus

.. _layouts:

Layouts
-------
Layouts are using a predefined :ref:`grid system <grids>` and define which data shall be shown in which grid-cells.

There can be multiple layouts using the same :ref:`grid system <grids>`, but maybe showing different data.
E.g. a layout for bugs and one for specifications.

``Sphinx-Needs`` comes with some predefined layouts.
But the user is free to create own layouts and use only them.

Most useful layout are:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 20 60

   - * Layout
     * Used grid
     * Comment
   - * clean
     * :ref:`grid_simple`
     * The standard ``Sphinx-Needs`` layout
   - * complete
     * :ref:`grid_complex`
     * Divided head, meta, footer rows. Showing really all user-added data.
   - * focus
     * :ref:`grid_content`
     * Content focused layout. Showing content only. Nothing more.

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
     * Shows **all** meta data (also internal ones) in the footer.
       Useful do see what data is available for a need and which can be used in :ref:`filter_string`.

Defining own layouts
~~~~~~~~~~~~~~~~~~~~

A full, valid layout configuration look like this::

   # Sphinx-Needs definition of the  *clean* layout
   'clean': {
        'grid': 'simple',
        'layout': {
            'head': [
                '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>>  <<collapse_button("meta", collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>>'
            ],
            'meta': [
                '<<meta_all(no_links=True)>>',
                '<<meta_links_all()>>'
            ],
        }
    },

layout_functions
++++++++++++++++

To get custom data into your layout the usage of layout function is needed.
A layout function may look like ``<<meta(arg1, arg2, kwarg=data)>>``

Available layout functions are:

* :func:`meta <sphinxcontrib.needs.layout.LayoutHandler.meta>`
* :func:`meta_all <sphinxcontrib.needs.layout.LayoutHandler.meta_all>`
* :func:`meta_links <sphinxcontrib.needs.layout.LayoutHandler.meta_links>`
* :func:`meta_links_all <sphinxcontrib.needs.layout.LayoutHandler.meta_links_all>`
* :func:`meta_id <sphinxcontrib.needs.layout.LayoutHandler.meta_id>`
* :func:`image <sphinxcontrib.needs.layout.LayoutHandler.image>`
* :func:`link <sphinxcontrib.needs.layout.LayoutHandler.link>`
* :func:`collapse_button <sphinxcontrib.needs.layout.LayoutHandler.collapse_button>`

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.meta(name, prefix=None, show_empty=False)

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.meta_id()

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.meta_all(prefix='', postfix='', exclude=None, no_links=False, defaults=True, show_empty=False)

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.meta_links(name, incoming=False)

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.meta_links_all(prefix='', postfix='')

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.image(url, height=None, width=None, align=None, no_link=False)

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.link(url, text=None, image_url=None, image_height=None, image_width=None)

.. autofunction:: sphinxcontrib.needs.layout.LayoutHandler.collapse_button(target='meta', collapsed='Show', visible='Close', initial=False)

HTML output
-----------

For **html output** the used layout and style names are added as css-class to the need table object.
Beside this also the used grid system is added::

   <table class="need needs_grid_simple needs_layout_complex needes_style_blue docutils" id="SPEC_1">

The above line contains the following css classes:

* need: Each html table, which represents a ``need`` has the **need** class
* needs_grid_simple: Used grid system of the layout
* needs_layout_complex: Used layout
* needs_style_needs_blue: Used style

Please note, that the classes added by ``Sphinx-Needs`` always contain a prefix:
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
This is the default layout used by ``Sphinx-Needs``.

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
+------+---------+
| side | head    |
|      +---------+
|      | meta    |
|      +---------+
|      | content |
|      +---------+
|      | footer  |
+------+---------+

.. _grid_simple_side_right:

simple_side_right
+++++++++++++++++
+---------+------+
| head    | side |
+---------+      |
| meta    |      |
+---------+      |
| content |      |
+---------+      |
| footer  |      |
+---------+------+

.. _grid_simple_side_left_partial:

simple_side_left_partial
++++++++++++++++++++++++
+------+------+
| side | head |
|      +------+
|      | meta |
+------+------+
| content     |
+-------------+
| footer      |
+-------------+

.. _grid_simple_side_right_partial:

simple_side_right_partial
+++++++++++++++++++++++++
+------+------+
| head | side |
+------+      |
| meta |      |
+------+------+
| content     |
+-------------+
| footer      |
+-------------+

Complex grids
~~~~~~~~~~~~~

.. _grid_complex:

complex
+++++++

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
+---------+
| content |
+---------+

.. _grid_content_footer:

content_footer
++++++++++++++
+---------+
| content |
+---------+
| footer  |
+---------+

.. _grid_content_side_left:

content_side_left
+++++++++++++++++
+------+---------+
| side | content |
+------+---------+

.. _grid_content_side_right:

content_side_right
++++++++++++++++++
+---------+------+
| content | side |
+---------+------+

.. _grid_content_footer_side_left:

content_footer_side_left
++++++++++++++++++++++++
+--------+---------+
| side   | content |
|        +---------+
|        | footer  |
+--------+---------+

.. _grid_content_footer_side_right:

content_footer_side_right
+++++++++++++++++++++++++
+---------+------+
| content | side |
+---------+      |
| footer  |      |
+---------+------+

Styles
------

Customisation
=============

The layout and structure of needs can be highly customized.

There are three ways to do this:

* Define own jinja template for a need
* Provide a css file by using :ref:`needs_css`
* Set own css on sphinx level

Need jinja template
-------------------

Please see :ref:`needs_template` on the configuration page.

.. _styles_css:

Sphinx-needs CSS option
-----------------------

A css file can be set in the **conf.py** file by setting **needs_css**.
See :ref:`needs_css` on the configuration page for more information.

Sphinx-needs provides the following css styles:

**blank.css**

.. image:: _static/need_blank.png

**modern.css**

.. image:: _static/need_modern.png

**dark.css**

.. image:: _static/need_dark.png

blank.css
~~~~~~~~~
.. literalinclude:: ../sphinxcontrib/needs/css/blank.css

modern.css
~~~~~~~~~~
.. literalinclude:: ../sphinxcontrib/needs/css/modern.css

dark.css
~~~~~~~~
.. literalinclude:: ../sphinxcontrib/needs/css/dark.css

Own CSS file on sphinx level
----------------------------

If you want to use most of the sphinx-needs internal styles but only need some specific changes for single elements, you
can provide your own CSS file by register it inside your conf.py::

    def setup(app):
        app.add_stylesheet('css/my_custom.css')  # may also be an URL

.. hint::

    Do not name it **custom.css** if you are using `Read the docs <http://readthedocs.org>`_ as
    this name is already taken.

