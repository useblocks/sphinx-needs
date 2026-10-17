"""A changed ``needs_types`` entry is applied on an incremental build (#2287).

``needs_types`` is registered with ``rebuild = "html"``, so a change to it re-read no
document, and the needs of every unchanged document kept what the previous entries gave
them. Since a need type declares fields, link types, their defaults and ``derive`` rules,
and its ``title`` and ``prefix`` are stored on each need, a changed entry changes need
data: the needs an incremental build ends with now equal those of a fresh build.

The option itself stays ``"html"``: it holds the configured need types only, while those
added from code (``add_need_type``, the GitHub services) are kept in sphinx-needs'
registry, so ``"env"`` would not see a change to them. The complete list is compared
instead, and an unchanged list re-reads nothing more than the changed documents.
"""

from __future__ import annotations

import json
import pickle
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import responses
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs_testkit import build_warnings

INDEX = """\
Index
=====

.. toctree::

   other

.. req:: A title
   :id: REQ_001
   :label: authored

.. spec:: A spec
   :id: SPEC_001
"""

OTHER = "Other\n=====\n\nText.\n"


def conf(req: str = "", spec: str = "", fields: str = "") -> str:
    """A ``conf.py`` with a ``req`` and a ``spec`` type, each entry extended by its text."""
    return f"""\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_fields = {{{fields}}}
needs_types = [
    {{"directive": "req", "title": "Requirement", "prefix": "R_", {req}}},
    {{"directive": "spec", "title": "Specification", "prefix": "S_", {spec}}},
]
"""


#: ``label`` declared on ``req`` alone, without and with a ``derive`` rule
LABEL = '"fields": {"label": {"schema": {"type": "string"}}}'
LABEL_DERIVED = (
    '"fields": {"label": {"schema": {"type": "string"}, '
    '"derive": {"kind": "copy", "field": "title"}}}'
)
#: a field of the project, which ``req`` gives a default
GLOBAL_LABEL = '"label": {"schema": {"type": "string"}, "nullable": True}'
LABEL_DEFAULT = '"fields": {"label": {"default": "from the type"}}'

CASES = {
    "derive-removed": (conf(req=LABEL_DERIVED), conf(req=LABEL)),
    "derive-added": (conf(req=LABEL), conf(req=LABEL_DERIVED)),
    "field-default-added": (
        conf(fields=GLOBAL_LABEL),
        conf(fields=GLOBAL_LABEL, spec=LABEL_DEFAULT),
    ),
    "inherits-added": (
        conf(fields=GLOBAL_LABEL, req=LABEL_DEFAULT),
        conf(fields=GLOBAL_LABEL, req=LABEL_DEFAULT, spec='"inherits": "req"'),
    ),
    "link-default-added": (
        conf(req=LABEL),
        conf(req=LABEL, spec='"links": {"links": {"default": ["REQ_001"]}}'),
    ),
    "title-changed": (
        conf(req=LABEL),
        conf(req=LABEL).replace('"Specification"', '"Spec"'),
    ),
}


def _write(srcdir: Path, conf_py: str) -> Path:
    srcdir.mkdir(parents=True, exist_ok=True)
    for name, text in {
        "conf.py": conf_py,
        "index.rst": INDEX,
        "other.rst": OTHER,
    }.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    return srcdir


def _needs(app: SphinxTestApp) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


def _read_docs(app: SphinxTestApp) -> list[str]:
    """The documents the build read, from its ``reading sources`` lines."""
    status = strip_colors(app._status.getvalue())
    return re.findall(r"reading sources\.\.\. \[\s*\d+%\] (\S+)", status)


def _build(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, *, fresh: bool
) -> tuple[dict[str, dict[str, Any]], list[str], list[str]]:
    """Build, and return the needs, the warnings and the documents read."""
    app = make_app("html", srcdir=srcdir, freshenv=fresh)
    try:
        app.build()
        return _needs(app), build_warnings(app), _read_docs(app)
    finally:
        app.cleanup()


@pytest.mark.parametrize(("before", "after"), CASES.values(), ids=CASES.keys())
def test_changed_type_entry_is_applied_on_incremental_build(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, before: str, after: str
) -> None:
    """The needs of an incremental build after the change equal a fresh build's."""
    srcdir = _write(tmp_path / "incremental", before)
    _build(make_app, srcdir, fresh=True)
    (srcdir / "conf.py").write_text(after, encoding="utf-8")
    incremental, incremental_warnings, read = _build(make_app, srcdir, fresh=False)

    fresh, fresh_warnings, _ = _build(
        make_app, _write(tmp_path / "fresh", after), fresh=True
    )
    assert incremental == fresh
    assert incremental_warnings == fresh_warnings
    assert sorted(read) == ["index", "other"]


