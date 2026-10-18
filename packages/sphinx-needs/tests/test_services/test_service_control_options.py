"""A service's control options are the needservice directive's, not need fields.

``BaseService.options`` are the options of the ``needservice`` directive a service reads
-- request parameters, such as the GitHub services' ``query``, ``specific``,
``max_amount``, ``max_content_lines`` and ``id_prefix`` -- and ``BaseService.fields`` the
need fields its needs carry. The five used to be registered as need fields too, so every
need a GitHub service made carried them, and so did needs.json and its ``needs_schema``.
They are now accepted by the ``needservice`` of the service that reads them and nowhere
else, never copied onto a need, and dropped silently from an imported needs.json.

A class that declares ``options`` but no ``fields`` of its own (a service written for the
old meaning) keeps it, with one ``needs.deprecated`` warning: its options are registered
as need fields, as before.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any

import pytest
import responses

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import assert_no_warnings, build_warnings

RST = "Title\n=====\n\nText.\n"

CONF = (
    'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'
    # Sphinx's own warning that a class in the configuration is not pickled
    'suppress_warnings = ["config.cache"]\n'
)

#: ``github-issues`` configured, with no avatar to download
GH_CONF = CONF + 'needs_services = {"github-issues": {"download_avatars": False}}\n'

#: the needservice options of the GitHub services: request parameters
GITHUB_OPTIONS = ("query", "specific", "max_amount", "max_content_lines", "id_prefix")

#: the need fields of the GitHub services
GITHUB_FIELDS = ("user", "created_at", "updated_at", "closed_at", "service", "url")
GITHUB_IMAGE_FIELDS = ("avatar",)


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


def needs_json(app: Any) -> dict[str, Any]:
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf-8"))
    return data["versions"][data["current_version"]]


def schema_fields(app: Any) -> set[str]:
    return set(SphinxNeedsData(app.env).get_schema().iter_extra_field_names())


def deprecated(name: str, klass: str, options: list[str]) -> str:
    """The warning of a service class written for the old meaning of ``options``."""
    listed = ", ".join(repr(option) for option in options)
    return (
        f"WARNING: Service {name!r}: its class {klass!r} declares 'options' but no "
        f"'fields' of its own, so its options ({listed}) are registered as need "
        "fields. This is deprecated: from sphinx-needs 10.0 a service's 'options' are "
        "only the needservice options it reads; list the fields its needs carry in "
        "'fields' (an empty list will do) [needs.deprecated]"
    )


def control_option_hint(shown: str, name: str) -> str:
    """The text of the ``Unknown option`` warning for a GitHub control option set on a
    need or a needextend."""
    return (
        f"Unknown option '{shown}': {name!r} is an option of the needservice "
        "directive, a request parameter of the GitHub services, not a need field; set "
        f"it on a needservice, or declare a field {name!r} in needs_fields"
    )


# -- a GitHub service's needs --------------------------------------------------------------


def issue(number: int, body: str) -> dict[str, Any]:
    """A GitHub issue as the API returns it."""
    return {
        "number": number,
        "title": f"Issue {number}",
        "body": body,
        "state": "open",
        "labels": [],
        "user": {"login": "octo", "avatar_url": "https://avatars.example/u/1"},
        "html_url": f"https://github.com/o/r/issues/{number}",
        "created_at": "2020-01-01T00:00:00Z",
        "updated_at": "2020-01-02T00:00:00Z",
        "closed_at": None,
    }


BODY = "line one\nline two\nline three"

#: a search with every control option but ``specific``, and one ``specific`` request
GH_INDEX = (
    RST
    + """
.. needservice:: github-issues
   :query: repo:o/r
   :max_amount: 1
   :max_content_lines: 1
   :id_prefix: GHUB_

.. needservice:: github-issues
   :specific: o/r/8
