"""A directive option matches a declared field, link type or core field ignoring case.

docutils lowercases the name of every reStructuredText directive option before a directive
sees it; myst-parser hands the name over as written. Matching the declared names exactly
therefore made a field declared with capitals (``needs_fields = {"Owner": {}}``)
unreachable from reStructuredText, and made MyST's ``:Status:`` an unknown option where
reStructuredText's is ``status``: the same project read differently per markup.

The rule, in both hosts and for the need directives, ``needextend`` and ``needservice``:
an option matches the declared name equal to it ignoring case (``str.lower``, as docutils
compares), and its value is stored under the DECLARED spelling, which ``needs.json``,
filters and tables keep. Two declared names equal ignoring case are a configuration error.

The change is additive: an option that matched before still matches the same name (an
exact spelling is tried first), so only an option that used to be an unknown one, with
its value lost, now lands. Where MyST writes one name twice in two cases, the spelling
that matched before keeps its value and the other is reported and ignored.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs_testkit import build_warnings

HOSTS = ("rst", "myst")

CONF = """\
extensions = ["sphinx_needs", "myst_parser"]
needs_types = [dict(directive="req", title="Req", prefix="R_")]
needs_id_regex = ".*"
"""

CAPITALS = (
    CONF
    + """\
needs_fields = {"Owner": {"nullable": True}, "team": {"nullable": True}}
needs_links = {"Satisfies": {}}
"""
)


def _directive(
    host: str, name: str, argument: str, options: Sequence[tuple[str, str]]
) -> str:
    """A directive in the host's syntax, with its options written as given."""
    if host == "rst":
        lines = [f".. {name}:: {argument}"]
        lines += [f"   :{key}: {value}".rstrip() for key, value in options]
        return "\n".join(lines) + "\n\n"
    lines = [f"```{{{name}}} {argument}"]
    lines += [f":{key}: {value}".rstrip() for key, value in options]
    return "\n".join([*lines, "```"]) + "\n\n"


def _build(
    make_app: Any, tmp_path: Path, host: str, body: str, conf: str = CAPITALS
) -> Any:
    """Build a one-page project of the host's markup; return the application."""
    (tmp_path / "conf.py").write_text(conf, encoding="utf-8")
    if host == "rst":
        (tmp_path / "index.rst").write_text("Probe\n=====\n\n" + body, encoding="utf-8")
    else:
        (tmp_path / "index.md").write_text("# Probe\n\n" + body, encoding="utf-8")
    app = make_app("needs", srcdir=tmp_path, freshenv=True)
    app.build()
    return app


def _needs(app: Any) -> dict[str, Any]:
    """The needs as the build's ``needs.json`` holds them."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _warnings(app: Any) -> list[str]:
    return build_warnings(app)


# -- a field declared with capitals -------------------------------------------------


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("written", ["Owner", "owner", "OWNER"])
def test_a_field_declared_with_capitals_is_set_by_any_case(
    make_app: Any, tmp_path: Path, host: str, written: str
) -> None:
    """``Owner`` is set by ``:Owner:``, ``:owner:`` and ``:OWNER:`` alike, and kept
    under the declared spelling. Before: reStructuredText warned ``Unknown option
    'owner'`` for every spelling (docutils lowercases the name); MyST took ``:Owner:``
    alone."""
    app = _build(
        make_app,
        tmp_path,
        host,
        _directive(host, "req", "One", [("id", "R_1"), (written, "bob")]),
    )
    assert _warnings(app) == []
    need = _needs(app)["R_1"]
    assert need["Owner"] == "bob"
    assert "owner" not in need


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("written", ["team", "Team", "TEAM"])
def test_a_lowercase_field_is_set_by_any_case(
    make_app: Any, tmp_path: Path, host: str, written: str
) -> None:
    """A field declared in lower case, set by a capitalised option: reStructuredText
    already lowercased it; MyST's ``:Team:`` was an unknown option."""
    app = _build(
        make_app,
        tmp_path,
        host,
        _directive(host, "req", "One", [("id", "R_1"), (written, "alpha")]),
    )
    assert _warnings(app) == []
    assert _needs(app)["R_1"]["team"] == "alpha"


# -- a link type declared with capitals -----------------------------------------------


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("written", ["Satisfies", "satisfies"])
def test_a_link_type_declared_with_capitals_is_set_by_any_case(
    make_app: Any, tmp_path: Path, host: str, written: str
) -> None:
    app = _build(
        make_app,
        tmp_path,
        host,
        _directive(host, "req", "Zero", [("id", "R_0")])
        + _directive(host, "req", "One", [("id", "R_1"), (written, "R_0")]),
    )
    assert _warnings(app) == []
    needs = _needs(app)
    assert needs["R_1"]["Satisfies"] == ["R_0"]
    assert needs["R_0"]["Satisfies_back"] == ["R_1"]


