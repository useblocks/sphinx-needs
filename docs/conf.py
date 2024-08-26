"""sphinx-needs documentation build configuration file"""

import datetime
import os
from pathlib import Path
from typing import Any, Dict

from sphinx_needs import __version__

# -- General configuration ------------------------------------------------

# General information about the project.
project = "Sphinx-Needs"
now = datetime.datetime.now()
copyright = f"2017-{now.year}, team useblocks"
author = "team useblocks"

master_doc = "index"
language = "en"

version = release = __version__

# set theme based on environment variable or file
DOCS_THEME = os.getenv("DOCS_THEME", "alabaster")
if (_path := Path(__file__).parent.joinpath("DOCS_THEME")).is_file():
    DOCS_THEME = _path.read_text().strip()

extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.extlinks",
    "sphinxcontrib.plantuml",
    "sphinx_needs",
    "sphinx.ext.autodoc",
    "sphinx_copybutton",
    "sphinxcontrib.programoutput",
    "sphinx_design",
    "sphinx.ext.duration",
    "sphinx.ext.todo",
]
if DOCS_THEME == "sphinx_immaterial":
    extensions.append("sphinx_immaterial")

suppress_warnings = ["needs.link_outgoing"]

nitpicky = True
nitpick_ignore = [
    ("py:class", "docutils.nodes.Node"),
    ("py:class", "docutils.parsers.rst.states.RSTState"),
    ("py:class", "docutils.statemachine.StringList"),
    ("py:class", "T"),
    ("py:class", "sphinx_needs.debug.T"),
    ("py:class", "sphinx_needs.data.NeedsInfoType"),
]

rst_epilog = """

.. |br| raw:: html

   <br>

"""

extlinks = {
    "pr": ("https://github.com/useblocks/sphinx-needs/pull/%s", "PR #%s"),
    "issue": ("https://github.com/useblocks/sphinx-needs/issues/%s", "issue #%s"),
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.8", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master", None),
}

# smartquotes = False

add_module_names = False  # Used to shorten function name output
autodoc_docstring_signature = (
    True  # Used to read spec. func-defs from docstring (e.g. get rid of self)
)

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
exclude_patterns += os.getenv("SPHINX_EXCLUDE", "").split(",")

sd_custom_directives = {
    "dropdown": {
        "inherit": "dropdown",
        "options": {
            "icon": "pencil",
            "class-container": "sn-dropdown-default",
        },
    }
}

graphviz_output_format = "svg"

# -- Options for html builder ----------------------------------------------

html_static_path = ["_static"]
html_css_files = ["_css/shared.css"]
html_favicon = "./_static/sphinx-needs-logo-square-dark.svg"

html_theme = DOCS_THEME

if DOCS_THEME == "alabaster":
    # https://alabaster.readthedocs.io
    html_theme_options = {
        "logo": "sphinx-needs-logo-long-light.svg",
        "description": "",
        "github_type": "star",
        "github_user": "useblocks",
        "github_repo": "sphinx-needs",
    }
elif DOCS_THEME == "furo":
    # https://pradyunsg.me/furo
    html_css_files += ["_css/furo.css"]
    html_theme_options = {
        "sidebar_hide_name": True,
        "top_of_page_buttons": ["view", "edit"],
        "source_repository": "https://github.com/useblocks/sphinx-needs",
        "source_branch": "master",
        "source_directory": "docs/",
        "light_logo": "sphinx-needs-logo-long-light.svg",
        "dark_logo": "sphinx-needs-logo-long-dark.svg",
    }
    templates_path = ["_static/_templates/furo"]
    html_sidebars = {
        "**": [
            "sidebar/brand.html",
            "sidebar/search.html",
            "sidebar/scroll-start.html",
            "sidebar/navigation.html",
            "sidebar/ethical-ads.html",
            "sidebar/scroll-end.html",
            "side-github.html",
            "sidebar/variant-selector.html",
        ]
    }
    html_context = {"repository": "useblocks/sphinx-needs"}
