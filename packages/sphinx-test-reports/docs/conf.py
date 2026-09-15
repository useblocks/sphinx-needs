#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/stable/config

# -- Path setup --------------------------------------------------------------

import datetime
import os
import shutil

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
import sys
import tomllib
from pathlib import Path

from packaging.version import Version

import sphinx_needs

sys.path.append(os.path.abspath("."))

from ub_theme.conf import html_theme_options

# -- Project information -----------------------------------------------------

project = "sphinx-test-reports"
now = datetime.datetime.now()
copyright = f"team useblocks, 2017-{now.year}"
author = "team useblocks"

# The short X.Y version
version = "2.0"
# The full version, including alpha/beta/rc tags
release = "2.0.0"

needs_id_regex = ".*"
needs_css = "dark.css"

# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx_needs",
    "sphinxcontrib.test_reports",
    "sphinxcontrib.plantuml",
    "sphinx_design",
    "sphinx_immaterial",
]


def _resolve_plantuml() -> str:
    """How these docs render PlantUML, in the order the whole workspace agrees on.

    1. ``PLANTUML_JAR``, through ``java``. An explicit choice wins, and a value naming no
       file is an error rather than a silent fall-through.
    2. The workspace's committed jar, ``vendor/plantuml/plantuml-<pinned version>.jar``.
       ``vendor/plantuml/pin.toml`` is the one place the version is written, and the jar is
       committed beside it, so this route needs nothing of the environment -- which is what
       lets Read the Docs build these docs with no network beyond its own install.
    3. A ``plantuml`` executable on ``PATH`` (``plantumlc`` first on Windows, whose
       chocolatey ``plantuml`` shim is a non-blocking ``javaw`` launcher).

    These docs carried their own jar under ``docs/utils/`` until the import into this
    workspace -- a second copy, at a second version, beside the test suite's own. The chain
    is written out here rather than imported from the shared test layer, exactly as
    ``packages/sphinx-needs/docs/conf.py`` writes it out: a docs build must not import a
    test-only member, and a reader of this file should not have to look elsewhere to find
    out what renders their diagrams.
    """
    quoted = 'java -Djava.awt.headless=true -jar "{}"'
    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        if not os.path.isfile(env_jar):
            raise RuntimeError(
                f"PLANTUML_JAR names {env_jar!r}, which is not a file. Point it at a "
                "plantuml jar, or unset it to render with the jar committed at "
                "vendor/plantuml/."
            )
        return quoted.format(env_jar)
    vendor = Path(__file__).resolve().parents[3] / "vendor" / "plantuml"
    pinned = None
    if (pin := vendor / "pin.toml").is_file():
        version = tomllib.loads(pin.read_text(encoding="utf-8"))["version"]
        pinned = vendor / f"plantuml-{version}.jar"
        if pinned.is_file():
            return quoted.format(pinned)
    for name in ("plantumlc", "plantuml") if os.name == "nt" else ("plantuml",):
        if executable := shutil.which(name):
            return executable
    if pinned is None:
        raise RuntimeError(
            "no PlantUML to render these docs with, and this tree has no "
            "vendor/plantuml/pin.toml naming one -- which is what an sdist looks like. "
            "Set PLANTUML_JAR to a plantuml jar (with java on PATH), or install a "
            "plantuml executable; in a checkout of the repository, "
            "`uv run poe fetch-plantuml` downloads the pinned one."
        )
    raise RuntimeError(
        "no PlantUML to render these docs with. Run `uv run poe fetch-plantuml` to "
        "download the pinned jar into vendor/plantuml/, or set PLANTUML_JAR to a plantuml "
        "jar of your own (with java on PATH), or install a plantuml executable."
    )


plantuml = _resolve_plantuml()

plantuml_output_format = "png"


# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates", "ub_theme/templates"]
if Version(sphinx_needs.__version__) >= Version("7.0.0"):
    needs_fields = {
        "more_info": {"nullable": True},
    }
else:
    needs_extra_options = ["more_info"]

tr_extra_options = ["more_info"]
# Add a custom test report template. Please add a relative path from this conf.py
# tr_report_template = "./custom_test_report_template.txt"

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_immaterial"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_logo = "_static/sphinx-test-reports-logo.svg"
html_favicon = "_static/sphinx-test-reports-logo.svg"
html_title = "Sphinx-Test-Reports"

other_options = {
    "repo_url": "https://github.com/useblocks/sphinx-needs",
    "repo_name": "sphinx-needs",
    "font": False,
}
html_theme_options.update(other_options)
html_theme_options["features"].extend(["navigation.tabs", "navigation.tabs.sticky"])
# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static", "ub_theme/css", "ub_theme/js"]
html_css_files = ["ub-theme.css"]
html_js_files = ["jquery.js"]

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "sphinx-test-reportsdoc"


# -- Options for LaTeX output ------------------------------------------------

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
    (
        master_doc,
        "sphinx-test-reports.tex",
        "sphinx-test-reports Documentation",
        "team useblocks",
        "manual",
    ),
]


# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (
        master_doc,
        "sphinx-test-reports",
        "sphinx-test-reports Documentation",
        [author],
        1,
    )
]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "sphinx-test-reports",
        "sphinx-test-reports Documentation",
        author,
        "sphinx-test-reports",
        "One line description of project.",
        "Miscellaneous",
    ),
]

# LINKCHECK config
# https://www.sphinx-doc.org/en/master/usage/configuration.html?highlight=linkcheck#options-for-the-linkcheck-builder
linkcheck_ignore = [
    r"http://localhost:\d+",
    r"http://127.0.0.1:\d+",
    r"https://fonts.googleapis.com",
]

linkcheck_request_headers = {
    "*": {
        "User-Agent": "Mozilla/5.0",
    }
}

linkcheck_workers = 5
