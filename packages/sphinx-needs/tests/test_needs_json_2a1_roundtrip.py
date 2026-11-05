"""Reading the draft needs.json "2a1" back (experimental): ``needimport`` and external
needs keep each record's source hops, as the need's ``upstream``.

Three projects in a chain: ``up`` writes a 2a1 file (a page need with a part, a link to
that part, a need in a nested include); ``down`` imports it (``needimport``, ids ``D_``)
and loads it as external needs (ids ``X_``), and writes its own 2a1 file; ``down2``
imports that. A hop with no ``origin`` in a file is the writing project's: it is filled
with the envelope's ``project.name`` on read, and an origin a file states is never
changed. Nothing a need of this build answers moves: its legacy location keys and its
``c.source`` facets are those of the same need imported from the format-1 file.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs import _source_facets as facets
from sphinx_needs._needsfile_v2a1 import hop_to_json
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import NeedItemSource
from sphinx_needs_testkit import build_warnings

BETA = "[needs.beta]"

UP_CONF = """\
project = "up"
version = "1.0"
extensions = ["sphinx_needs"]
exclude_patterns = ["_build", "mid.rst", "frag.rst"]
needs_json_format_version = {format!r}
"""

UP_INDEX = """\
Up
==

Requirements
------------

.. req:: First
   :id: REQ_1

   Body with :np:`(p1) a part`.

.. req:: Second
   :id: REQ_2
   :links: REQ_1.p1

.. include:: mid.rst
"""

UP_FILES = {
    "index.rst": UP_INDEX,
    "mid.rst": ".. include:: frag.rst\n",
    "frag.rst": ".. req:: Included\n   :id: REQ_INC\n",
}

DOWN_CONF = """\
project = "down"
version = "2.0"
extensions = ["sphinx_needs"]
exclude_patterns = ["_build"]
needs_json_format_version = "2a1"
needs_external_needs = [
    {"base_url": "http://up.example", "json_path": "up.json", "id_prefix": "X_"}
]
"""

DOWN_INDEX = """\
Down
====

.. needimport:: up.json
   :id_prefix: D_
"""

DOWN2_CONF = """\
project = "down2"
extensions = ["sphinx_needs"]
exclude_patterns = ["_build"]
needs_json_format_version = "2a1"
"""

DOWN2_INDEX = """\
Down2
=====

