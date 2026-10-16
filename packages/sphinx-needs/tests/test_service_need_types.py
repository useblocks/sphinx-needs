"""The GitHub services' need types and layout, and the need types added from code (#2265).

sphinx-needs keeps the need types added with ``add_need_type`` and the GitHub services'
three need types (``issue``, ``pr``, ``commit``) and ``github`` layout in its own
registry, never in the ``needs_types`` and ``needs_layouts`` values: those hold what the
project configures, so Sphinx compares the same values on both sides of an incremental
build. ``NeedsSphinxConfig(config).types`` and ``.layouts`` -- and so every reader --
merge the two, a configured entry winning over a registered one of the same name.

The GitHub built-ins are registered from a ``config-inited`` handler that runs after
every extension's default-priority one, each only if nothing of its name exists by then,
so a type or layout of the project's, or of another extension's, wins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import responses
from sphinx.util.parallel import parallel_available

from sphinx_needs.api import get_need_types
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.services.config.github import GITHUB_LAYOUT
from sphinx_needs_testkit import build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
"""

#: the three GitHub service types, as sphinx-needs registers them
GITHUB_TYPES = {
    "issue": ("Issue", "IS_"),
    "pr": ("PullRequest", "PR_"),
    "commit": ("Commit", "C_"),
}

#: one need of each GitHub service type, each in the ``github`` layout
SERVICE_TYPES_INDEX = """\
.. issue:: An issue
   :id: IS_00001
   :layout: github

.. pr:: A pull request
   :id: PR_00001
   :layout: github

.. commit:: A commit
   :id: C_00001
   :layout: github
"""


def _project(
    conf: str, index: str, *, buildername: str = "html", **files: str
) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Case\n====\n\n" + index),
            *((Path(name), text) for name, text in files.items()),
        ],
    }


def _types(app: Any) -> dict[str, tuple[str, str]]:
    """Each need type every reader sees, by directive: its title and prefix."""
    return {
        entry["directive"]: (entry["title"], entry["prefix"])
        for entry in NeedsSphinxConfig(app.config).types
    }


def _configured_directives(app: Any) -> list[str]:
    """The directives of the ``needs_types`` value itself."""
    return [entry["directive"] for entry in app.config.needs_types]


# -- the service types and layout work -----------------------------------------------------


@pytest.mark.parametrize(
    "test_app", [_project(CONF, SERVICE_TYPES_INDEX)], indirect=True
)
def test_the_service_types_and_layout_are_usable(test_app: Any) -> None:
    """A need of each GitHub service type, in the ``github`` layout, builds with no
    warning, and the three are known to the schema."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count("needs_layout_github") == 3
    assert {"issue", "pr", "commit"} <= SphinxNeedsData(app.env).get_schema().need_types


@pytest.mark.parametrize(
    "test_app", [_project(CONF, SERVICE_TYPES_INDEX)], indirect=True
)
def test_the_service_entries_stay_out_of_the_configuration_values(
    test_app: Any,
) -> None:
    """The service's types and layout are read through ``NeedsSphinxConfig``, and
    ``needs_types`` and ``needs_layouts`` hold, after the build, only what the project
    configures and sphinx-needs' own built-in layouts (#2265)."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert get_need_types(app)[-3:] == ["issue", "pr", "commit"]
    assert NeedsSphinxConfig(app.config).layouts["github"] == GITHUB_LAYOUT
    assert _configured_directives(app) == ["req", "spec", "impl", "test", "need"]
    assert "github" not in app.config.needs_layouts


#: a GitHub issue as the search API returns it
ISSUE = {
    "number": 7,
    "title": "An issue",
    "body": "Its body",
    "state": "open",
    "labels": [{"name": "bug"}],
    "user": {"login": "octo", "avatar_url": "https://avatars.example/u/1"},
    "html_url": "https://github.com/o/r/issues/7",
    "created_at": "2020-01-01T00:00:00Z",
    "updated_at": "2020-01-02T00:00:00Z",
    "closed_at": None,
}

#: no avatar download, so the one request is the search below
SERVICE_CONF = (
    CONF + 'needs_services = {"github-issues": {"download_avatars": False}}\n'
)


