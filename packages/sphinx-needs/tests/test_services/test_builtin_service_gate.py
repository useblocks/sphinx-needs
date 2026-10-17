"""The built-in GitHub services are registered only when ``needs_services`` names them.

``github-issues``, ``github-prs`` and ``github-commits`` used to be registered in every
build, so every project carried their twelve fields (``url``, ``user``, ``avatar``, ...),
their three need types (``issue``, ``pr``, ``commit``) and the ``github`` layout,
whether or not it used GitHub. A built-in is now registered only when ``needs_services``
names it with a mapping of options (``{}`` will do), from ``conf.py`` or a
``[needs.services.<name>]`` table of the ``needs_from_toml`` file: then the service, the
twelve fields, the need type of that service alone, and the layout. A ``needservice``
naming an unconfigured built-in is one warning that says how to configure it, and a
needs.json written by an earlier version, which carries the twelve keys on every need,
still imports without a warning for their empty values.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
import responses

from sphinx_needs.api import get_need_types
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needservice import Needservice
from sphinx_needs.nodes import Need
from sphinx_needs_testkit import assert_no_warnings, build_warnings

RST = "Title\n=====\n\nText.\n"

CONF = 'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'

#: each built-in service, and the need type it adds
BUILT_IN = {"github-issues": "issue", "github-prs": "pr", "github-commits": "commit"}

#: the fields every built-in service registers (its ``options`` but ``type``)
SERVICE_FIELDS = {
    "user",
    "created_at",
    "updated_at",
    "closed_at",
    "service",
    "url",
    "avatar",
    "query",
    "specific",
    "max_amount",
    "max_content_lines",
    "id_prefix",
}


def services_conf(*names: str) -> str:
    """A ``conf.py`` configuring the named built-ins, each with no options."""
    entries = ", ".join(f"{name!r}: {{}}" for name in names)
    return CONF + f"needs_services = {{{entries}}}\n"


@pytest.fixture
def build(make_app: Any, tmp_path: Path) -> Any:
    """Write a project, build it, and return the application."""

    def _build(files: dict[str, str], **kwargs: Any) -> Any:
        srcdir = tmp_path / "src"
        for name, content in {"index.rst": RST, **files}.items():
            path = srcdir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(content), encoding="utf-8")
        app = make_app(srcdir=srcdir, freshenv=True, **kwargs)
        app.build()
        return app

    return _build


def registered(app: Any) -> set[str]:
    """The names of the services the build registered."""
    return set(app._needs_services.services)


def service_types(app: Any) -> set[str]:
    """The built-in services' need types every reader sees."""
    return set(get_need_types(app)) & set(BUILT_IN.values())


def service_fields(app: Any) -> set[str]:
    """The built-in services' fields the schema knows."""
    schema = SphinxNeedsData(app.env).get_schema()
    return SERVICE_FIELDS & set(schema.iter_extra_field_names())


def has_github_layout(app: Any) -> bool:
    return "github" in NeedsSphinxConfig(app.config).layouts


# -- what is registered ---------------------------------------------------------------


def test_a_project_naming_no_service_has_no_github_service(build: Any) -> None:
    """No service, none of the twelve fields (in the schema or on a need of needs.json),
    no ``issue``/``pr``/``commit`` and no ``github`` layout."""
    app = build({"conf.py": CONF, "index.rst": RST + "\n.. req:: R\n   :id: R_001\n"})
    assert_no_warnings(app)
    assert registered(app) == set()
    assert service_fields(app) == set()
    assert service_types(app) == set()
    assert not has_github_layout(app)
    needs_json = json.loads(Path(app.outdir, "needs.json").read_text("utf-8"))
    version = needs_json["versions"][needs_json["current_version"]]
    assert SERVICE_FIELDS.isdisjoint(version["needs"]["R_001"])
    assert SERVICE_FIELDS.isdisjoint(version["needs_schema"]["properties"])


@pytest.mark.parametrize("name", list(BUILT_IN))
def test_a_configured_built_in_adds_its_own_type_only(build: Any, name: str) -> None:
    """Configuring one built-in registers that service, the twelve fields, the
    ``github`` layout and its own need type -- not the other two services' types."""
    app = build({"conf.py": services_conf(name)})
    assert_no_warnings(app)
    assert registered(app) == {name}
    assert service_fields(app) == SERVICE_FIELDS
    assert service_types(app) == {BUILT_IN[name]}
    assert has_github_layout(app)