def test_derive_removed_restores_the_authored_value(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The issue's measurement: the field held ``None``, a fresh build the authored value."""
    srcdir = _write(tmp_path / "src", conf(req=LABEL_DERIVED))
    needs, _, _ = _build(make_app, srcdir, fresh=True)
    assert needs["REQ_001"]["label"] == "A title"
    (srcdir / "conf.py").write_text(conf(req=LABEL), encoding="utf-8")
    needs, warnings, _ = _build(make_app, srcdir, fresh=False)
    assert needs["REQ_001"]["label"] == "authored"
    assert warnings == []


def test_unchanged_types_reread_only_changed_documents(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """An unchanged ``needs_types`` adds no document to an incremental build.

    The GitHub services' need types are in the list compared on every build, so the
    comparison sees them on both sides rather than re-reading everything each time.
    """
    srcdir = _write(tmp_path / "src", conf(req=LABEL_DERIVED))
    _build(make_app, srcdir, fresh=True)
    (srcdir / "other.rst").write_text(OTHER + "\nMore text.\n", encoding="utf-8")
    _, warnings, read = _build(make_app, srcdir, fresh=False)
    assert read == ["other"]
    assert warnings == []
    _, _, read = _build(make_app, srcdir, fresh=False)
    assert read == []


def test_type_change_with_no_document_edited(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Only ``conf.py`` changes, so Sphinx itself would re-read no document.

    The type's new prefix reaches the id generated for a need of the unchanged page.
    """
    srcdir = _write(tmp_path / "src", conf(req=LABEL))
    (srcdir / "other.rst").write_text(OTHER + "\n.. spec:: No id\n", encoding="utf-8")
    needs, _, _ = _build(make_app, srcdir, fresh=True)
    [generated] = [need_id for need_id in needs if need_id.startswith("S_")]
    (srcdir / "conf.py").write_text(
        conf(req=LABEL).replace('"prefix": "S_"', '"prefix": "SP_"'), encoding="utf-8"
    )
    needs, warnings, read = _build(make_app, srcdir, fresh=False)
    assert sorted(read) == ["index", "other"]
    assert "SP_" + generated.removeprefix("S_") in needs
    assert generated not in needs
    assert warnings == []


def test_environment_without_the_record_rereads_once(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """An environment pickled before the need types were recorded re-reads every
    document on its first incremental build, and records them, so the next reads none."""
    srcdir = _write(tmp_path / "src", conf(req=LABEL))
    app = make_app("html", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        pickled = Path(app.doctreedir, "environment.pickle")
    finally:
        app.cleanup()
    env = pickle.loads(pickled.read_bytes())
    del env._needs_types_read_with
    pickled.write_bytes(pickle.dumps(env, pickle.HIGHEST_PROTOCOL))

    _, warnings, read = _build(make_app, srcdir, fresh=False)
    assert sorted(read) == ["index", "other"]
    assert warnings == []
    _, _, read = _build(make_app, srcdir, fresh=False)
    assert read == []


#: an extension's need type, added from code: not part of the ``needs_types`` value
ADDED_TYPE_CONF = """\
from sphinx_needs.api import add_need_type

extensions = ["sphinx_needs"]
needs_build_json = True


def setup(app):
    app.connect(
        "config-inited",
        lambda app, config: add_need_type(app, "ext", "{title}", "E_"),
        priority=500,
    )
"""


def test_change_to_a_type_added_from_code_is_applied(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A type added with ``add_need_type`` is not in the ``needs_types`` value, so no
    configuration value changes with it; the complete list compared still does."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(ADDED_TYPE_CONF.format(title="Before"), "utf-8")
    (srcdir / "index.rst").write_text(
        "Index\n=====\n\n.. toctree::\n\n   other\n\n.. ext:: Added\n   :id: E_001\n",
        "utf-8",
    )
    (srcdir / "other.rst").write_text(OTHER, "utf-8")
    needs, _, _ = _build(make_app, srcdir, fresh=True)
    assert needs["E_001"]["type_name"] == "Before"
    (srcdir / "conf.py").write_text(ADDED_TYPE_CONF.format(title="After"), "utf-8")
    needs, warnings, read = _build(make_app, srcdir, fresh=False)
    assert sorted(read) == ["index", "other"]
    assert needs["E_001"]["type_name"] == "After"
    assert warnings == []


# -- the configured built-in GitHub services ------------------------------------------------

#: the project declares its own ``issue`` type, so configuring or removing the
#: ``github-issues`` service leaves the list of need types as it is
OWN_ISSUE_CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {"directive": "issue", "title": "Issue", "prefix": "I_"},
]
"""

#: ``github-issues`` configured, with no avatar download: one search request
SERVICE = 'needs_services = {"github-issues": {"download_avatars": False}}\n'

SERVICE_INDEX = """\
Index
=====

.. toctree::

   other

.. req:: A title
   :id: REQ_001

.. needservice:: github-issues
   :query: repo:o/r
   :max_amount: 1
"""

#: a GitHub issue as the search API returns it
ISSUE = {
    "number": 7,
    "title": "An issue",
    "body": "Its body",
    "state": "open",
    "labels": [],
    "user": {"login": "octo", "avatar_url": "https://avatars.example/u/1"},
    "html_url": "https://github.com/o/r/issues/7",
    "created_at": "2020-01-01T00:00:00Z",
    "updated_at": "2020-01-02T00:00:00Z",
    "closed_at": None,
}


def _service_project(srcdir: Path, conf_py: str, index: str) -> Path:
    srcdir.mkdir(parents=True, exist_ok=True)
    for name, text in {
        "conf.py": conf_py,
        "index.rst": index,
        "other.rst": OTHER,
    }.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    return srcdir


def _fake_search() -> None:
    responses.get(
        "https://api.github.com/search/issues",
        match=[
            responses.matchers.query_param_matcher(
                {"q": "repo:o/r is:issue", "per_page": "1"}
            )
        ],
        json={"items": [ISSUE]},
    )


@responses.activate
def test_removing_a_built_in_service_rereads_every_document(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The service's need, and every field it registered, go with the service: the
    pickled need of the unchanged page is not rendered in a layout that is gone, which
    ended the build with ``Given layout "github" is unknown``."""
    _fake_search()
    srcdir = _service_project(tmp_path / "src", OWN_ISSUE_CONF + SERVICE, SERVICE_INDEX)
    needs, warnings, _ = _build(make_app, srcdir, fresh=True)
    assert (sorted(needs), warnings) == (["GITHUB_7", "REQ_001"], [])
    (srcdir / "conf.py").write_text(OWN_ISSUE_CONF, encoding="utf-8")
    needs, warnings, read = _build(make_app, srcdir, fresh=False)
    assert sorted(read) == ["index", "other"]
    assert sorted(needs) == ["REQ_001"]
    assert "url" not in needs["REQ_001"]
    assert warnings == [
        "<srcdir>/index.rst:11: WARNING: Service 'github-issues' is a built-in service "
        "that is not configured, so it is not registered: name it in needs_services to "
        'use it, e.g. needs_services = {"github-issues": {}} in conf.py, or a '
        "[needs.services.github-issues] table in the needs_from_toml file "
        "[needs.load_service_need]"
    ]


#: an index with a need of the project's own type, and no service
PLAIN_INDEX = (
    "Index\n=====\n\n.. toctree::\n\n   other\n\n.. req:: A title\n   :id: REQ_001\n"
)


def test_adding_a_built_in_service_rereads_every_document(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The needs of an unchanged page gain the service's fields, as in a fresh build."""
    srcdir = _service_project(tmp_path / "src", OWN_ISSUE_CONF, PLAIN_INDEX)
    needs, _, _ = _build(make_app, srcdir, fresh=True)
    assert "url" not in needs["REQ_001"]
    (srcdir / "conf.py").write_text(OWN_ISSUE_CONF + SERVICE, encoding="utf-8")
    needs, warnings, read = _build(make_app, srcdir, fresh=False)
    assert sorted(read) == ["index", "other"]
    assert needs["REQ_001"]["url"] is None
    assert warnings == []
    _, _, read = _build(make_app, srcdir, fresh=False)
    assert read == []


def test_environment_without_the_services_record_rereads_once(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """An environment pickled before the configured built-in services were recorded --
    by a version that registered them in every build, so its needs may carry their
    fields -- re-reads every document on its first incremental build, and records
    them, so the next reads none. The project's own ``issue`` keeps the type list as it
    was, so the need types alone would not re-read it."""
    srcdir = _service_project(tmp_path / "src", OWN_ISSUE_CONF, PLAIN_INDEX)
    app = make_app("html", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        pickled = Path(app.doctreedir, "environment.pickle")
    finally:
        app.cleanup()
    env = pickle.loads(pickled.read_bytes())
    env.__dict__.pop("_needs_builtin_services_read_with", None)
    pickled.write_bytes(pickle.dumps(env, pickle.HIGHEST_PROTOCOL))

    _, warnings, read = _build(make_app, srcdir, fresh=False)
    assert sorted(read) == ["index", "other"]
    assert warnings == []
    _, _, read = _build(make_app, srcdir, fresh=False)
    assert read == []
