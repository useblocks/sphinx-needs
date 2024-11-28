"""sphinx-needs documentation build configuration file"""

import datetime
import os
from pathlib import Path
from typing import Any

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
    ("py:class", "sphinx_needs.debug.T"),
    ("py:class", "sphinx_needs.views._LazyIndexes"),
    ("py:class", "sphinx_needs.config.NeedsSphinxConfig"),
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
latex_elements: dict[str, Any] = {
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
    r"http://sourceforge.net/projects/plantuml.*",
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

needs_from_toml = "ubproject.toml"

needs_debug_measurement = "READTHEDOCS" in os.environ  # run on CI
needs_debug_filters = True


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

# You can uncomment some of the following lines to override the default configuration for Sphinx-Needs.
# DEFAULT_DIAGRAM_TEMPLATE = "<size:12>{{type_name}}</size>\\n**{{title|wordwrap(15, wrapstring='**\\\\n**')}}**\\n<size:10>{{id}}</size>"
# needs_diagram_template = DEFAULT_DIAGRAM_TEMPLATE

# Absolute path to the needs_report_template_file based on the conf.py directory
# needs_report_template = "/needs_templates/report_template.need"   # Use custom report template

# -- custom extensions ---------------------------------------
from typing import get_args  # noqa: E402

from docutils import nodes  # noqa: E402
from docutils.statemachine import StringList  # noqa: E402
from sphinx.application import Sphinx  # noqa: E402
from sphinx.directives import SphinxDirective  # noqa: E402
from sphinx.roles import SphinxRole  # noqa: E402

from sphinx_needs.api import generate_need  # noqa: E402
from sphinx_needs.config import NeedsSphinxConfig  # noqa: E402
from sphinx_needs.logging import (  # noqa: E402
    WarningSubTypeDescription,
    WarningSubTypes,
)
from sphinx_needs.needsfile import NeedsList  # noqa: E402


class NeedsWarningsDirective(SphinxDirective):
    """Directive to list all extension warning subtypes."""

    def run(self):
        parsed = nodes.container(classes=["needs-warnings"])
        content = [
            f"- ``needs.{name}`` {WarningSubTypeDescription.get(name, '')}"
            for name in get_args(WarningSubTypes)
        ]
        self.state.nested_parse(StringList(content), self.content_offset, parsed)
        return [parsed]


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


class NeedConfigDefaultRole(SphinxRole):
    """Role to add a default configuration value to the documentation."""

    def run(self):
        default = NeedsSphinxConfig.get_default(self.text)
        return [[nodes.literal("", repr(default), language="python")], []]


def create_tutorial_needs(app: Sphinx, _env, _docnames):
    """Create a JSON to import in the tutorial.

    We do this dynamically, to avoid having to maintain the JSON file manually.
    """
    needs_config = NeedsSphinxConfig(app.config)
    writer = NeedsList(app.config, outdir=app.confdir, confdir=app.confdir)
    for i in range(1, 5):
        need_item = generate_need(
            needs_config,
            need_type="tutorial-test",
            id=f"T_00{i}",
            title=f"Unit test {i}",
            content=f"Test case {i}",
        )
        writer.add_need(version, need_item)
    json_str = writer.dump_json()
    outpath = Path(app.confdir, "_static", "tutorial_needs.json")
    if outpath.is_file() and outpath.read_text() == json_str:
        return  # only write this file if it has changed
    outpath.write_text(json_str)


def setup(app: Sphinx):
    app.add_directive("need-example", NeedExampleDirective)
    app.add_directive("need-warnings", NeedsWarningsDirective)
    app.add_role("need_config_default", NeedConfigDefaultRole())
    app.connect("env-before-read-docs", create_tutorial_needs, priority=600)