# -- core fields --------------------------------------------------------------------


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("written", ["Status", "STATUS", "status"])
def test_a_core_field_is_set_by_any_case(
    make_app: Any, tmp_path: Path, host: str, written: str
) -> None:
    """MyST's ``:Status:`` sets ``status``, as reStructuredText's always did."""
    app = _build(
        make_app,
        tmp_path,
        host,
        _directive(
            host, "req", "One", [("ID", "R_1"), (written, "open"), ("Tags", "a, b")]
        ),
    )
    assert _warnings(app) == []
    need = _needs(app)["R_1"]
    assert need["status"] == "open"
    assert need["tags"] == ["a", "b"]


# -- needextend ---------------------------------------------------------------------


@pytest.mark.parametrize("host", HOSTS)
def test_needextend_matches_its_keys_ignoring_case(
    make_app: Any, tmp_path: Path, host: str
) -> None:
    """A ``needextend`` key, ``+``/``-`` prefix and all, matches ignoring case: the
    declared ``Owner`` and ``Satisfies``, the core ``status`` and ``tags``."""
    body = (
        _directive(host, "req", "Zero", [("id", "R_0")])
        + _directive(host, "req", "One", [("id", "R_1"), ("tags", "a")])
        + _directive(
            host,
            "needextend",
            "R_1",
            [
                ("Owner", "carol"),
                ("+Satisfies", "R_0"),
                ("Status", "done"),
                ("+TAGS", "b"),
            ],
        )
    )
    app = _build(make_app, tmp_path, host, body)
    assert _warnings(app) == []
    need = _needs(app)["R_1"]
    assert need["Owner"] == "carol"
    assert need["Satisfies"] == ["R_0"]
    assert need["status"] == "done"
    assert need["tags"] == ["a", "b"]


@pytest.mark.parametrize("host", HOSTS)
def test_needextend_options_of_its_own_match_ignoring_case(
    make_app: Any, tmp_path: Path, host: str
) -> None:
    """``:Strict: false`` is ``needextend``'s own ``strict``, not an unknown option:
    the missing need is a warning, where ``needextend_strict`` would stop the build."""
    body = _directive(host, "req", "One", [("id", "R_1")]) + _directive(
        host, "needextend", "R_NOPE", [("Strict", "false")]
    )
    app = _build(
        make_app, tmp_path, host, body, conf=CAPITALS + "needextend_strict = True\n"
    )
    warnings = _warnings(app)
    assert len(warnings) == 1
    assert "Provided id 'R_NOPE' for needextend does not exist." in warnings[0]


# -- what does not change -----------------------------------------------------------


@pytest.mark.parametrize("host", HOSTS)
def test_an_unknown_option_is_still_unknown(
    make_app: Any, tmp_path: Path, host: str
) -> None:
    app = _build(
        make_app,
        tmp_path,
        host,
        _directive(host, "req", "One", [("id", "R_1"), ("Bogus", "x")]),
    )
    written = "bogus" if host == "rst" else "Bogus"
    warnings = _warnings(app)
    assert len(warnings) == 1
    assert f"Unknown option '{written}'" in warnings[0]
    assert "R_1" in _needs(app)


@pytest.mark.parametrize(
    ("options", "kept", "ignored"),
    [
        ([("status", "open"), ("Status", "closed")], "open", "Status"),
        ([("Status", "closed"), ("status", "open")], "open", "Status"),
        ([("STATUS", "open"), ("Status", "closed")], "open", "Status"),
    ],
    ids=["exact-first", "exact-second", "neither-exact"],
)
def test_myst_writing_one_core_field_twice_keeps_the_value_set_before(
    make_app: Any,
    tmp_path: Path,
    options: list[tuple[str, str]],
    kept: str,
    ignored: str,
) -> None:
    """MyST may write one name twice in two cases (reStructuredText refuses that as a
    duplicate option). The spelling that matched before keeps its value -- the exact
    one, else the first written -- and the other is reported and ignored, so no value
    set before changes."""
    app = _build(
        make_app,
        tmp_path,
        "myst",
        _directive("myst", "req", "One", [("id", "R_1"), *options]),
    )
    assert _needs(app)["R_1"]["status"] == kept
    warnings = _warnings(app)
    assert len(warnings) == 1
    assert f"'{ignored}'" in warnings[0]


def test_myst_writing_a_capitalised_field_twice_keeps_the_declared_spelling(
    make_app: Any, tmp_path: Path
) -> None:
    """MyST ``:Owner: a`` set ``Owner`` before and ``:owner: b`` was unknown: it still
    is ``a``, and ``owner`` is reported."""
    app = _build(
        make_app,
        tmp_path,
        "myst",
        _directive(
            "myst", "req", "One", [("id", "R_1"), ("owner", "b"), ("Owner", "a")]
        ),
    )
    assert _needs(app)["R_1"]["Owner"] == "a"
    warnings = _warnings(app)
    assert len(warnings) == 1
    assert "'owner'" in warnings[0]


# -- needservice --------------------------------------------------------------------

SERVICE = (
    CAPITALS
    + """\
from sphinx_needs.services.base import BaseService

class EchoService(BaseService):
    options = ["Query"]

    def __init__(self, app, name, config, **kwargs):
        super().__init__()

    def request(self, options):
        return [
            {"id": "S_1", "title": "From the service", "type": "req",
             "Owner": options.get("Owner"), "content": options.get("Query", "")}
        ]

needs_services = {"echo": {"class": EchoService, "class_init": {}}}
suppress_warnings = ["config.cache"]
"""
)