"""
)


def fake_github() -> None:
    """The two requests ``GH_INDEX`` makes, each matched exactly: the search's query
    and page size, and the URL of the specific issue."""
    responses.get(
        "https://api.github.com/search/issues",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "repo:o/r is:issue", "per_page": "1"}
            )
        ],
        json={"items": [issue(7, BODY)]},
    )
    responses.get(
        "https://api.github.com/repos/o/r/issues/8",
        match=[responses.matchers.query_param_matcher({})],
        json=issue(8, BODY),
    )


@responses.activate
@pytest.mark.parametrize("all_data", [False, True], ids=["default", "service_all_data"])
def test_the_control_options_are_on_no_need_and_not_in_the_schema(
    build: Any, all_data: bool
) -> None:
    """The five are request parameters: no need of the service carries them, nor does
    needs.json's ``needs_schema``, while the seven data fields stay. With
    ``needs_service_all_data`` a datum's unknown keys go to the need's content, so the
    five must not reach the datum either."""
    fake_github()
    app = build(
        {
            "conf.py": GH_CONF + f"needs_service_all_data = {all_data}\n",
            "index.rst": GH_INDEX,
        }
    )
    assert_no_warnings(app)
    version = needs_json(app)
    assert sorted(version["needs"]) == ["GHUB_7", "GITHUB_8"]
    for need in version["needs"].values():
        assert set(GITHUB_OPTIONS).isdisjoint(need)
        assert set(GITHUB_FIELDS + GITHUB_IMAGE_FIELDS) <= set(need)
        assert need["user"] == "octo"
        for option in GITHUB_OPTIONS:
            assert f":{option}:" not in need["content"]
    properties = version["needs_schema"]["properties"]
    assert set(GITHUB_OPTIONS).isdisjoint(properties)
    assert set(GITHUB_FIELDS + GITHUB_IMAGE_FIELDS) <= set(properties)
    assert set(GITHUB_OPTIONS).isdisjoint(schema_fields(app))


@responses.activate
def test_the_control_options_still_drive_the_request(build: Any) -> None:
    """What the five do is unchanged: the search's ``q`` and ``per_page`` and the
    specific issue's URL (each request is matched exactly), the id prefix, and the
    truncation of the content to ``max_content_lines``."""
    fake_github()
    app = build({"conf.py": GH_CONF, "index.rst": GH_INDEX})
    assert_no_warnings(app)
    assert len(responses.calls) == 2
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["GHUB_7", "GITHUB_8"]
    assert "[...]" in needs["GHUB_7"]["content"]
    assert "line two" not in needs["GHUB_7"]["content"]
    assert "line three" in needs["GITHUB_8"]["content"]


@responses.activate
def test_a_field_of_a_control_option_name_is_not_set_by_the_needservice(
    build: Any,
) -> None:
    """A project's own field ``query`` is a field like any other, but on a needservice
    ``:query:`` is the service's request parameter: the control option wins, and the
    field is not set from it."""
    fake_github()
    app = build(
        {
            "conf.py": GH_CONF + "needs_fields = {'query': {'nullable': True}}\n",
            "index.rst": GH_INDEX,
        }
    )
    assert_no_warnings(app)
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert sorted(needs) == ["GHUB_7", "GITHUB_8"]
    assert [need["query"] for need in needs.values()] == [None, None]


# -- a control option where it is not one --------------------------------------------------


@pytest.mark.parametrize("conf", [CONF, GH_CONF], ids=["no-service", "github-issues"])
def test_a_control_option_on_a_need_says_it_belongs_to_a_needservice(
    build: Any, conf: str
) -> None:
    """``:query:`` on a need is not a field, whether a GitHub service is configured or
    not: the warning says what it is, and the two ways out."""
    app = build(
        {
            "conf.py": conf,
            "index.rst": RST + "\n.. req:: R\n   :id: R_001\n   :query: repo:o/r\n",
        }
    )
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:6: WARNING: {control_option_hint('query', 'query')} "
        "[needs.directive]"
    ]
    assert "query" not in SphinxNeedsData(app.env).get_needs_view()["R_001"]


@pytest.mark.parametrize("conf", [CONF, GH_CONF], ids=["no-service", "github-issues"])
def test_a_control_option_on_a_needextend_says_it_belongs_to_a_needservice(
    build: Any, conf: str
) -> None:
    app = build(
        {
            "conf.py": conf,
            "index.rst": RST
            + "\n.. req:: R\n   :id: R_001\n"
            + "\n.. needextend:: R_001\n   :max_amount: 3\n"
            + "\n.. needextend:: R_001\n   :+id_prefix: GH_\n",
        }
    )
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:9: WARNING: {control_option_hint('max_amount', 'max_amount')} "
        "[needs.needextend]",
        f"<srcdir>/index.rst:12: WARNING: {control_option_hint('+id_prefix', 'id_prefix')} "
        "[needs.needextend]",
    ]


def test_a_field_of_a_control_option_name_is_a_field_on_a_need(build: Any) -> None:
    """The hint is for a name no field has: a project's own ``query`` is set as any
    field is."""
    app = build(
        {
            "conf.py": CONF + "needs_fields = {'query': {'nullable': True}}\n",
            "index.rst": RST + "\n.. req:: R\n   :id: R_001\n   :query: repo:o/r\n",
        }
    )
    assert_no_warnings(app)
    assert SphinxNeedsData(app.env).get_needs_view()["R_001"]["query"] == "repo:o/r"


def test_a_field_of_a_control_option_name_on_another_type_gives_no_hint(
    build: Any,
) -> None:
    """A field ``query`` the ``spec`` type alone declares is a field of the project,
    so on a ``req`` it is refused as any field absent from a type is, and the hint,
    which would tell the project to declare it, is not given."""
    app = build(
        {
            "conf.py": CONF
            + "needs_types = [\n"
            + "    {'directive': 'req', 'title': 'Req', 'prefix': 'R_'},\n"
            + "    {'directive': 'spec', 'title': 'Spec', 'prefix': 'S_',\n"
            + "     'fields': {'query': {'schema': {'type': 'string'}}}},\n"
            + "]\n",
            "index.rst": RST + "\n.. req:: R\n   :id: R_001\n   :query: repo:o/r\n",
        }
    )
    assert build_warnings(app) == [
        "<srcdir>/index.rst:6: WARNING: Field 'query' is not declared on need type "
        "'req' and cannot be set in need 'R_001'; the value 'repo:o/r' is ignored "
        "[needs.undeclared_for_type]"
    ]


#: a service of the new kind that reads no option, beside ``github-issues``
PLAIN_SERVICE = """
from sphinx_needs.services.base import BaseService