elif DOCS_THEME == "pydata_sphinx_theme":
    # https://pydata-sphinx-theme.readthedocs.io
    html_css_files += ["_css/pydata_sphinx_theme.css"]
    html_theme_options = {
        "logo": {
            "image_light": "_static/sphinx-needs-logo-long-light.svg",
            "image_dark": "_static/sphinx-needs-logo-long-dark.svg",
        },
        "use_edit_page_button": True,
        "github_url": "https://github.com/useblocks/sphinx-needs",
    }
    html_context = {
        "github_user": "useblocks",
        "github_repo": "sphinx-needs",
        "github_version": "master",
        "doc_path": "docs",
    }
elif DOCS_THEME == "sphinx_rtd_theme":
    # https://sphinx-rtd-theme.readthedocs.io
    html_css_files += ["_css/sphinx_rtd_theme.css"]
    html_logo = "./_static/sphinx-needs-logo-long-dark.svg"
    html_theme_options = {
        "logo_only": True,
    }
elif DOCS_THEME == "sphinx_immaterial":
    # https://jbms.github.io/sphinx-immaterial
    html_logo = "./_static/sphinx-needs-logo-long-dark.svg"
    templates_path = ["_templates/sphinx_immaterial"]
    html_css_files += ["_css/sphinx_immaterial.css"]
    html_sidebars = {
        "**": ["about.html", "navigation.html", "searchbox.html"],
    }
    html_theme_options = {
        "font": False,
        "icon": {
            "repo": "fontawesome/brands/github",
        },
        "site_url": "https://sphinx-needs.readthedocs.io/",
        "repo_url": "https://github.com/useblocks/sphinx-needs",
        "repo_name": "Sphinx-Needs",
        "edit_uri": "blob/master/docs",
        "globaltoc_collapse": True,
        "features": [
            "navigation.sections",
            "navigation.top",
            "search.share",
        ],
        "palette": [
            {
                "media": "(prefers-color-scheme: light)",
                "scheme": "default",
                "primary": "blue",
                "accent": "light-blue",
                "toggle": {
                    "icon": "material/weather-night",
                    "name": "Switch to dark mode",
                },
            },
            {
                "media": "(prefers-color-scheme: dark)",
                "scheme": "slate",
                "primary": "blue",
                "accent": "yellow",
                "toggle": {
                    "icon": "material/weather-sunny",
                    "name": "Switch to light mode",
                },
            },
        ],
        "toc_title_is_page_title": True,
    }

# -- Options for htmlhelp builder ------------------------------------------
# Output file base name for HTML help builder.
htmlhelp_basename = "needstestdocsdoc"

# -- Options for latex builder -------------------------------------------
# Grouping the document tree into LaTeX files. List of tuples (source start file, target name, title, author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "needstestdocs.tex",
        "needs test docs Documentation",
        "team useblocks",
        "manual",
    ),
]
latex_elements: Dict[str, Any] = {
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

# -- Options for man builder ---------------------------------------
# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (master_doc, "needstestdocs", "needs test docs Documentation", [author], 1)
]

# -- Options for texinfo builder -------------------------------------------
# Grouping the document tree into Texinfo files. List of tuples (source start file, target name, title, author, dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "needstestdocs",
        "needs test docs Documentation",
        author,
        "needstestdocs",
        "One line description of project.",
        "Miscellaneous",
    ),
]

# -- Options for lincheck builder ---------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html?highlight=linkcheck#options-for-the-linkcheck-builder

linkcheck_ignore = [
    r"http://localhost:\d+",
    r"http://127.0.0.1:\d+",
    r"../.*",
    r"https?://useblocks.com/sphinx-needs/bench/index.html",
]

linkcheck_request_headers = {
    "*": {
        "User-Agent": "Mozilla/5.0",
    }
}

linkcheck_workers = 5

# -- Options for PlantUML extension ---------------------------------------

local_plantuml_path = os.path.join(
    os.path.dirname(__file__), "utils", "plantuml-1.2022.14.jar"
)
plantuml = f"java -Djava.awt.headless=true -jar {local_plantuml_path}"

# plantuml_output_format = 'png'
plantuml_output_format = "svg_img"

# -- Options for Needs extension ---------------------------------------

needs_debug_measurement = False