.. needimport:: down.json
"""


def _write(srcdir: Path, files: dict[str, str]) -> Path:
    srcdir.mkdir(parents=True)
    for name, text in files.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    return srcdir


def _build(make_app: Any, srcdir: Path) -> tuple[Any, Path]:
    """Build ``srcdir`` with the ``needs`` builder; return the app, cleaned up (its
    environment and its warnings are still read), and its needs.json."""
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
    finally:
        # the next application of the test registers its nodes anew
        app.cleanup()
    return app, Path(app.outdir, "needs.json")


def _records(path: Path) -> dict[str, dict[str, Any]]:
    return {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["needs"]}


def _with_origin(hops: list[dict[str, Any]], origin: str) -> list[dict[str, Any]]:
    """``hops`` as a reader keeps them: an absent origin filled, a stated one kept."""
    return [{**hop, "origin": hop.get("origin", origin)} for hop in hops]


def _facts(need: Any) -> dict[str, Any]:
    """What a need of the reading build answers about where it is from."""
    source = need.source
    return {
        "docname": need["docname"],
        "lineno": need["lineno"],
        "is_external": need["is_external"],
        "is_import": need["is_import"],
        "external_url": need["external_url"],
        "sections": list(need["sections"]),
        "kind": facets.kind_of(source),
        "path": facets.path_of(source),
        "line": facets.line_of(source),
        "paths": list(facets.paths_of(source)),
        "symbol": facets.symbol_of(source),
        "hops": [hop_to_json(hop) for hop in source.hops],
    }


@pytest.fixture
def chain(make_app: Any, tmp_path: Path) -> dict[str, Any]:
    """Build up (2a1, and format 1 beside it), down (from each), and down2."""
    up, up_json = _build(
        make_app,
        _write(tmp_path / "up", {"conf.py": UP_CONF.format(format="2a1"), **UP_FILES}),
    )
    assert [w for w in build_warnings(up) if BETA not in w] == []
    _, up_v1_json = _build(
        make_app,
        _write(tmp_path / "up_v1", {"conf.py": UP_CONF.format(format=1), **UP_FILES}),
    )
    down_files = {"conf.py": DOWN_CONF, "index.rst": DOWN_INDEX}
    down_src = _write(tmp_path / "down", down_files)
    shutil.copy(up_json, down_src / "up.json")
    down, down_json = _build(make_app, down_src)
    down_v1_src = _write(
        tmp_path / "down_v1", {**down_files, "conf.py": DOWN_CONF.replace('"2a1"', "1")}
    )
    shutil.copy(up_v1_json, down_v1_src / "up.json")
    down_v1, _ = _build(make_app, down_v1_src)
    down2_src = _write(
        tmp_path / "down2", {"conf.py": DOWN2_CONF, "index.rst": DOWN2_INDEX}
    )
    shutil.copy(down_json, down2_src / "down.json")
    down2, down2_json = _build(make_app, down2_src)
    return {
        "up": _records(up_json),
        "down_app": down,
        "down": _records(down_json),
        "down_v1_app": down_v1,
        "down2_app": down2,
        "down2": _records(down2_json),
    }


def test_the_chain_builds_without_warnings(chain: dict[str, Any]) -> None:
    for name in ("down_app", "down2_app"):
        assert [w for w in build_warnings(chain[name]) if BETA not in w] == [], name


def test_hops_are_only_appended_and_origins_only_filled(chain: dict[str, Any]) -> None:
    """Every hop a file holds reaches the next file unchanged, after it, but for an
    absent origin, which is filled with the name of the project that wrote it."""
    up, down, down2 = chain["up"], chain["down"], chain["down2"]
    up_hops = up["REQ_INC"]["source"]
    assert [hop["kind"] for hop in up_hops] == ["file", "file", "page"]
    assert all("origin" not in hop for hop in up_hops)

    down_hops = down["D_REQ_INC"]["source"]
    local = down_hops[len(up_hops) :]
    assert down_hops[: len(up_hops)] == _with_origin(up_hops, "up")
    assert [hop["kind"] for hop in local] == ["file", "page"]
    assert all("origin" not in hop for hop in local)

    down2_hops = down2["D_REQ_INC"]["source"]
    assert down2_hops[: len(down_hops)] == _with_origin(down_hops, "down")
    # up's hops keep the origin down's file states
    assert [hop["origin"] for hop in down2_hops[: len(up_hops)]] == ["up"] * 3
    assert [hop.get("origin") for hop in down2_hops[len(down_hops) :]] == [None, None]


def test_an_imported_need_keeps_its_upstream_beside_its_hops(
    chain: dict[str, Any],
) -> None:
    """The record's hops are the need's ``upstream``; its ``hops`` are this build's."""
    need = SphinxNeedsData(chain["down_app"].env).get_needs_view()["D_REQ_INC"]
    source = need.source
    assert isinstance(source, NeedItemSource)
    assert [hop_to_json(hop) for hop in source.upstream] == _with_origin(
        chain["up"]["REQ_INC"]["source"], "up"
    )
    assert [hop.kind for hop in source.hops] == ["file", "page"]
    assert all(hop.origin is None for hop in source.hops)


@pytest.mark.parametrize(
    "need_id", ["D_REQ_1", "D_REQ_2", "D_REQ_INC", "X_REQ_1", "X_REQ_2", "X_REQ_INC"]
)
def test_what_a_need_answers_is_a_format_1_import_s(
    chain: dict[str, Any], need_id: str
) -> None:
    """The legacy keys and the ``c.source`` facets of an imported and an external need
    are those of the same need read from the format-1 file: the upstream hops are kept,
    not read."""
    read = SphinxNeedsData(chain["down_app"].env).get_needs_view()[need_id]
    v1 = SphinxNeedsData(chain["down_v1_app"].env).get_needs_view()[need_id]
    assert _facts(read) == _facts(v1)


def test_an_external_need_of_a_2a1_file(chain: dict[str, Any]) -> None:
    """External, with no page of this build; its URL from the docname projected from
    its placement; its part, which its record's content carries, a link target."""
    needs = SphinxNeedsData(chain["down_app"].env).get_needs_view()
    first, second = needs["X_REQ_1"], needs["X_REQ_2"]
    assert first["is_external"] is True
    assert first["docname"] is None
    assert first["external_url"] == "http://up.example/index.html#REQ_1"
    assert list(first["sections"]) == ["Requirements", "Up"]
    assert list(first["parts"]) == ["p1"]
    assert second["links"] == ["X_REQ_1.p1"]
    assert second["has_dead_links"] is False
    assert first["parts"]["p1"]["links_back"] == ["X_REQ_2"]
    source = first.source
    assert isinstance(source, NeedItemSource)
    assert [hop.kind for hop in source.hops] == ["external"]
    assert [(hop.kind, hop.origin) for hop in source.upstream] == [("page", "up")]