class Plain(BaseService):
    options = []
    fields = []

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return []


needs_services["plain"] = {"class": Plain, "class_init": {}}
"""


def test_a_github_control_option_on_another_service_is_unknown(build: Any) -> None:
    """The five are the GitHub services' options: a needservice of another service
    does not accept them, a GitHub service configured or not."""
    app = build(
        {
            "conf.py": GH_CONF + PLAIN_SERVICE,
            "index.rst": RST + "\n.. needservice:: plain\n   :query: repo:o/r\n",
        }
    )
    assert build_warnings(app) == [
        "<srcdir>/index.rst:6: WARNING: Unknown option 'query' [needs.directive]"
    ]


# -- a needs.json written by an earlier version ------------------------------------------


def old_needs_json(**values: Any) -> str:
    """A needs.json as the version before wrote it for a GitHub service's need: the
    five control keys with their values, the seven data keys."""
    need = {
        "id": "OLD_1",
        "title": "Old",
        "type": "req",
        "query": "repo:o/r",
        "specific": None,
        "max_amount": "2",
        "max_content_lines": "4",
        "id_prefix": "GH_",
        **dict.fromkeys(GITHUB_FIELDS + GITHUB_IMAGE_FIELDS),
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


def import_project(reader: str, conf: str) -> dict[str, str]:
    extra_conf, directive = READERS[reader]
    return {
        "conf.py": conf + extra_conf,
        "index.rst": RST + directive,
        "old.json": old_needs_json(),
    }


@pytest.mark.parametrize("conf", [CONF, GH_CONF], ids=["no-service", "github-issues"])
@pytest.mark.parametrize("reader", list(READERS))
def test_an_old_needs_json_drops_the_control_keys_silently(
    build: Any, reader: str, conf: str
) -> None:
    """Every needs.json written with a GitHub service configured carries the five on
    its needs, with the values of the directive that made them: request parameters of
    that build, not data, so they are dropped without a warning, whatever their value
    and whether a service is configured or not."""
    app = build(import_project(reader, conf))
    assert_no_warnings(app)
    need = SphinxNeedsData(app.env).get_needs_view()["OLD_1"]
    assert set(GITHUB_OPTIONS).isdisjoint(need.keys())


@pytest.mark.parametrize("reader", list(READERS))
def test_a_field_of_a_control_option_name_is_imported(build: Any, reader: str) -> None:
    """A project's own field ``query`` is known, so it is imported as any field is."""
    app = build(
        import_project(reader, CONF + "needs_fields = {'query': {'nullable': True}}\n")
    )
    assert_no_warnings(app)
    need = SphinxNeedsData(app.env).get_needs_view()["OLD_1"]
    assert need["query"] == "repo:o/r"
    assert "max_amount" not in need.keys()


# -- service classes: options and fields ----------------------------------------------------


def service_conf(code: str, entry: str) -> str:
    return CONF + code + f"\nneeds_services = {{{entry}}}\n"


LEGACY = """
from sphinx_needs.services.base import BaseService


class Legacy(BaseService):
    options = ["custom_option", "type", "exists"]

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return []
"""