needs_types = [
    # Architecture types
    {
        "directive": "int",
        "title": "Interface",
        "content": "plantuml",
        "prefix": "I_",
        "color": "#BFD8D2",
        "style": "card",
    },
    {
        "directive": "comp",
        "title": "Component",
        "content": "plantuml",
        "prefix": "C_",
        "color": "#BFD8D2",
        "style": "card",
    },
    {
        "directive": "sys",
        "title": "System",
        "content": "plantuml",
        "prefix": "S_",
        "color": "#BFD8D2",
        "style": "card",
    },
    # Normal types
    {
        "directive": "req",
        "title": "Requirement",
        "prefix": "R_",
        "color": "#BFD8D2",
        "style": "node",
    },
    {
        "directive": "spec",
        "title": "Specification",
        "prefix": "S_",
        "color": "#FEDCD2",
        "style": "node",
    },
    {
        "directive": "impl",
        "title": "Implementation",
        "prefix": "I_",
        "color": "#DF744A",
        "style": "node",
    },
    {
        "directive": "test",
        "title": "Test Case",
        "prefix": "T_",
        "color": "#DCB239",
        "style": "node",
    },
    {
        "directive": "feature",
        "title": "Feature",
        "prefix": "F_",
        "color": "#FFCC00",
        "style": "node",
    },
    {
        "directive": "user",
        "title": "User",
        "prefix": "U_",
        "color": "#777777",
        "style": "node",
    },
    {
        "directive": "action",
        "title": "Action",
        "prefix": "A_",
        "color": "#FFCC00",
        "style": "node",
    },
    {
        "directive": "milestone",
        "title": "Milestone",
        "prefix": "M_",
        "color": "#FF3333",
        "style": "node",
    },
    # for tutorial
    {
        "directive": "tutorial-project",
        "title": "Project",
        "prefix": "P_",
        "color": "#BFD8D2",
        "style": "rectangle",
    },
    {
        "directive": "tutorial-req",
        "title": "Requirement",
        "prefix": "R_",
        "color": "#BFD8D2",
        "style": "rectangle",
    },
    {
        "directive": "tutorial-spec",
        "title": "Specification",
        "prefix": "S_",
        "color": "#FEDCD2",
        "style": "rectangle",
    },
    {
        "directive": "tutorial-test",
        "title": "Test Case",
        "prefix": "T_",
        "color": "#f9e79f",
        "style": "rectangle",
    },
]

needs_extra_links = [
    {
        "option": "blocks",
        "incoming": "is blocked by",
        "outgoing": "blocks",
        "copy": True,
        "style": "#AA0000",
        "style_part": "dotted,#AA0000",
        "style_start": "-",
        "style_end": "-o",
        "allow_dead_links": True,
    },
    {
        "option": "tests",
        "incoming": "is tested by",
        "outgoing": "tests",
        "copy": True,
        "style": "#00AA00",
        "style_part": "dotted,#00AA00",
    },
    {
        "option": "checks",
        "incoming": "is checked by",
        "outgoing": "checks",
        "copy": False,
        "style": "#00AA00",
        "style_part": "dotted,#00AA00",
    },
    {
        "option": "triggers",
        "incoming": "triggered by",
        "outgoing": "triggers",
        "copy": False,
        "style": "#00AA00",
        "style_part": "solid,#777777",
        "allow_dead_links": True,
    },
    {
        "option": "starts_with",
        "incoming": "triggers directly",
        "outgoing": "starts with",
        "copy": False,
        "style": "#00AA00",
        "style_part": "solid,#777777",
    },
    {
        "option": "starts_after",
        "incoming": "triggers at end",
        "outgoing": "starts after",
        "copy": False,
        "style": "#00AA00",
        "style_part": "solid,#777777",
    },
    {
        "option": "ends_with",
        "incoming": "triggers to end with",
        "outgoing": "ends with",
        "copy": False,
        "style": "#00AA00",
        "style_part": "solid,#777777",
    },
    # for tutorial
    {
        "option": "tutorial_required_by",
        "incoming": "requires",
        "outgoing": "required by",
        "style": "#00AA00",
    },
    {
        "option": "tutorial_specifies",
        "incoming": "specified by",
        "outgoing": "specifies",
    },
    {
        "option": "tutorial_tests",
        "incoming": "tested by",
        "outgoing": "tests",
    },
]

