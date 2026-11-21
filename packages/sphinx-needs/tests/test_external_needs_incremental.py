"""An incremental build holds the external needs its configuration gives, and no other.

``needs_external_needs`` is registered with ``rebuild = "html"``, so a change to it -- or
to a file it reads -- re-reads no document: the pickled environment is kept, and its
sources are loaded into it again at ``env-before-read-docs``. An external need belongs to
the build that loaded it, so the needs a previous build loaded are removed before the
sources are loaded again: a need under an id the configuration no longer gives (a
changed ``id_prefix``, a source removed, a need gone from its file) does not stay beside
the current ones, warning again.

The oracle is a fresh build of the configuration after the change: the needs an
incremental build ends with, and its warnings, equal that build's.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

INDEX = """\
Index
=====

.. req:: A local need
   :id: LOCAL_1
"""


def _record(key: str, **fields: Any) -> dict[str, Any]:
    return {
        "id": key,
        "type": "req",
        "title": f"Title of {key}",
        "docname": "index",
        **fields,
    }


def _needs_json(
    versions: Mapping[str, Mapping[str, dict[str, Any]]], current: str
) -> str:
    return json.dumps(
        {
            "current_version": current,
            "versions": {v: {"needs": dict(needs)} for v, needs in versions.items()},
        }
    )


#: a file of three needs, one of them linking to a need it does not hold
A_NEEDS = {
    "REQ_1": _record("REQ_1"),
    "REQ_2": _record("REQ_2", links=["REQ_1", "MISSING_1"]),
    "REQ_3": _record("REQ_3"),
}
A = _needs_json({"1.0": A_NEEDS}, "1.0")
#: the same file, ``REQ_3`` gone from it
A_SHORTER = _needs_json(
    {"1.0": {k: v for k, v in A_NEEDS.items() if k != "REQ_3"}}, "1.0"
)
#: another file, of other needs
B = _needs_json({"1.0": {"SPEC_1": _record("SPEC_1")}}, "1.0")
#: a file of two versions, with other needs in each
VERSIONED = _needs_json(
    {
        "1.0": {"OLD_1": _record("OLD_1"), "BOTH_1": _record("BOTH_1")},
        "2.0": {"NEW_1": _record("NEW_1"), "BOTH_1": _record("BOTH_1")},
    },
    "2.0",
)


def _source(json_path: str, **keys: str) -> dict[str, str]:
    return {"json_path": json_path, "base_url": "http://ext.example", **keys}


def _conf(*sources: dict[str, str]) -> str:
    return (
        'extensions = ["sphinx_needs"]\n'
        "needs_build_json = True\n"
        'needs_builder_filter = ""\n'
        f"needs_external_needs = {json.dumps(list(sources), indent=4)}\n"
    )


def _project(conf: str, **files: str) -> dict[str, str]:
    """The files of a project: ``conf.py``, ``index.rst`` and the sources' files."""
    return {"conf.py": conf, "index.rst": INDEX, **files}