ANONYMOUS = {
    "format_version": "2a1",
    "needs": [
        {
            "id": "ANON_1",
            "type": "req",
            "fields": {"title": "anonymous"},
            "source": [
                {"kind": "page", "document": "index"},
                {"kind": "page", "document": "there", "origin": "named"},
            ],
        }
    ],
}


def test_without_a_project_name_the_origin_is_the_source(
    make_app: Any, tmp_path: Path
) -> None:
    """A file whose envelope names no project: an absent origin is the file as the
    reader names it -- the needimport's path relative to the source directory, an
    external source's ``json_path`` as written (``./data/anon.json``). A stated origin is kept."""
    srcdir = _write(
        tmp_path / "anon",
        {
            "conf.py": 'extensions = ["sphinx_needs"]\n'
            "needs_external_needs = [\n"
            '    {"base_url": "http://x", "json_path": "./data/anon.json", "id_prefix": "X_"}\n'
            "]\n",
            "index.rst": "Anon\n====\n\n.. needimport:: data/anon.json\n",
        },
    )
    (srcdir / "data").mkdir()
    (srcdir / "data" / "anon.json").write_text(json.dumps(ANONYMOUS))
    app, _ = _build(make_app, srcdir)
    needs = SphinxNeedsData(app.env).get_needs_view()
    for need_id, origin in (
        ("ANON_1", "data/anon.json"),
        ("X_ANON_1", "./data/anon.json"),
    ):
        source = needs[need_id].source
        assert isinstance(source, NeedItemSource)
        assert [hop.origin for hop in source.upstream] == [origin, "named"]


LINKS_CONF = """\
project = "{project}"
extensions = ["sphinx_needs"]
exclude_patterns = ["_build"]
needs_json_format_version = "2a1"
needs_links = {{
    "refs": {{"incoming": "is referenced by", "outgoing": "refs", "parse_conditions": False}}
}}
"""

LINKS_INDEX = """\
Links
=====

.. req:: A
   :id: REQ_A
   :status: open

   With :np:`(p1) a part`.

.. req:: B
   :id: REQ_B
   :status: open

.. req:: Linking
   :id: REQ_L
   :links: REQ_B, REQ_A.p1, REQ_B[status == "open"], REQ_A.p1[status == "open"]
   :refs: REQ_B, REQ_A.p1
"""

#: REQ_L's links as a 2a1 record spells them: a bare id only for a link with neither a
#: part nor a condition
SPELLED = {
    "links": [
        {"id": "REQ_A", "part": "p1"},
        {"id": "REQ_A", "part": "p1", "condition": 'status == "open"'},
        "REQ_B",
        {"id": "REQ_B", "condition": 'status == "open"'},
    ],
    "refs": [{"id": "REQ_A", "part": "p1"}, "REQ_B"],
    "parent_needs": [],
}


def _prefixed(links: dict[str, list[Any]], prefix: str) -> dict[str, list[Any]]:
    return {
        name: [
            prefix + link
            if isinstance(link, str)
            else {**link, "id": prefix + link["id"]}
            for link in items
        ]
        for name, items in links.items()
    }


def test_every_link_spelling_round_trips(make_app: Any, tmp_path: Path) -> None:
    """A bare id, a part, a condition, a part and a condition, and a link type that does
    not parse conditions: written by ``up``, read by ``down``'s ``needimport`` and its
    external needs, and written again by ``down``, each link is the same link -- its
    id prefixed, its part and condition kept, every condition evaluated and passing."""
    up, up_json = _build(
        make_app,
        _write(
            tmp_path / "up",
            {"conf.py": LINKS_CONF.format(project="up"), "index.rst": LINKS_INDEX},
        ),
    )
    assert [w for w in build_warnings(up) if BETA not in w] == []
    assert _records(up_json)["REQ_L"]["links"] == SPELLED

    down_src = _write(
        tmp_path / "down",
        {
            "conf.py": LINKS_CONF.format(project="down") + "needs_external_needs = [\n"
            '    {"base_url": "http://up.example", "json_path": "up.json", '
            '"id_prefix": "X_"}\n'
            "]\n",
            "index.rst": "Down\n====\n\n.. needimport:: up.json\n   :id_prefix: D_\n",
        },
    )
    shutil.copy(up_json, down_src / "up.json")
    down, down_json = _build(make_app, down_src)
    assert [w for w in build_warnings(down) if BETA not in w] == []
    assert _records(down_json)["D_REQ_L"]["links"] == _prefixed(SPELLED, "D_")

    needs = SphinxNeedsData(down.env).get_needs_view()
    for prefix in ("D_", "X_"):
        need = needs[f"{prefix}REQ_L"]
        assert [
            (link.id, link.part, link.condition)
            for link in need.get_links("links", as_str=False)
        ] == [
            (f"{prefix}REQ_A", "p1", None),
            (f"{prefix}REQ_A", "p1", 'status == "open"'),
            (f"{prefix}REQ_B", None, None),
            (f"{prefix}REQ_B", None, 'status == "open"'),
        ], prefix
        assert [
            (link.id, link.part, link.condition)
            for link in need.get_links("refs", as_str=False)
        ] == [(f"{prefix}REQ_A", "p1", None), (f"{prefix}REQ_B", None, None)], prefix
        assert need["has_dead_links"] is False