def test_every_built_in_configured_adds_the_three_types(build: Any) -> None:
    app = build({"conf.py": services_conf(*BUILT_IN)})
    assert_no_warnings(app)
    assert registered(app) == set(BUILT_IN)
    assert get_need_types(app)[-3:] == ["issue", "pr", "commit"]
    assert has_github_layout(app)


def test_a_toml_table_configures_a_built_in(build: Any) -> None:
    """A ``[needs.services.<name>]`` table of the ``needs_from_toml`` file is a
    configuration of the built-in, as a ``conf.py`` entry is."""
    app = build(
        {
            "conf.py": CONF + 'needs_from_toml = "ubproject.toml"\n',
            "ubproject.toml": "[needs.services.github-prs]\nmax_amount = 2\n",
        }
    )
    assert_no_warnings(app)
    assert registered(app) == {"github-prs"}
    assert service_types(app) == {"pr"}
    assert has_github_layout(app)


#: records, from ``config-inited`` handlers at priorities 11 and 13, whether a reader
#: of the need types sees ``issue``
PRIORITY_PROBE = """
def _probe(priority):
    def handler(app, config):
        from sphinx_needs.api import get_need_types
        app.gate_probe[priority] = "issue" in get_need_types(app)
    return handler

def setup(app):
    app.gate_probe = {}
    for priority in (11, 13):
        app.connect("config-inited", _probe(priority), priority=priority)
"""


@pytest.mark.parametrize(
    ("conf", "seen"),
    [
        pytest.param(services_conf("github-issues"), {11: False, 13: True}, id="on"),
        pytest.param(CONF, {11: False, 13: False}, id="off"),
    ],
)
def test_the_service_type_is_listed_from_config_inited_priority_12(
    build: Any, conf: str, seen: dict[int, bool]
) -> None:
    """The type is added at ``config-inited`` priority 12, where the final
    ``needs_services`` (``conf.py``, the TOML file, ``-D``) is known: a reader above 12
    sees it when the service is configured, a reader below 12 never does."""
    app = build({"conf.py": conf + PRIORITY_PROBE})
    assert app.gate_probe == seen


# -- what an unconfigured built-in gives --------------------------------------------------


def not_configured(name: str, line: int = 6) -> str:
    return (
        f"<srcdir>/index.rst:{line}: WARNING: Service {name!r} is a built-in service "
        "that is not configured, so it is not registered: name it in needs_services "
        f'to use it, e.g. needs_services = {{"{name}": {{}}}} in conf.py, or a '
        f"[needs.services.{name}] table in ubproject.toml [needs.load_service_need]"
    )


def assert_nothing_rendered(app: Any) -> None:
    """The directive added no node, and no need was created."""
    doctree = app.env.get_doctree("index")
    assert not list(doctree.findall(Needservice))
    assert not list(doctree.findall(Need))
    assert len(SphinxNeedsData(app.env).get_needs_view()) == 0


@pytest.mark.parametrize("name", list(BUILT_IN))
def test_a_needservice_naming_an_unconfigured_built_in_says_how_to_configure_it(
    build: Any, name: str
) -> None:
    app = build({"conf.py": CONF, "index.rst": RST + f"\n.. needservice:: {name}\n"})
    assert build_warnings(app) == [not_configured(name)]
    assert_nothing_rendered(app)


def test_the_unconfigured_built_in_warning_is_the_only_one(build: Any) -> None:
    """The service's control options are fields only once a service registered them:
    the built-in is checked before the options, so ``:query:`` and ``:max_amount:``
    are not each an ``Unknown option`` warning besides the one that names the cause."""
    app = build(
        {
            "conf.py": CONF,
            "index.rst": RST
            + "\n.. needservice:: github-issues\n"
            + "   :query: repo:o/r\n   :max_amount: 1\n   :id_prefix: GH_\n",
        }
    )
    assert build_warnings(app) == [not_configured("github-issues")]
    assert_nothing_rendered(app)