@responses.activate
@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            SERVICE_CONF,
            ".. needservice:: github-issues\n   :query: repo:o/r\n   :max_amount: 1\n",
        )
    ],
    indirect=True,
)
def test_a_needservice_need_is_an_issue_in_the_github_layout(test_app: Any) -> None:
    """A need the ``github-issues`` service creates is of the ``issue`` type and in the
    ``github`` layout by default, no request leaving the test."""
    responses.get(
        "https://api.github.com/search/issues",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "repo:o/r is:issue", "per_page": "1"}
            )
        ],
        json={"items": [ISSUE]},
    )
    app = test_app
    app.build()
    assert build_warnings(app) == []
    need = SphinxNeedsData(app.env).get_needs_view()["GITHUB_7"]
    assert (need["type"], need["layout"]) == ("issue", "github")
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count("needs_layout_github") == 1


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **_project(
                CONF,
                ".. toctree::\n\n" + "".join(f"   d{i}\n" for i in range(1, 7)),
                **{
                    f"d{i}.rst": f"D{i}\n===\n\n"
                    + SERVICE_TYPES_INDEX.replace("_00001\n", f"_0000{i}\n")
                    for i in range(1, 7)
                },
            ),
            "parallel": 2,
        }
    ],
    indirect=True,
)
@pytest.mark.skipif(not parallel_available, reason="Parallel execution not supported")
def test_a_parallel_build_keeps_the_service_types_and_layout(test_app: Any) -> None:
    """The registry is filled before the documents are read, so every process that
    reads them knows the service's types and layout."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert len(SphinxNeedsData(app.env).get_needs_view()) == 18
    for i in range(1, 7):
        html = Path(app.outdir, f"d{i}.html").read_text(encoding="utf-8")
        assert html.count("needs_layout_github") == 3


# -- what wins -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("test_app", "mine"),
    [
        pytest.param(
            _project(
                CONF
                + "needs_types = [\n"
                + '    {"directive": "req", "title": "Requirement", "prefix": "R_"},\n'
                + f'    {{"directive": "{name}", "title": "Mine", "prefix": "MI_"}},\n'
                + "]\n",
                f".. {name}:: Mine\n   :id: MI_00001\n",
            ),
            name,
            id=name,
        )
        for name in GITHUB_TYPES
    ],
    indirect=["test_app"],
)
def test_a_configured_service_type_wins_and_the_others_are_added(
    test_app: Any, mine: str
) -> None:
    """A configured type named as one of the service's keeps its own title and prefix,
    and the service still adds its other two, each on its own. A configured ``issue``
    used to stop the service adding ``pr`` and ``commit``, and a configured ``pr`` its
    ``commit``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert _types(app) == {
        "req": ("Requirement", "R_"),
        mine: ("Mine", "MI_"),
        **{name: entry for name, entry in GITHUB_TYPES.items() if name != mine},
    }


#: another extension adds ``issue`` from a handler at the default priority
THIRD_PARTY_ISSUE = """
def _add_issue(app, config):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "issue", "Their issue", "TI_")

def setup(app):
    app.connect("config-inited", _add_issue)
"""


@pytest.mark.parametrize(
    "test_app",
    [_project(CONF + THIRD_PARTY_ISSUE, ".. issue:: Theirs\n   :id: TI_00001\n")],
    indirect=True,
)
def test_an_extension_type_named_as_a_service_type_wins(test_app: Any) -> None:
    """``add_need_type`` for ``issue`` from another extension's ``config-inited``
    handler succeeds, and the service's ``issue`` is not added; its ``pr`` and
    ``commit`` are, after it."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert get_need_types(app) == [
        "req",
        "spec",
        "impl",
        "test",
        "need",
        "issue",
        "pr",
        "commit",
    ]
    assert _types(app)["issue"] == ("Their issue", "TI_")


#: a project layout named ``github``
MY_GITHUB = {"grid": "simple", "layout": {"head": ["Mine: <<meta('title')>>"]}}


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            CONF + f"needs_layouts = {{'github': {MY_GITHUB!r}}}\n",
            SERVICE_TYPES_INDEX,
        )
    ],
    indirect=True,
)
def test_a_configured_github_layout_wins(test_app: Any) -> None:
    """A ``needs_layouts`` entry named ``github`` is the layout every reader sees, and
    the one the needs are rendered with."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert NeedsSphinxConfig(app.config).layouts["github"] == MY_GITHUB
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count("needs_layout_github") == 3
    assert html.count("Mine: ") == 3


def test_the_view_is_a_fresh_value_on_each_read(tmp_path: Path, make_app: Any) -> None:
    """Changing the list or mapping a read returned changes nothing: types and layouts
    are added with ``add_need_type`` and configured with the options."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    app = make_app("html", srcdir=srcdir)
    try:
        config = NeedsSphinxConfig(app.config)
        config.types.append({"directive": "x", "title": "X", "prefix": "X_"})
        config.layouts["x"] = {}
        assert "x" not in get_need_types(app)
        assert "x" not in config.layouts
    finally:
        app.cleanup()