def test_a_class_without_fields_registers_its_options_as_fields_and_warns_once(
    build: Any,
) -> None:
    """The old meaning, kept for a class written for it: its options but ``type`` are
    need fields. One warning per service, at its registration, however many
    needservice directives name it."""
    app = build(
        {
            "conf.py": service_conf(
                LEGACY, '"legacy": {"class": Legacy, "class_init": {}}'
            ),
            "index.rst": RST
            + "\n.. needservice:: legacy\n   :exists: yes\n"
            + "\n.. needservice:: legacy\n   :custom_option: yes\n",
        }
    )
    assert build_warnings(app) == [
        deprecated("legacy", "Legacy", ["custom_option", "exists"])
    ]
    assert {"custom_option", "exists"} <= schema_fields(app)


def test_a_class_without_fields_and_without_options_does_not_warn(
    build: Any,
) -> None:
    """Nothing is registered by the old meaning, so there is nothing to warn about."""
    app = build(
        {
            "conf.py": service_conf(
                LEGACY.replace('["custom_option", "type", "exists"]', '["type"]'),
                '"legacy": {"class": Legacy, "class_init": {}}',
            )
        }
    )
    assert_no_warnings(app)


GITHUB_SUBCLASS = """
from sphinx_needs.services.github import GithubService


class MyGithub(GithubService):
    options = [*GithubService.options, "label"]
"""


def test_a_github_subclass_adding_options_without_fields_is_legacy(
    build: Any,
) -> None:
    """Its ``options`` are declared below the class declaring ``fields``, so they were
    written for the old meaning: they are registered as fields, beside the fields it
    inherits, with the warning."""
    app = build(
        {
            "conf.py": service_conf(
                GITHUB_SUBCLASS,
                '"mine": {"class": MyGithub, "class_init": {"gh_type": "issue"}}',
            )
        }
    )
    assert build_warnings(app) == [
        deprecated("mine", "MyGithub", [*GITHUB_OPTIONS, "label"])
    ]
    assert {"label", *GITHUB_OPTIONS, *GITHUB_FIELDS} <= schema_fields(app)


FACTORY = """
class Made:
    def __init__(self, app, name, config, **kwargs):
        pass

    def request_from_directive(self, directive):
        options = directive.options
        return [{"id": "MADE_1", "title": "Made", "made_field": options["made_option"]}]


def factory(app, name, config, **kwargs):
    return Made(app, name, config, **kwargs)


factory.options = ["made_option"]
factory.fields = ["made_field"]
"""


def test_a_factory_with_fields_is_of_the_new_kind(build: Any) -> None:
    """A callable carrying ``fields`` declares both: its ``fields`` are registered,
    and its ``options`` are options of its needservice, not fields."""
    app = build(
        {
            "conf.py": service_conf(
                FACTORY, '"made": {"class": factory, "class_init": {}}'
            ),
            "index.rst": RST + "\n.. needservice:: made\n   :made_option: given\n",
        }
    )
    assert_no_warnings(app)
    fields = schema_fields(app)
    assert "made_field" in fields
    assert "made_option" not in fields
    need = SphinxNeedsData(app.env).get_needs_view()["MADE_1"]
    assert need["made_field"] == "given"
    assert "made_option" not in need.keys()


# -- the documentation's own-service example (#2327) -----------------------------------------

SERVICES_DOC = Path(__file__).parents[2] / "docs" / "services" / "index.rst"


def code_blocks(text: str, language: str) -> list[str]:
    """The ``code-block`` directives of the language in an rst text, dedented."""
    blocks = []
    pattern = rf"^\.\. code-block:: {language}\n\n((?:(?: {{3,}}.*)?\n)+)"
    for match in re.finditer(pattern, text, flags=re.MULTILINE):
        blocks.append(textwrap.dedent(match.group(1)))
    return blocks


def test_the_own_service_example_of_the_documentation_works(build: Any) -> None:
    """The class, its configuration and its directives, as ``docs/services/index.rst``
    shows them under *Own services*, build without a warning and create the needs the
    page says they do."""
    own = SERVICES_DOC.read_text("utf-8").split("\nOwn services\n", 1)[1]
    service_class, configuration = code_blocks(own, "python")[:2]
    usage = code_blocks(own, "rst")[0]
    configuration = "\n".join(
        line for line in configuration.splitlines() if "import MyService" not in line
    )
    app = build(
        {
            "conf.py": CONF + service_class + "\n" + configuration + "\n",
            "index.rst": RST + "\n" + usage,
        }
    )
    assert_no_warnings(app)
    needs = SphinxNeedsData(app.env).get_needs_view()
    by_title = {need["title"]: need for need in needs.values()}
    assert sorted(by_title) == ["My Issue 1", "My Issue 2"]
    assert by_title["My Issue 1"]["status"] == "open"
    assert by_title["My Issue 1"]["origin"] == "Awesome"
    assert by_title["My Issue 2"]["type"] == "spec"