def test_a_built_in_configured_with_a_non_mapping_is_not_registered(
    build: Any,
) -> None:
    """``-D needs_services.github-issues=1`` sets the string ``'1'``, which used to end
    the build in the service's constructor. It is a ``needs.config`` warning and the
    service is not registered; a ``needservice`` naming it says what is wrong."""
    app = build(
        {"conf.py": CONF, "index.rst": RST + "\n.. needservice:: github-issues\n"},
        confoverrides={"needs_services.github-issues": "1"},
    )
    assert build_warnings(app) == [
        "WARNING: needs_services entry 'github-issues' is not registered: its "
        "configuration must be a mapping of options (got a value of type 'str') "
        "[needs.config]",
        "<srcdir>/index.rst:6: WARNING: Service 'github-issues' is a built-in service "
        "whose needs_services entry is not a mapping of options, so it is not "
        'registered: configure it as a mapping, e.g. needs_services = {"github-issues": '
        "{}} in conf.py, or a [needs.services.github-issues] table in ubproject.toml "
        "[needs.load_service_need]",
    ]
    assert registered(app) == set()
    assert service_types(app) == set()


def test_a_hand_written_service_type_needs_the_service(build: Any) -> None:
    """``.. issue::`` is the directive of the ``issue`` type, which only a configured
    ``github-issues`` (or the project's own ``needs_types``) declares."""
    app = build(
        {"conf.py": CONF, "index.rst": RST + "\n.. issue:: I\n   :id: IS_001\n"}
    )
    assert [w for w in build_warnings(app) if 'Unknown directive type "issue"' in w]
    assert len(SphinxNeedsData(app.env).get_needs_view()) == 0


def test_a_service_field_on_a_need_needs_the_service(build: Any) -> None:
    """``:url:`` on a need of the project's own type is a field only a configured
    service (or ``needs_fields``) declares."""
    app = build(
        {
            "conf.py": CONF,
            "index.rst": RST + "\n.. req:: R\n   :id: R_001\n   :url: https://x.org\n",
        }
    )
    assert build_warnings(app) == [
        "<srcdir>/index.rst:6: WARNING: Unknown option 'url' [needs.directive]"
    ]
    assert "url" not in SphinxNeedsData(app.env).get_needs_view()["R_001"]


# -- a needs.json written before the gate -----------------------------------------------


def old_needs_json(**values: Any) -> str:
    """A needs.json as earlier versions wrote it: the twelve service keys on the need,
    null unless given."""
    need = {
        "id": "OLD_1",
        "title": "Old",
        "type": "req",
        **dict.fromkeys(sorted(SERVICE_FIELDS)),
        **values,
    }
    return json.dumps(
        {"current_version": "1", "versions": {"1": {"needs": {"OLD_1": need}}}}
    )


#: each reader of a needs.json, and how its index file imports ``old.json``
READERS = {
    "needimport": ("", "\n.. needimport:: old.json\n"),
    "external": (
        'needs_external_needs = [{"json_path": "old.json", "base_url": "http://x"}]\n',
        "",
    ),
}


def import_project(reader: str, conf: str, needs_json: str) -> dict[str, str]:
    extra_conf, directive = READERS[reader]
    return {
        "conf.py": conf + extra_conf,
        "index.rst": RST + directive,
        "old.json": needs_json,
    }


def unknown_keys_warning(reader: str, keys: list[str]) -> str:
    if reader == "needimport":
        return (
            f"<srcdir>/index.rst:6: WARNING: Unknown keys in import need source: "
            f"{keys!r} [needs.unknown_import_keys]"
        )
    return (
        f"WARNING: Unknown keys in external need source 'old.json': {keys!r} "
        "[needs.unknown_external_keys]"
    )


@pytest.mark.parametrize("empty", [None, ""], ids=["null", "empty-string"])
@pytest.mark.parametrize("reader", list(READERS))
def test_an_old_needs_json_imports_its_empty_service_keys_silently(
    build: Any, reader: str, empty: Any
) -> None:
    """Every needs.json written up to now carries the twelve keys, null (or ``""`` in
    older files) where no service made the need. Into a project with no service they
    are dropped without the unknown-keys warning, which would fail a ``-W`` build of a
    project that never used GitHub."""
    values = dict.fromkeys(SERVICE_FIELDS, empty)
    app = build(import_project(reader, CONF, old_needs_json(**values)))
    assert_no_warnings(app)
    need = SphinxNeedsData(app.env).get_needs_view()["OLD_1"]
    assert SERVICE_FIELDS.isdisjoint(need.keys())


@pytest.mark.parametrize("reader", list(READERS))
def test_an_old_needs_json_reports_a_service_key_that_holds_a_value(
    build: Any, reader: str
) -> None:
    """Only an empty value is dropped silently: a value is data the project cannot
    keep, and is reported as an unknown key, as before."""
    app = build(import_project(reader, CONF, old_needs_json(url="https://x.org")))
    assert build_warnings(app) == [unknown_keys_warning(reader, ["url"])]
    need = SphinxNeedsData(app.env).get_needs_view()["OLD_1"]
    assert SERVICE_FIELDS.isdisjoint(need.keys())


