"""The GitHub services' need types and layout, and the types and layouts added from code
(#2265).

sphinx-needs keeps the need types and layouts added with ``add_need_type`` and
``add_need_layout``, and the GitHub services' three need types (``issue``, ``pr``,
``commit``) and ``github`` layout, in its own registry, never in the ``needs_types`` and
``needs_layouts`` values: those hold what the project configures, so Sphinx compares the
same values on both sides of an incremental build. ``NeedsSphinxConfig(config).types``
and ``.layouts`` -- and so every reader -- read three tiers, each entry shadowing those of
its name below it: the configured entries, then the added ones, then the GitHub
built-ins, which therefore come last and give way, one by one, to a type or layout of
their name configured or added at any time. The two reads cannot be written through.
"""

from __future__ import annotations

import copy
import pickle
from pathlib import Path
from typing import Any

import pytest
import responses
from sphinx.util.parallel import parallel_available

from sphinx_needs.api import add_need_type, get_need_types
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsApiConfigException
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


#: another extension adds ``issue``, from a handler of the event and priority given
THIRD_PARTY_ISSUE = """
def _add_issue(app, *_args):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "issue", "Their issue", "TI_")

def setup(app):
    app.connect({event!r}, _add_issue, priority={priority})
"""


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            _project(
                CONF + THIRD_PARTY_ISSUE.format(event=event, priority=priority),
                ".. issue:: Theirs\n   :id: TI_00001\n",
            ),
            id=f"{event}-{priority}",
        )
        for event, priority in (
            ("config-inited", 500),
            ("config-inited", 950),
            ("builder-inited", 500),
        )
    ],
    indirect=True,
)
def test_an_extension_type_named_as_a_service_type_wins(test_app: Any) -> None:
    """``add_need_type`` for ``issue`` from another extension succeeds whenever it is
    called, and the service's ``issue`` gives way to it; its ``pr`` and ``commit`` are
    still there, last."""
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
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "TI_00001" in html


#: another extension adds ``story`` after every ``config-inited`` handler of sphinx-needs
LATE_STORY = """
def _add_story(app, config):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "story", "Story", "ST_")

def setup(app):
    app.connect("config-inited", _add_story, priority=950)
"""