#: before and after: a project's files, then the files written over them
CASES: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    "id_prefix-changed": (
        _project(_conf(_source("a.json", id_prefix="SUP::")), **{"a.json": A}),
        {"conf.py": _conf(_source("a.json", id_prefix="SUP2::"))},
    ),
    "source-removed": (
        _project(
            _conf(_source("a.json", id_prefix="A_"), _source("b.json", id_prefix="B_")),
            **{"a.json": A, "b.json": B},
        ),
        {"conf.py": _conf(_source("a.json", id_prefix="A_"))},
    ),
    "need-gone-from-the-file": (
        _project(_conf(_source("a.json")), **{"a.json": A}),
        {"a.json": A_SHORTER},
    ),
    "nothing-changed": (_project(_conf(_source("a.json")), **{"a.json": A}), {}),
    "json_path-changed": (
        _project(_conf(_source("a.json")), **{"a.json": A, "b.json": B}),
        {"conf.py": _conf(_source("b.json"))},
    ),
    "version-changed": (
        _project(_conf(_source("v.json", version="1.0")), **{"v.json": VERSIONED}),
        {"conf.py": _conf(_source("v.json", version="2.0"))},
    ),
    "base_url-changed": (
        _project(_conf(_source("a.json")), **{"a.json": A}),
        {"conf.py": _conf({**_source("a.json"), "base_url": "http://moved.example"})},
    ),
    "target_url-changed": (
        _project(_conf(_source("a.json")), **{"a.json": A}),
        {"conf.py": _conf(_source("a.json", target_url="need/{{need['id']}}"))},
    ),
    "source-added": (
        _project(_conf(_source("a.json")), **{"a.json": A, "b.json": B}),
        {"conf.py": _conf(_source("a.json"), _source("b.json"))},
    ),
    "sources-reordered": (
        _project(
            _conf(_source("a.json", id_prefix="A_"), _source("b.json", id_prefix="B_")),
            **{"a.json": A, "b.json": B},
        ),
        {
            "conf.py": _conf(
                _source("b.json", id_prefix="B_"), _source("a.json", id_prefix="A_")
            )
        },
    ),
    "all-sources-removed": (
        _project(_conf(_source("a.json")), **{"a.json": A}),
        {"conf.py": _conf()},
    ),
}

#: the needs the configuration after the change gives, besides ``LOCAL_1``
EXPECTED_AFTER = {
    "id_prefix-changed": ["SUP2::REQ_1", "SUP2::REQ_2", "SUP2::REQ_3"],
    "source-removed": ["A_REQ_1", "A_REQ_2", "A_REQ_3"],
    "need-gone-from-the-file": ["REQ_1", "REQ_2"],
    "nothing-changed": ["REQ_1", "REQ_2", "REQ_3"],
    "json_path-changed": ["SPEC_1"],
    "version-changed": ["BOTH_1", "NEW_1"],
    "base_url-changed": ["REQ_1", "REQ_2", "REQ_3"],
    "target_url-changed": ["REQ_1", "REQ_2", "REQ_3"],
    "source-added": ["REQ_1", "REQ_2", "REQ_3", "SPEC_1"],
    "sources-reordered": ["A_REQ_1", "A_REQ_2", "A_REQ_3", "B_SPEC_1"],
    "all-sources-removed": [],
}


def _write(srcdir: Path, files: Mapping[str, str]) -> Path:
    srcdir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    return srcdir


def _held(app: SphinxTestApp) -> dict[str, tuple[bool, str | None, str]]:
    """The needs held: ``is_external``, ``external_url`` and title by id, from
    ``needs.json``, which lists the external needs too."""
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    needs = data["versions"][data["current_version"]]["needs"]
    return {
        need_id: (need["is_external"], need["external_url"], need["title"])
        for need_id, need in needs.items()
    }


def _build(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, *, fresh: bool
) -> tuple[dict[str, tuple[bool, str | None, str]], list[str]]:
    """Build, and return the needs held and the warnings."""
    app = make_app("html", srcdir=srcdir, freshenv=fresh)
    try:
        app.build()
        return _held(app), build_warnings(app)
    finally:
        app.cleanup()


def _build_and_record(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, *, fresh: bool
) -> tuple[dict[str, tuple[bool, str | None, str]], list[str]]:
    """Build, and return the needs held and the environment's record of the ids
    ``needs_external_needs`` loaded."""
    app = make_app("html", srcdir=srcdir, freshenv=fresh)
    try:
        app.build()
        return _held(app), list(SphinxNeedsData(app.env).external_needs_loaded)
    finally:
        app.cleanup()