@pytest.mark.parametrize("reader", list(READERS))
def test_a_configured_service_imports_the_service_keys_as_fields(
    build: Any, reader: str
) -> None:
    """With a built-in configured the twelve keys are fields, and are imported as
    they are: an empty string stays one."""
    app = build(
        import_project(
            reader,
            services_conf("github-issues"),
            old_needs_json(url="", user="octo"),
        )
    )
    assert_no_warnings(app)
    need = SphinxNeedsData(app.env).get_needs_view()["OLD_1"]
    assert (need["url"], need["user"], need["avatar"]) == ("", "octo", None)


# -- a custom GithubService entry, as in the GitHub Enterprise example ---------------------

#: a ``needs_services`` entry of the class itself, as the documentation's GitHub
#: Enterprise example configures it, without the built-in it imitates
ENTERPRISE_CONF = (
    CONF
    + """
from sphinx_needs.services.github import GithubService

needs_services = {
    "my-company-issues": {
        "class": GithubService,
        "class_init": {"gh_type": "issue"},
        "url": "https://github.example/api/v3/",
        "download_avatars": False,
    },
}
# Sphinx's own warning that a class in the configuration is not pickled
suppress_warnings = ["config.cache"]
"""
)

ENTERPRISE_INDEX = (
    RST
    + "\n.. needservice:: my-company-issues\n   :query: repo:o/r\n   :max_amount: 1\n"
)

#: a GitHub issue as the search API returns it
ISSUE = {
    "number": 7,
    "title": "An issue",
    "body": "Its body",
    "state": "open",
    "labels": [],
    "user": {"login": "octo", "avatar_url": "https://avatars.example/u/1"},
    "html_url": "https://github.example/o/r/issues/7",
    "created_at": "2020-01-01T00:00:00Z",
    "updated_at": "2020-01-02T00:00:00Z",
    "closed_at": None,
}


def fake_enterprise_search() -> None:
    """The one request the project makes, answered without leaving the test."""
    responses.get(
        "https://github.example/api/v3/search/issues",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "repo:o/r is:issue", "per_page": "1"}
            )
        ],
        json={"items": [ISSUE]},
    )


@responses.activate
def test_a_custom_github_service_alone_says_which_built_in_adds_its_type(
    build: Any,
) -> None:
    """The service runs, but its needs are of the ``issue`` type, which only the
    configured ``github-issues`` adds: the refusal says so, and how to fix it."""
    fake_enterprise_search()
    app = build({"conf.py": ENTERPRISE_CONF, "index.rst": ENTERPRISE_INDEX})
    assert build_warnings(app) == [
        "<srcdir>/index.rst:6: WARNING: Service need could not be created: Unknown "
        "need type 'issue'. The 'issue' type is registered by the built-in "
        "'github-issues' service: configure needs_services['github-issues'] (an empty "
        "entry is enough), or declare the 'issue' need type. [needs.load_service_need]"
    ]
    assert len(SphinxNeedsData(app.env).get_needs_view()) == 0


@responses.activate
def test_a_custom_github_service_with_its_built_in_configured_creates_its_needs(
    build: Any,
) -> None:
    """Configuring the built-in it imitates adds the type and the layout."""
    fake_enterprise_search()
    app = build(
        {
            "conf.py": ENTERPRISE_CONF + 'needs_services["github-issues"] = {}\n',
            "index.rst": ENTERPRISE_INDEX,
        }
    )
    assert_no_warnings(app)
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert [(need["type"], need["layout"]) for need in needs.values()] == [
        ("issue", "github")
    ]


@responses.activate
def test_an_unknown_type_of_another_cause_keeps_its_text(build: Any) -> None:
    """The hint is for a GitHub service's own type alone: a ``:type:`` the project
    does not declare is refused with today's text, built-in configured or not."""
    fake_enterprise_search()
    app = build(
        {
            "conf.py": ENTERPRISE_CONF,
            "index.rst": ENTERPRISE_INDEX + "   :type: nope\n",
        }
    )
    assert build_warnings(app) == [
        "<srcdir>/index.rst:6: WARNING: Service need could not be created: Unknown "
        "need type 'nope'. [needs.load_service_need]"
    ]