needs_variant_options = ["status"]

needs_flow_configs = {
    "my_config": """
       skinparam monochrome true
       skinparam componentStyle uml2
   """,
    "another_config": """
       skinparam class {
           BackgroundColor PaleGreen
           ArrowColor SeaGreen
           BorderColor SpringGreen
       }
   """,
    "tutorial": """
    left to right direction
    skinparam backgroundcolor transparent
    skinparam Arrow {
      Color #57ACDC
      FontColor #808080
      FontStyle Bold
    }
    skinparam rectangleBorderThickness 2
   """,
}

needs_graphviz_styles = {
    "tutorial": {
        "graph": {
            "rankdir": "LR",
            "bgcolor": "transparent",
        },
        "node": {
            "fontname": "sans-serif",
            "fontsize": 12,
            "penwidth": 2,
            "margin": "0.11,0.11",
            "style": "rounded",
        },
        "edge": {
            "color": "#57ACDC",
            "fontsize": 10,
            "fontcolor": "#808080",
        },
    }
}

needs_show_link_type = False
needs_show_link_title = False
needs_title_optional = True
needs_max_title_length = 75

needs_id_regex = "^[A-Za-z0-9_]*"
needs_id_required = False
# needs_css = "dark.css"

needs_table_style = "datatables"
needs_table_columns = "ID;TITLE;STATUS;OUTGOING"

needs_extra_options = [
    "my_extra_option",
    "another_option",
    "author",
    "comment",
    "amount",
    "hours",
    "image",
    "config",
    "github",
    "value",
    "unit",
]

_names = [t["directive"] for t in needs_types] + ["issue", "pr", "commit"]
needs_warnings = {
    "type_check": f"type not in {_names}",
    # 'valid_status': 'status not in ["open", "in progress", "closed", "done", "implemented"] and status is not None'
}

needs_default_layout = "clean"
needs_default_style = None

needs_layouts = {
    "example": {
        "grid": "simple_side_right_partial",
        "layout": {
            "head": ['**<<meta("title")>>** for *<<meta("author")>>*'],
            "meta": [
                '**status**: <<meta("status")>>',
                '**author**: <<meta("author")>>',
            ],
            "side": ['<<image("_images/{{author}}.png", align="center")>>'],
        },
    },
    "permalink_example": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>> <<permalink()>> <<collapse_button("meta", '
                'collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>> '
            ],
            "meta": ["<<meta_all(no_links=True)>>", "<<meta_links_all()>>"],
        },
    },
    "detail_view": {
        "grid": "simple",
        "layout": {
            "head": [
                '<<meta("type_name")>>: **<<meta("title")>>** <<meta_id()>> <<permalink()>> <<collapse_button("meta", '
                'collapsed="icon:arrow-down-circle", visible="icon:arrow-right-circle", initial=False)>> '
                '<<sidebar("")>>'
            ],
            "meta": ["<<meta_all(no_links=True)>>", "<<meta_links_all()>>"],
        },
    },
}

needs_service_all_data = True

needs_services = {}

needs_string_links = {
    "config_link": {
        "regex": r"^(?P<value>\w+)$",
        "link_url": 'https://sphinxcontrib-needs.readthedocs.io/en/latest/configuration.html#{{value | replace("_", "-")}}',
        "link_name": 'Sphinx-Needs docs for {{value | replace("_", "-") }}',
        "options": ["config"],
    },
    "github_link": {
        "regex": r"^(?P<value>\w+)$",
        "link_url": "https://github.com/useblocks/sphinxcontrib-needs/issues/{{value}}",
        "link_name": "GitHub #{{value}}",
        "options": ["github"],
    },
}


def custom_defined_func():
    return "List of contributors:"


needs_render_context = {
    "custom_data_1": "Project_X",
    "custom_data_2": custom_defined_func(),
    "custom_data_3": True,
    "custom_data_4": [("Daniel", 811982), ("Marco", 234232)],
}