@pytest.mark.parametrize("host", HOSTS)
def test_needservice_hands_the_service_the_declared_spelling(
    make_app: Any, tmp_path: Path, host: str
) -> None:
    """The service reads its options by the declared names: ``:query:`` and ``:owner:``
    reach it as ``Query`` and ``Owner``."""
    app = _build(
        make_app,
        tmp_path,
        host,
        _directive(host, "needservice", "echo", [("query", "q"), ("owner", "dan")]),
        conf=SERVICE,
    )
    assert [w for w in _warnings(app) if "unpickl" not in w] == []
    assert _needs(app)["S_1"]["Owner"] == "dan"


# -- two declared names equal ignoring case -----------------------------------------


def _refused(make_app: Any, tmp_path: Path, conf: str) -> str:
    """The configuration error a project of ``conf`` stops with."""
    (tmp_path / "conf.py").write_text(conf, encoding="utf-8")
    (tmp_path / "index.rst").write_text("Probe\n=====\n", encoding="utf-8")
    with pytest.raises(NeedsConfigException) as exc_info:
        app = make_app("html", srcdir=tmp_path, freshenv=True)
        app.build()
    return str(exc_info.value)


CLASHES = {
    "field-field": (
        'needs_fields = {"Owner": {}, "owner": {}}\n',
        ("field 'Owner' (from needs_fields)", "field 'owner' (from needs_fields)"),
    ),
    "field-core": (
        'needs_fields = {"Status": {}}\n',
        ("field 'Status' (from needs_fields)", "core field 'status'"),
    ),
    "extra_option-core": (
        'needs_extra_options = ["ID"]\n',
        ("field 'ID' (from needs_extra_options)", "core field 'id'"),
    ),
    "field-link": (
        'needs_fields = {"satisfies": {}}\nneeds_links = {"Satisfies": {}}\n',
        ("field 'satisfies' (from needs_fields)", "link type 'Satisfies'"),
    ),
    "link-link": (
        'needs_links = {"Satisfies": {}}\n'
        'needs_extra_links = [{"option": "satisfies"}]\n',
        ("link type 'Satisfies'", "link type 'satisfies'"),
    ),
    "link-core_link": (
        'needs_links = {"Links": {}}\n',
        ("link type 'Links'", "core link type 'links'"),
    ),
    "link-back_links": (
        'needs_links = {"tests": {}, "Tests_Back": {}}\n',
        ("link type 'Tests_Back'", "'tests_back', the back links of link type 'tests'"),
    ),
    "field-back_links": (
        'needs_links = {"Tests": {}}\nneeds_fields = {"tests_back": {}}\n',
        ("field 'tests_back'", "'Tests_back', the back links of link type 'Tests'"),
    ),
    "type_field-field": (
        'needs_fields = {"owner": {}}\n'
        'needs_types = [dict(directive="req", title="Req", prefix="R_",'
        ' fields={"Owner": {"schema": {"type": "string"}}})]\n',
        ("field 'Owner' (from needs_types)", "field 'owner' (from needs_fields)"),
    ),
    "type_link-link": (
        'needs_links = {"satisfies": {}}\n'
        'needs_types = [dict(directive="req", title="Req", prefix="R_",'
        ' links={"Satisfies": {}})]\n',
        ("link type 'Satisfies' (from needs_types)", "link type 'satisfies'"),
    ),
    "field-directive_option": (
        'needs_fields = {"Strict": {}}\n',
        ("field 'Strict' (from needs_fields)", "the directive option 'strict'"),
    ),
}


@pytest.mark.parametrize("clash", CLASHES)
def test_two_names_equal_ignoring_case_are_a_configuration_error(
    make_app: Any, tmp_path: Path, clash: str
) -> None:
    conf, named = CLASHES[clash]
    message = _refused(make_app, tmp_path, CONF + conf)
    for text in named:
        assert text in message
    assert "ignoring case" in message


@pytest.mark.parametrize(
    "conf",
    [
        'needs_fields = {"status": {"schema": {"enum": ["open", "done"]}}}\n',
        'needs_fields = {"Owner": {}}\nneeds_links = {"Satisfies": {}}\n',
        'needs_fields = {"strict": {}, "delete": {}}\n',
    ],
    ids=["core-specialisation", "capitals", "exact-directive-options"],
)
def test_names_spelt_alike_or_apart_are_no_case_clash(
    make_app: Any, tmp_path: Path, conf: str
) -> None:
    """An entry naming a core field exactly specialises it, as before; names equal
    only exactly to a directive's own option keep what they did before (no new error)."""
    (tmp_path / "conf.py").write_text(CONF + conf, encoding="utf-8")
    (tmp_path / "index.rst").write_text("Probe\n=====\n", encoding="utf-8")
    app = make_app("html", srcdir=tmp_path, freshenv=True)
    app.build()
    assert [w for w in _warnings(app) if "ignoring case" in w] == []