@pytest.mark.parametrize(("before", "after"), CASES.values(), ids=CASES.keys())
def test_incremental_build_holds_the_external_needs_of_the_current_configuration(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    request: pytest.FixtureRequest,
    before: dict[str, str],
    after: dict[str, str],
) -> None:
    """After the change, an incremental build holds the ids a fresh build of the
    changed project holds, each external or not, with its URL and title, as there; and
    it gives that build's warnings, each once."""
    srcdir = _write(tmp_path / "incremental", before)
    _build(make_app, srcdir, fresh=True)
    incremental, incremental_warnings = _build(
        make_app, _write(srcdir, after), fresh=False
    )

    fresh, fresh_warnings = _build(
        make_app, _write(tmp_path / "fresh", {**before, **after}), fresh=True
    )
    case = request.node.callspec.id
    assert sorted(incremental) == sorted(["LOCAL_1", *EXPECTED_AFTER[case]])
    assert incremental == fresh
    assert incremental_warnings == fresh_warnings
    assert len(set(incremental_warnings)) == len(incremental_warnings)


def test_id_prefix_changed_keeps_only_the_new_ids(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The recorded case: a source's ``id_prefix`` changed from ``SUP::`` to
    ``SUP2::``; the needs of the old prefix are gone, and so are their warnings."""
    before, after = CASES["id_prefix-changed"]
    srcdir = _write(tmp_path / "src", before)
    _build(make_app, srcdir, fresh=True)
    needs, warnings = _build(make_app, _write(srcdir, after), fresh=False)
    assert (sorted(needs), warnings) == (
        ["LOCAL_1", "SUP2::REQ_1", "SUP2::REQ_2", "SUP2::REQ_3"],
        [
            "WARNING: http://ext.example/index.html#REQ_2: Need 'SUP2::REQ_2' has "
            "unknown outgoing link 'MISSING_1' in field 'links' "
            "[needs.external_link_outgoing]"
        ],
    )


def test_clean_build(make_app: Callable[..., SphinxTestApp], tmp_path: Path) -> None:
    """A fresh build holds the project's need and every need its source gives."""
    before, _ = CASES["id_prefix-changed"]
    needs, warnings = _build(make_app, _write(tmp_path / "src", before), fresh=True)
    assert needs == {
        "LOCAL_1": (False, None, "A local need"),
        "SUP::REQ_1": (True, "http://ext.example/index.html#REQ_1", "Title of REQ_1"),
        "SUP::REQ_2": (True, "http://ext.example/index.html#REQ_2", "Title of REQ_2"),
        "SUP::REQ_3": (True, "http://ext.example/index.html#REQ_3", "Title of REQ_3"),
    }
    assert warnings == [
        "WARNING: http://ext.example/index.html#REQ_2: Need 'SUP::REQ_2' has unknown "
        "outgoing link 'MISSING_1' in field 'links' [needs.external_link_outgoing]"
    ]


def test_a_local_need_of_a_loaded_id_stays_local(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A need of the project replaces the external need of its id, and still does on an
    incremental build, where its document is not read again."""
    srcdir = _write(
        tmp_path / "src",
        _project(
            _conf(_source("a.json")),
            **{"a.json": A, "index.rst": INDEX + "\n.. req:: Mine\n   :id: REQ_3\n"},
        ),
    )
    first, first_warnings = _build(make_app, srcdir, fresh=True)
    assert first["REQ_3"] == (False, None, "Mine")
    second, second_warnings = _build(make_app, srcdir, fresh=False)
    assert second == first
    assert second_warnings == first_warnings


API_EXT = '''\
"""Adds an external need through ``add_external_need`` while a document is read."""

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import add_external_need


class ExternalProbe(SphinxDirective):
    optional_arguments = 1

    def run(self):
        add_external_need(
            self.env.app,
            "req",
            "an external need of the API",
            id=self.arguments[0] if self.arguments else "R_API",
            external_url="http://example.org/api.html",
        )
        return []


def setup(app):
    app.add_directive("external-probe", ExternalProbe)
    return {"parallel_read_safe": True}
'''


#: a need ``API_EXT`` adds, as ``_held`` gives it
API_NEED = (True, "http://example.org/api.html", "an external need of the API")

#: a second document, which an incremental build does not read again unless it changes
OTHER = ":orphan:\n\nOther\n=====\n"


def _api_conf(*sources: dict[str, str]) -> str:
    """``conf.py`` of a project that also loads ``external_api_ext.py``, beside it."""
    return (
        "import sys\nfrom pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).parent))\n"
        'sys.modules.pop("external_api_ext", None)\n'
        + _conf(*sources).replace(
            '["sphinx_needs"]', '["sphinx_needs", "external_api_ext"]'
        )
    )


def test_an_external_need_of_the_api_stays(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """An external need an extension added while a document was read is not one
    ``needs_external_needs`` loaded: it stays when that document is not read again,
    as the needs of the document's own directives do."""
    srcdir = _write(
        tmp_path / "src",
        _project(
            _api_conf(_source("a.json", id_prefix="SUP::")),
            **{
                "a.json": A,
                "external_api_ext.py": API_EXT,
                "index.rst": INDEX + "\n.. external-probe::\n",
            },
        ),
    )
    first, _ = _build(make_app, srcdir, fresh=True)
    assert first["R_API"] == (
        True,
        "http://example.org/api.html",
        "an external need of the API",
    )
    second, _ = _build(make_app, srcdir, fresh=False)
    assert second == first


def test_the_record_leaves_out_an_external_need_of_the_api(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The record of the needs loaded names only those the sources gave, not every
    external need: the need of the API, in a document not read again, is not in the
    environment saved with that record, and the build after it still holds the need."""
    srcdir = _write(
        tmp_path / "src",
        _project(
            _api_conf(_source("a.json")),
            **{
                "a.json": A,
                "external_api_ext.py": API_EXT,
                "other.rst": OTHER + "\n.. external-probe::\n",
            },
        ),
    )
    first, _ = _build_and_record(make_app, srcdir, fresh=True)
    # index.rst changed, other.rst not: the environment is saved again, with the record
    second, record = _build_and_record(
        make_app, _write(srcdir, {"index.rst": INDEX + "\nChanged.\n"}), fresh=False
    )
    third, _ = _build_and_record(make_app, srcdir, fresh=False)
    assert "R_API" not in record
    assert record == ["REQ_1", "REQ_2", "REQ_3"]
    assert [needs.get("R_API") for needs in (first, second, third)] == [API_NEED] * 3


def test_no_source_empties_the_record(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Once no source is configured, the record of the needs loaded is empty, in the
    environment an incremental build that reads a document again saves."""
    srcdir = _write(
        tmp_path / "src", _project(_conf(_source("a.json")), **{"a.json": A})
    )
    _, record = _build_and_record(make_app, srcdir, fresh=True)
    assert record == ["REQ_1", "REQ_2", "REQ_3"]
    needs, record = _build_and_record(
        make_app,
        _write(srcdir, {"conf.py": _conf(), "index.rst": INDEX + "\nChanged.\n"}),
        fresh=False,
    )
    assert (sorted(needs), record) == (["LOCAL_1"], [])


def test_an_external_need_of_the_api_under_an_id_loaded_before_stays(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The sources are emptied (a document read again); then an extension adds an
    external need under an id they had loaded: the build after, which reads nothing
    again, still holds it."""
    srcdir = _write(
        tmp_path / "src",
        _project(
            _api_conf(_source("a.json")),
            **{"a.json": A, "external_api_ext.py": API_EXT, "other.rst": OTHER},
        ),
    )
    first, _ = _build(make_app, srcdir, fresh=True)
    assert first["REQ_1"] == (
        True,
        "http://ext.example/index.html#REQ_1",
        "Title of REQ_1",
    )
    no_source, _ = _build(
        make_app,
        _write(srcdir, {"conf.py": _api_conf(), "index.rst": INDEX + "\nChanged.\n"}),
        fresh=False,
    )
    assert sorted(no_source) == ["LOCAL_1"]
    probed, _ = _build(
        make_app,
        _write(srcdir, {"other.rst": OTHER + "\n.. external-probe:: REQ_1\n"}),
        fresh=False,
    )
    unchanged, _ = _build(make_app, srcdir, fresh=False)
    assert [needs.get("REQ_1") for needs in (probed, unchanged)] == [API_NEED] * 2
