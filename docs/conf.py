# -*- coding: utf-8 -*-
#
# needs test docs documentation build configuration file, created by
# sphinx-quickstart on Tue Mar 28 11:37:14 2017.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import datetime

from docutils.parsers.rst import directives

sys.path.insert(0, os.path.abspath('../sphinxcontrib'))

# -- General configuration ------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.3'
# The full version, including alpha/beta/rc tags.
release = '0.3.10'

on_rtd = os.environ.get('READTHEDOCS') == 'True'
if on_rtd:
    extensions = ['sphinxcontrib.needs', 'sphinx.ext.autodoc']
else:
    extensions = ['sphinxcontrib.plantuml', 'sphinxcontrib.needs', 'sphinx.ext.autodoc']

add_module_names = False

# NEEDS CONFIGURATION

# TITLE_TEMPLATE = """
# .. _{{id}}:
#
# {{type_name}}: **{{title}}** ({{id}})
#
#     {{content|indent(4) }}
#
#     {% if status -%}
#     **status**: {{status}}
#     {% endif %}
#
#     {% if tags -%}
#     **tags**: {{"; ".join(tags)}}
#     {% endif %}
#
#     {% if links -%}
#     **links**:
#     {% for link in links -%}
#         :ref:`{{link}} <{{link}}>` {%if loop.index < links|length -%}; {% endif -%}
#     {% endfor -%}
#     {% endif %}
# """

NOTE_TEMPLATE = """
.. _{{id}}:

.. note:: {{title}} ({{id}})

   {{content|indent(4) }}

   {% if status -%}
   **status**: {{status}}
   {% endif %}

   {% if tags -%}
   **tags**: {{"; ".join(tags)}}
   {% endif %}

   {% if links -%}
   **links**:
   {% for link in links -%}
       :ref:`{{link}} <{{link}}>` {%if loop.index < links|length -%}; {% endif -%}
   {% endfor -%}
   {% endif %}
"""

EXTRA_CONTENT_TEMPLATE_COLLAPSE = """
.. _{{id}}:

{% if hide == false -%}
.. role:: needs_tag
.. role:: needs_status
.. role:: needs_type
.. role:: needs_id
.. role:: needs_title

.. rst-class:: need
.. rst-class:: need_{{type_name}}

.. container:: need

    .. container:: toggle

        .. container:: header

            :needs_type:`{{type_name}}`: {% if title %}:needs_title:`{{title}}`{% endif %} :needs_id:`{{id}}`

{% if status and  status|upper != "NONE" and not hide_status %}        | status: :needs_status:`{{status}}`{% endif %}
{% if tags and not hide_tags %}        | tags: :needs_tag:`{{tags|join("` :needs_tag:`")}}`{% endif %}
{% if my_extra_option != "" %}        | my_extra_option: {{ my_extra_option }}{% endif %}
{% if another_option != "" %}        | another_option: {{ another_option }}{% endif %}
        | links incoming: :need_incoming:`{{id}}`
        | links outgoing: :need_outgoing:`{{id}}`

    {{content|indent(4) }}

{% endif -%}
"""

DEFAULT_DIAGRAM_TEMPLATE = \
    "<size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>"

# To not use the default configuration for sphinx needs, uncomment some of the following lines.

# needs_template = TITLE_TEMPLATE
# needs_diagram_template = DEFAULT_DIAGRAM_TEMPLATE

needs_types = [dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
               dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
               dict(directive="impl", title="Implementation", prefix="I_", color="#DF744A", style="node"),
               dict(directive="test", title="Test Case", prefix="T_", color="#DCB239", style="node"),
               ]

needs_extra_links = [
    {
        "name": "blocks",
        "incoming": "is blocked by",
        "outgoing": "blocks",
        "copy": True,
        "color": "#AA0000"
    },
    {
        "name": "tests",
        "incoming": "is tested by",
        "outgoing": "tests",
        "copy": True,
        "color": "#00AA00"
    }]

needs_show_link_type = False
needs_show_link_title = False
needs_title_optional = True
needs_max_title_length = 75

needs_id_regex = "^[A-Za-z0-9_]"

# needs_css = "dark.css"

cwd = os.getcwd()
plantuml = 'java -jar %s' % os.path.join(cwd, "utils/plantuml_beta.jar")

# If we are running on windows, we need to manipulate the path,
# otherwise plantuml will have problems.
if os.name == "nt":
    plantuml = plantuml.replace("/", "\\")
    plantuml = plantuml.replace("\\", "\\\\")

plantuml_output_format = 'png'

needs_collapse_details = True
needs_table_style = "datatables"
needs_table_columns = "ID;TITLE;STATUS;OUTGOING"


needs_template_collapse = EXTRA_CONTENT_TEMPLATE_COLLAPSE
needs_extra_options = {
         "my_extra_option": directives.unchanged,
         "another_option": directives.unchanged,
         "author": directives.unchanged,
         "comment": directives.unchanged,
         "amount": directives.unchanged,
         "hours": directives.unchanged,
         }

needs_title_from_content = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = 'Sphinx-Needs'
now = datetime.datetime.now()
copyright = '2017-{year}, <a href="http://useblocks.com">team useblocks</a>'.format(year=now.year)
author = 'team useblocks'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# html_logo = "_static/needs_logo.png"
# html_sidebars = {'**': ['about.html', 'navigation.html', 'sourcelink.html', 'searchbox.html'], }
html_sidebars = {'**': ['about.html', 'navigation.html'], }

html_theme_options = {
    'logo': 'needs_logo.png',
    'logo_name': True,
    # 'description': "an extension for sphinx",
    'logo_text_align': "center",
    'github_user': 'useblocks',
    'github_repo': 'sphinxcontrib-needs',
    'github_banner': True,
    'github_button': False,
    'fixed_sidebar': True,
    'extra_nav_links': {'needs@PyPi': "https://pypi.python.org/pypi/sphinxcontrib-needs/",
                        'needs@github': "https://github.com/useblocks/sphinxcontrib-needs",
                        'needs@travis': "https://travis-ci.org/useblocks/sphinxcontrib-needs"}
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = 'needstestdocsdoc'

# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',

    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (master_doc, 'needstestdocs.tex', 'needs test docs Documentation',
     'team useblocks', 'manual'),
]

# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, 'needstestdocs', 'needs test docs Documentation',
     [author], 1)
]

# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (master_doc, 'needstestdocs', 'needs test docs Documentation',
     author, 'needstestdocs', 'One line description of project.',
     'Miscellaneous'),
]


def rstjinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # Make sure we're outputting HTML
    if app.builder.format != 'html':
        return
    src = source[0]
    rendered = app.builder.templates.render_string(
        src, app.config.html_context
    )
    source[0] = rendered


def setup(app):
    app.connect("source-read", rstjinja)