# needs_external_needs = [
#     {
#         "base_url": "https://sphinxcontrib-needs.readthedocs.io/en/latest",
#         "json_path": "examples/needs.json",
#         "id_prefix": "EXT_",
#         "css_class": "external_link",
#     },
# ]

# build needs.json to make permalinks work
needs_build_json = True

# build needs_json for every needs-id to make detail panel
needs_build_json_per_id = False

# contains different constraints
needs_constraints = {
    "critical": {
        "check_0": "'critical' in tags",
        "check_1": "'SECURITY_REQ' in links",
        "severity": "CRITICAL",
    },
    "security": {"check_0": "'security' in tags", "severity": "HIGH"},
    "team": {"check_0": 'author == "Bob"', "severity": "LOW"},
}

# defines what to do if a constraint is not met
needs_constraint_failed_options = {
    "CRITICAL": {"on_fail": ["warn"], "style": ["red_bar"], "force_style": True},
    "HIGH": {"on_fail": ["warn"], "style": ["orange_bar"], "force_style": True},
    "MEDIUM": {"on_fail": ["warn"], "style": ["yellow_bar"], "force_style": False},
    "LOW": {"on_fail": [], "style": ["yellow_bar"], "force_style": False},
}

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

DEFAULT_DIAGRAM_TEMPLATE = "<size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>"

# You can uncomment some of the following lines to override the default configuration for Sphinx-Needs.
# needs_diagram_template = DEFAULT_DIAGRAM_TEMPLATE

# Absolute path to the needs_report_template_file based on the conf.py directory
# needs_report_template = "/needs_templates/report_template.need"   # Use custom report template

# -- custom extensions ---------------------------------------

from docutils import nodes  # noqa: E402
from sphinx.application import Sphinx  # noqa: E402
from sphinx.directives import SphinxDirective  # noqa: E402

from sphinx_needs.api.need import add_external_need  # noqa: E402
from sphinx_needs.data import SphinxNeedsData  # noqa: E402
from sphinx_needs.needsfile import NeedsList  # noqa: E402


class NeedExampleDirective(SphinxDirective):
    """Directive to add example content to the documentation.

    It adds a container with a title, a code block, and a parsed content block.
    """

    optional_arguments = 1
    final_argument_whitespace = True
    has_content = True

    def run(self):
        count = self.env.temp_data.setdefault("needs-example-count", 0)
        count += 1
        self.env.temp_data["needs-example-count"] = count
        root = nodes.container(classes=["needs-example"])
        self.set_source_info(root)
        title = f"Example {count}"
        title_nodes, _ = (
            self.state.inline_text(f"{title}: {self.arguments[0]}", self.lineno)
            if self.arguments
            else ([nodes.Text(title)], [])
        )
        root += nodes.rubric("", "", *title_nodes)
        code = nodes.literal_block(
            "", "\n".join(self.content), language="rst", classes=["needs-example-raw"]
        )
        root += code
        parsed = nodes.container(classes=["needs-example-raw"])
        root += parsed
        self.state.nested_parse(self.content, self.content_offset, parsed)
        return [root]


def create_tutorial_needs(app: Sphinx, _env, _docnames):
    """Create a JSON to import in the tutorial.

    We do this dynamically, to avoid having to maintain the JSON file manually.
    """
    all_data = SphinxNeedsData(app.env).get_or_create_needs()
    writer = NeedsList(app.config, outdir=app.confdir, confdir=app.confdir)
    for i in range(1, 5):
        test_id = f"T_00{i}"
        # TODO really here we don't want to create the data, without actually adding it to the needs
        if test_id in all_data:
            data = all_data[test_id]
        else:
            add_external_need(
                app,
                "tutorial-test",
                id=test_id,
                title=f"Unit test {i}",
                content=f"Test case {i}",
            )
            data = all_data.pop(test_id)
        writer.add_need(version, data)
    # TODO ideally we would only write this file if it has changed (also needimport should add dependency on file)
    writer.write_json(
        needs_file="tutorial_needs.json", needs_path=str(Path(app.confdir, "_static"))
    )


def setup(app: Sphinx):
    app.add_directive("need-example", NeedExampleDirective)
    app.connect("env-before-read-docs", create_tutorial_needs, priority=600)