@pytest.mark.parametrize("test_app", [_project(CONF + LATE_STORY, "")], indirect=True)
def test_the_service_types_come_after_every_added_type(test_app: Any) -> None:
    """The GitHub services' types follow the configured types and every type added
    with ``add_need_type``, however late, as they always did: the order of legends,
    of ``needreport`` and of ``list2need``'s types."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert get_need_types(app) == [
        "req",
        "spec",
        "impl",
        "test",
        "need",
        "story",
        "issue",
        "pr",
        "commit",
    ]


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


@pytest.fixture
def plain_app(tmp_path: Path, make_app: Any) -> Any:
    """An application of a project that configures nothing but sphinx-needs."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(CONF, encoding="utf-8")
    (srcdir / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    app = make_app("html", srcdir=srcdir)
    yield app
    app.cleanup()


ENTRY = {"directive": "x", "title": "X", "prefix": "X_"}


#: each change the list of types refuses: the method, and the arguments to call it with
TYPES_WRITES = {
    "append": (ENTRY,),
    "extend": ([ENTRY],),
    "insert": (0, ENTRY),
    "remove": (None,),
    "pop": (),
    "clear": (),
    "sort": (),
    "reverse": (),
    "__setitem__": (0, ENTRY),
    "__delitem__": (0,),
    "__iadd__": ([ENTRY],),
    "__imul__": (2,),
}

#: each change the dict of layouts refuses, as :data:`TYPES_WRITES`
LAYOUTS_WRITES = {
    "pop": ("clean",),
    "popitem": (),
    "clear": (),
    "setdefault": ("x", {}),
    "update": ({"x": {}},),
    "__setitem__": ("x", {}),
    "__delitem__": ("clean",),
    "__ior__": ({"x": {}},),
}


def _del_type(config: NeedsSphinxConfig) -> None:
    del config.types[0]


def _del_layout(config: NeedsSphinxConfig) -> None:
    del config.layouts["clean"]


def _add_types(config: NeedsSphinxConfig) -> None:
    types = config.types
    types += [ENTRY]


def _or_layouts(config: NeedsSphinxConfig) -> None:
    layouts = config.layouts
    layouts |= {"x": {}}


@pytest.mark.parametrize(
    ("write", "routes"),
    [
        *(
            pytest.param(
                lambda c, n=name, a=args: getattr(c.types, n)(*a),
                ("needs_types", "add_need_type"),
                id=f"types.{name}",
            )
            for name, args in TYPES_WRITES.items()
        ),
        *(
            pytest.param(
                lambda c, n=name, a=args: getattr(c.layouts, n)(*a),
                ("needs_layouts", "add_need_layout"),
                id=f"layouts.{name}",
            )
            for name, args in LAYOUTS_WRITES.items()
        ),
        pytest.param(_del_type, ("needs_types", "add_need_type"), id="del types[0]"),
        pytest.param(_add_types, ("needs_types", "add_need_type"), id="types +="),
        pytest.param(
            _del_layout, ("needs_layouts", "add_need_layout"), id="del layouts[name]"
        ),
        pytest.param(
            _or_layouts, ("needs_layouts", "add_need_layout"), id="layouts |="
        ),
        pytest.param(
            lambda c: setattr(c, "types", [ENTRY]),
            ("needs_types", "add_need_type"),
            id="types =",
        ),
        pytest.param(
            lambda c: setattr(c, "layouts", {}),
            ("needs_layouts", "add_need_layout"),
            id="layouts =",
        ),
    ],
)
def test_the_views_cannot_be_written_through(
    plain_app: Any, write: Any, routes: tuple[str, str]
) -> None:
    """The types and layouts every reader sees are read-only: each change through them,
    which could never reach the configuration or the registry, raises, naming the two
    routes, and changes nothing."""
    config = NeedsSphinxConfig(plain_app.config)
    types, layouts = list(config.types), dict(config.layouts)
    with pytest.raises(NeedsApiConfigException) as raised:
        write(config)
    assert all(route in str(raised.value) for route in routes)
    assert (list(config.types), dict(config.layouts)) == (types, layouts)


def test_a_copy_of_a_view_is_a_plain_value(plain_app: Any) -> None:
    """A copy of a read is the caller's own: a plain list or dict."""
    config = NeedsSphinxConfig(plain_app.config)
    for value in (config.types, config.layouts):
        for duplicate in (
            copy.copy(value),
            copy.deepcopy(value),
            pickle.loads(pickle.dumps(value)),
        ):
            assert type(duplicate) in (list, dict)
            assert duplicate == value


# -- the duplicate checks ----------------------------------------------------------------


def test_add_need_type_refuses_a_directive_already_taken(plain_app: Any) -> None:
    """A directive that is a configured need type, or one added before, is refused; the
    GitHub built-in ``issue`` is not taken: the added type replaces it."""
    add_need_type(plain_app, "x", "X", "X_")
    for directive in ("x", "req"):
        with pytest.raises(
            NeedsApiConfigException, match=f"{directive} already exists as need type"
        ):
            add_need_type(plain_app, directive, "Again", "AG_")
    add_need_type(plain_app, "issue", "Mine", "MI_")
    titles = {
        t["directive"]: t["title"] for t in NeedsSphinxConfig(plain_app.config).types
    }
    assert (titles["x"], titles["req"], titles["issue"]) == ("X", "Requirement", "Mine")


# -- add_need_layout ---------------------------------------------------------------------

#: an extension adds the layout ``ext_card`` from a ``config-inited`` handler
EXT_LAYOUT = """
def _add_layout(app, config):
    from sphinx_needs.api import add_need_layout
    add_need_layout(
        app, "ext_card", {"grid": "simple", "layout": {"head": ["Ext: <<meta('title')>>"]}}
    )

def setup(app):
    app.connect("config-inited", _add_layout)
"""


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            CONF + EXT_LAYOUT,
            ".. req:: A requirement\n   :id: R_00001\n   :layout: ext_card\n",
        )
    ],
    indirect=True,
)
def test_an_extension_layout_is_usable(test_app: Any) -> None:
    """A layout added with ``add_need_layout`` is read beside the configured ones, and a
    need is rendered with it; it is not written into ``needs_layouts``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert "ext_card" in NeedsSphinxConfig(app.config).layouts
    assert "ext_card" not in app.config.needs_layouts
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count("needs_layout_ext_card") == 1
    assert html.count("Ext: ") == 1


LAYOUT = {"grid": "simple", "layout": {"head": ["X"]}}

#: an extension adds a layout named as one of sphinx-needs' own, before they are merged
#: into ``needs_layouts`` (``config-inited``, priority 500)
EARLY_CLEAN = """
def _add_clean(app, config):
    from sphinx_needs.api import add_need_layout
    add_need_layout(app, "clean", {"grid": "simple", "layout": {}})

