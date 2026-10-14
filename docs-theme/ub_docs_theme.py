"""The useblocks look for furo, shared by every furo docs site in this repository.

A local Sphinx extension, not a package: a site's ``conf.py`` puts this directory on
``sys.path`` and adds ``"ub_docs_theme"`` to ``extensions`` (``README.md`` beside this file
says why it is not a package, and what that costs an sdist). Under any theme other than
furo it does nothing at all, so sphinx-needs' docs, which build against five themes, load
it unconditionally.

Everything it sets is a DEFAULT: a value the site's ``conf.py`` already gives wins, so a
site keeps only what is its own -- title, favicon, logos, ``source_directory`` and any
stylesheet of its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sphinx.application import Sphinx
from sphinx.config import Config

HERE = Path(__file__).resolve().parent

#: furo's own sidebar, plus the source-repository link (``templates/side-github.html``)
#: below the navigation
SIDEBARS = [
    "sidebar/brand.html",
    "sidebar/search.html",
    "sidebar/scroll-start.html",
    "sidebar/navigation.html",
    "sidebar/ethical-ads.html",
    "sidebar/scroll-end.html",
    "side-github.html",
    "sidebar/variant-selector.html",
]

#: every site lives in this one repository: furo's "view"/"edit" buttons build
#: ``<repo>/blob|edit/<branch>/<source_directory><page>``, so a site sets only
#: ``source_directory``, the path to its sources inside it
THEME_OPTIONS: dict[str, Any] = {
    "sidebar_hide_name": True,
    "top_of_page_buttons": ["view", "edit"],
    "source_repository": "https://github.com/useblocks/sphinx-needs",
    "source_branch": "master",
}

#: what ``side-github.html`` prints as the repository's name
REPOSITORY = "useblocks/sphinx-needs"


def apply_defaults(app: Sphinx, config: Config) -> None:
    """Point a furo build at the shared files and fill in what the site left unset."""
    if config.html_theme != "furo":
        return
    # A file of the site's own with the same name wins over the shared one, which takes
    # the two lists in opposite orders. Sphinx copies the `html_static_path` entries in
    # order, each over the last, so the shared directory goes FIRST and the site's copies
    # land on top of it; it searches `templates_path` in order and takes the first match,
    # so the shared directory goes LAST.
    config.html_static_path = [str(HERE / "static"), *config.html_static_path]
    config.templates_path = [*config.templates_path, str(HERE / "templates")]
    if not config.html_sidebars:
        config.html_sidebars = {"**": list(SIDEBARS)}
    config.html_context = {"repository": REPOSITORY, **config.html_context}
    config.html_theme_options = {**THEME_OPTIONS, **config.html_theme_options}
    # Between furo's own extension sheet and the site's: furo adds
    # `styles/furo-extensions.css` at 600 (in `builder-inited`, after this, so a tie would
    # put this one first and furo's sphinx-design tokens would win), and `html_css_files`
    # entries load at 800, so a site's own stylesheet still comes after this one and
    # overrides it, rule for rule
    app.add_css_file("ub-furo.css", priority=700)


def setup(app: Sphinx) -> dict[str, Any]:
    app.connect("config-inited", apply_defaults)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