def _import_one(
    make_app: Any, srcdir: Path, document: dict[str, Any], argument: str | None = None
) -> tuple[Any, NeedItemSource]:
    """``needimport`` the 2a1 ``document`` (``data/anon.json``, or ``argument``) and
    return the app and the one need's source."""
    (srcdir / "data").mkdir(parents=True)
    (srcdir / "data" / "anon.json").write_text(json.dumps(document))
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_json_format_version = "2a1"\n'
    )
    (srcdir / "index.rst").write_text(
        f"Anon\n====\n\n.. needimport:: {argument or 'data/anon.json'}\n"
    )
    app, _ = _build(make_app, srcdir)
    (need,) = SphinxNeedsData(app.env).get_needs_view().values()
    assert isinstance(need.source, NeedItemSource)
    return app, need.source


def test_a_url_is_the_origin_as_written(make_app: Any, tmp_path: Path) -> None:
    """Without a project name, a needimport from a URL names its hops by the URL as
    the directive writes it."""
    srcdir = tmp_path / "url"
    url = (srcdir / "data" / "anon.json").as_uri()
    _, source = _import_one(make_app, srcdir, ANONYMOUS, url)
    assert [hop.origin for hop in source.upstream] == [url, "named"]


def test_a_project_name_that_is_not_a_string_is_no_name(
    make_app: Any, tmp_path: Path
) -> None:
    """A ``project.name`` that is not a string is reported, and the file names the
    hops."""
    app, source = _import_one(
        make_app, tmp_path / "num", {**ANONYMOUS, "project": {"name": 5}}
    )
    assert [hop.origin for hop in source.upstream] == ["data/anon.json", "named"]
    assert [w for w in build_warnings(app) if "(at project.name)" in w] != []


def test_hop_keys_this_build_does_not_know_are_dropped_on_re_export(
    make_app: Any, tmp_path: Path
) -> None:
    """A key of a hop, of its ``physical`` or of a ``semantic`` entry that sphinx-needs
    does not model is read without error, and not written again."""
    document = {
        "format_version": "2a1",
        "project": {"name": "other"},
        "needs": [
            {
                "id": "ANON_1",
                "type": "req",
                "fields": {"title": "anonymous"},
                "source": [
                    {
                        "kind": "code",
                        "col": 3,
                        "future": {"x": 1},
                        "physical": {"path": "a.c", "start_line": 2, "start_col": 4},
                        "semantic": [
                            {"kind": "function", "name": "f", "extra_key": "y"}
                        ],
                    },
                    {"kind": "page", "document": "there"},
                ],
            }
        ],
    }
    app, _ = _import_one(make_app, tmp_path / "unknown", document)
    written = _records(Path(app.outdir, "needs.json"))["ANON_1"]["source"]
    assert written[:2] == [
        {
            "kind": "code",
            "origin": "other",
            "physical": {"path": "a.c", "start_line": 2},
            "semantic": [{"kind": "function", "name": "f"}],
        },
        {"kind": "page", "origin": "other", "document": "there"},
    ]


def test_an_unnamed_writer_is_named_by_its_file_downstream(
    make_app: Any, tmp_path: Path
) -> None:
    """A project that sets no ``project`` writes no name, so a reader names its hops by
    the file, not by Sphinx's placeholder."""
    up_src = _write(
        tmp_path / "unnamed",
        {
            "conf.py": 'extensions = ["sphinx_needs"]\n'
            'needs_json_format_version = "2a1"\n',
            "index.rst": "Up\n==\n\n.. req:: a\n   :id: REQ_001\n",
        },
    )
    _, up_json = _build(make_app, up_src)
    down_src = _write(
        tmp_path / "down",
        {
            "conf.py": 'extensions = ["sphinx_needs"]\n',
            "index.rst": "Down\n====\n\n.. needimport:: up.json\n",
        },
    )
    shutil.copy(up_json, down_src / "up.json")
    down, _ = _build(make_app, down_src)
    source = SphinxNeedsData(down.env).get_needs_view()["REQ_001"].source
    assert isinstance(source, NeedItemSource)
    assert [hop.origin for hop in source.upstream] == ["up.json"]