def setup(app):
    app.connect("config-inited", _add_clean, priority=499)
"""


def test_add_need_layout_refuses_a_builtin_name_before_it_is_configured(
    tmp_path: Path, make_app: Any
) -> None:
    """sphinx-needs' own layouts are taken from the start: added before they are merged
    into ``needs_layouts``, a layout of one's name would be shadowed by it silently."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(CONF + EARLY_CLEAN, encoding="utf-8")
    (srcdir / "index.rst").write_text("Case\n====\n", encoding="utf-8")
    with pytest.raises(NeedsApiConfigException, match="clean already exists"):
        make_app("html", srcdir=srcdir)


def test_add_need_layout_refuses_a_name_already_taken(plain_app: Any) -> None:
    """A name that is a configured layout (sphinx-needs' own included) or one added
    before is refused; the GitHub built-in ``github`` is not taken: the added layout
    replaces it."""
    from sphinx_needs.api import add_need_layout

    add_need_layout(plain_app, "x", LAYOUT)
    for name in ("x", "clean"):
        with pytest.raises(NeedsApiConfigException, match=f"{name} already exists"):
            add_need_layout(plain_app, name, LAYOUT)
    add_need_layout(plain_app, "github", LAYOUT)
    layouts = NeedsSphinxConfig(plain_app.config).layouts
    assert (layouts["x"], layouts["github"]) == (LAYOUT, LAYOUT)


# -- a configured entry wins on a collision -----------------------------------------------

#: an extension adds a type and a layout, and an old-style one writes the configuration
#: values after it, and after every ``config-inited`` handler: an entry of each tier's
#: name is configured late
COLLISIONS = """
def _add(app, config):
    from sphinx_needs.api import add_need_type
    add_need_type(app, "story", "Their story", "TS_")
    from sphinx_needs.api import add_need_layout
    add_need_layout(app, "ext_card", {"grid": "simple", "layout": {}})

def _late(app):
    app.config.needs_types = [
        *app.config.needs_types,
        {"directive": "issue", "title": "Mine", "prefix": "MI_"},
        {"directive": "story", "title": "My story", "prefix": "MS_"},
    ]
    app.config.needs_layouts = {
        **app.config.needs_layouts,
        "github": {"grid": "simple", "layout": {"head": ["MINE"]}},
        "ext_card": {"grid": "simple", "layout": {"head": ["MY CARD"]}},
    }

def setup(app):
    app.connect("config-inited", _add)
    app.connect("builder-inited", _late)
"""


@pytest.mark.parametrize("test_app", [_project(CONF + COLLISIONS, "")], indirect=True)
def test_a_configured_entry_wins_on_a_collision(test_app: Any) -> None:
    """Where a configured entry and an added or built-in one share a name -- which only
    a write into the configuration after they were added can make -- the configured
    entry is the one every reader sees, once."""
    app = test_app
    config = NeedsSphinxConfig(app.config)
    types = [t for t in config.types if t["directive"] in ("issue", "story")]
    assert [(t["directive"], t["title"]) for t in types] == [
        ("issue", "Mine"),
        ("story", "My story"),
    ]
    assert config.layouts["github"]["layout"] == {"head": ["MINE"]}
    assert config.layouts["ext_card"]["layout"] == {"head": ["MY CARD"]}
