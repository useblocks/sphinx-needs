"""The draft needs.json format "2a1" (experimental): what the builders write under
``needs_json_format_version = "2a1"``, and that nothing moves without it.

The project (``doc_test/doc_needs_json_2a1``) has a need with a part, a link to that
part and one under a condition, a nested need (``parent_needs``), a need in a nested
include, a ``needimport`` of a v1 file, a need in an autodoc docstring, a need a local
service generates, a link type of the project's own, and a field one need type alone
declares.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from syrupy.filters import props

import ub_needs_exchange as exchange
from sphinx_needs import __version__
from sphinx_needs._needsfile_v2a1 import hop_to_json
from sphinx_needs_testkit import build_warnings

PROJECT = "doc_test/doc_needs_json_2a1"

BETA = (
    'WARNING: needs.json format "2a1" is experimental: a file written in it may not '
    "be readable by the next release of sphinx-needs [needs.beta]"
)


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _needs_json(app: Any) -> dict[str, Any]:
    return _read(Path(app.outdir, "needs.json"))


def _records(app: Any) -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in _needs_json(app)["needs"]}


def _config_warnings(app: Any) -> list[str]:
    return [w for w in build_warnings(app) if "[needs.config]" in w]


# --- the writer ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "srcdir": PROJECT}], indirect=True
)
def test_the_needs_builder_writes_2a1(test_app: Any, snapshot: Any) -> None:
    """The envelope and every record: ``id``, ``type``, the need type's fields (core
    authored ones among them; ``collapse`` and ``hide`` excluded by default, as in
    v1), its links (a bare id, or an object where a part or a condition is given; no
    back links), its content (with its parts) and its source hops, innermost first,
    with ``None`` left out. No ``versions``, no schema, no computed key, no legacy
    location key, no ``type_*``, ``external_css``, ``arch`` or rendering instruction."""
    app = test_app
    app.build()

    assert build_warnings(app) == [BETA]
    data = _needs_json(app)
    assert list(data) == ["format_version", "project", "creator", "created", "needs"]
    assert data["format_version"] == "2a1"
    assert data["project"] == {"name": "up", "version": "1.0"}
    assert data["creator"] == {"program": "sphinx_needs", "version": __version__}
    assert [record["id"] for record in data["needs"]] == sorted(
        record["id"] for record in data["needs"]
    )
    for record in data["needs"]:
        assert list(record) == ["id", "type", "fields", "links", "content", "source"]
    # a hop's keys in the order of its fields, a field the hop does not hold left out
    code, page = _records(app)["REQ_DOC"]["source"]
    assert list(code) == ["kind", "physical", "semantic", "language"]
    assert list(page) == ["kind", "physical", "semantic", "document", "language"]
    # syrupy sorts the keys it prints: the orders inside a record are pinned here
    first = _records(app)["REQ_1"]
    assert list(first["fields"]) == [
        # the authored core fields, in their order, then the extras in the schema's
        # (``layout``, ``style``, ``duration`` and ``completion`` are ``null``: left out)
        *("title", "status", "tags", "constraints"),
        "asil",
    ]
    assert list(first["source"][0]["physical"]) == [
        "root",
        "path",
        "start_line",
        "end_line",
    ]
    assert data == snapshot(exclude=props("created", "creator"))


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "srcdir": PROJECT}], indirect=True
)
def test_the_file_reads_back_without_a_finding(test_app: Any) -> None:
    """ub-needs-exchange reads the file the writer writes with no finding: no
    ``field_reserved`` (no key the projection owns inside ``fields``), no invalid hop or
    link, every record kept."""
    app = test_app
    app.build()

    version = exchange.load(Path(app.outdir, "needs.json")).select_version(
        None, drafts=("2a1",)
    )
    assert version.format_version == "2a1"
    assert version.name == "1.0"
    assert list(version.diagnostics) == []
    records = version.records()
    assert [r.key for r in records] == list(_records(app))
    assert [(r.key, list(r.diagnostics)) for r in records if r.diagnostics] == []
    assert exchange.FIELD_RESERVED == "field_reserved"


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": PROJECT}],
    indirect=True,
)
def test_what_a_record_leaves_out(test_app: Any) -> None:
    """The keys a 2a1 record has no place for, by name, on every record."""
    app = test_app
    app.build()

    left_out = {
        # back links and computed keys
        "links_back",
        "implements_back",
        "parent_needs_back",
        "is_need",
        "is_part",
        "is_modified",
        "modifications",
        "id_parent",
        "id_complete",
        "section_name",
        "parent_need",
        "constraints_results",
        "constraints_passed",
        "constraints_error",
        "has_dead_links",
        "has_forbidden_dead_links",
        # configuration and products
        "type_name",
        "type_prefix",
        "type_color",
        "type_style",
        "external_css",
        "arch",
        # legacy location keys: projections of the source
        "docname",
        "lineno",
        "lineno_content",
        "sections",
        "signature",
        "external_url",
        "is_import",
        "is_external",
        # rendering instructions
        "template",
        "pre_template",
        "post_template",
        "pre_content",
        "post_content",
        "jinja_content",
        # the default exclusions, as in v1
        "collapse",
        "hide",
    }
    # the names a reader reserves in ``fields``: the record's own keys and the projection's
    reserved = {"id", "type", "content", "doctype", "parts", "docname", "sections"}
    for record in _records(app).values():
        assert not reserved & set(record["fields"]), record["id"]
        assert not left_out & set(record["fields"]), record["id"]
        assert not left_out & set(record["links"]), record["id"]
        assert not left_out & set(record), record["id"]


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "srcdir": PROJECT}], indirect=True
)
def test_a_field_a_need_type_lacks_is_left_out(test_app: Any) -> None:
    """``verdict`` is declared on ``spec`` alone; a ``req`` record has no such key,
    where v1 writes it ``null`` on every need."""
    app = test_app
    app.build()

    records = _records(app)
    assert records["SPEC_1"]["fields"]["verdict"] == "pass"
    assert "verdict" not in records["REQ_1"]["fields"]


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs", "srcdir": PROJECT}], indirect=True
)
def test_a_null_value_is_left_out(test_app: Any) -> None:
    """A field whose value is ``null`` is left out of ``fields``, which a reader reads
    as unset (its own default applies). Every other value is written: a default, which
    the reading project's may differ from (``asil``: ``QM``), and a typed empty
    (``tags``, ``constraints``: ``[]``); a link type without links is ``[]`` too."""
    app = test_app
    app.build()

    fields = _records(app)["REQ_2"]["fields"]
    assert fields == {
        "title": "The second",
        "tags": [],
        "constraints": [],
        "asil": "QM",
    }
    for record in _records(app).values():
        assert None not in record["fields"].values(), record["id"]
    assert _records(app)["REQ_2"]["links"]["parent_needs"] == []


@pytest.mark.parametrize(
    "test_app", [{"buildername": "needs_id", "srcdir": PROJECT}], indirect=True
)
def test_the_per_id_builder_writes_one_2a1_document_per_need(
    test_app: Any, snapshot: Any
) -> None:
    """One document per need, ``needs: [record]``, its record the one the needs
    builder writes."""
    app = test_app
    app.build()

    assert build_warnings(app) == [BETA]
    folder = Path(app.outdir, "needs_id")
    documents = {path.name: _read(path) for path in sorted(folder.iterdir())}
    assert sorted(documents) == snapshot
    for name, document in documents.items():
        assert document["format_version"] == "2a1"
        assert "versions" not in document
        assert len(document["needs"]) == 1
        assert f"{document['needs'][0]['id']}.json" == name
    assert documents["REQ_2.json"] == snapshot(exclude=props("created", "creator"))


# --- the option ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_needs_builder",
            "confoverrides": {"needs_reproducible_json": True},
        }
    ],
    indirect=True,
)
def test_the_default_writes_v1(test_app: Any) -> None:
    """At its default the option writes the v1 file, byte for byte what the
    ``needs_json_format_version = 1`` it stands for writes (the v1 snapshots of
    ``test_needs_builder.py`` pin the bytes themselves)."""
    app = test_app
    app.build()

    default = Path(app.outdir, "needs.json").read_bytes()
    data = json.loads(default)
    assert "format_version" not in data
    assert "versions" in data
    assert app.config.needs_json_format_version == 1

    app.config.needs_json_format_version = 1
    Path(app.outdir, "needs.json").unlink()
    app.builder.finish()
    assert Path(app.outdir, "needs.json").read_bytes() == default


@pytest.mark.parametrize("value", [2, "2", "1", "2a2", True, 1.0])
def test_an_unknown_value_warns_and_writes_v1(
    value: object, make_app: Any, tmp_path: Path
) -> None:
    """Any value but ``1`` and ``"2a1"`` is one ``needs.config`` warning, and the
    file is v1."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        f'extensions = ["sphinx_needs"]\nneeds_json_format_version = {value!r}\n'
    )
    (srcdir / "index.rst").write_text("T\n=\n\n.. req:: a\n   :id: REQ_001\n")
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert _config_warnings(app) == [
            f"WARNING: needs_json_format_version must be 1 or '2a1', not {value!r}; "
            "writing format version 1 [needs.config]"
        ]
        data = _needs_json(app)
        assert "format_version" not in data
        assert "REQ_001" in data["versions"][""]["needs"]
    finally:
        app.cleanup()


def test_the_option_is_read_from_ubproject_toml(make_app: Any, tmp_path: Path) -> None:
    """``[needs] json_format_version`` in ``ubproject.toml``."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_from_toml = "ubproject.toml"\n'
    )
    (srcdir / "ubproject.toml").write_text('[needs]\njson_format_version = "2a1"\n')
    (srcdir / "index.rst").write_text("T\n=\n\n.. req:: a\n   :id: REQ_001\n")
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert build_warnings(app) == [BETA]
        assert [r["id"] for r in _needs_json(app)["needs"]] == ["REQ_001"]
    finally:
        app.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": PROJECT,
            "confoverrides": {
                "needs_build_json": True,
                "needs_build_json_per_id": True,
            },
        }
    ],
    indirect=True,
)
def test_one_beta_warning_per_build(test_app: Any) -> None:
    """``needs_build_json`` and ``needs_build_json_per_id`` obey the option too, and
    a build that writes both warns once."""
    app = test_app
    app.build()

    assert [w for w in build_warnings(app) if "[needs.beta]" in w] == [BETA]
    assert _needs_json(app)["format_version"] == "2a1"
    per_id = _read(Path(app.outdir, "needs_id", "REQ_1.json"))
    assert per_id["format_version"] == "2a1"
    assert per_id["needs"] == [_records(app)["REQ_1"]]


# --- the v1 options under 2a1 ----------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": PROJECT,
            "confoverrides": {"needs_json_remove_defaults": True},
        }
    ],
    indirect=True,
)
def test_remove_defaults_is_ignored_with_a_warning(test_app: Any) -> None:
    app = test_app
    app.build()

    assert _config_warnings(app) == [
        "WARNING: needs_json_remove_defaults is ignored under "
        'needs_json_format_version "2a1": a 2a1 file writes every default, and '
        "carries no schema to restore one from [needs.config]"
    ]
    records = _records(app)
    assert records["REQ_2"]["fields"]["asil"] == "QM"
    assert records["REQ_2"]["fields"]["tags"] == []
    assert records["REQ_2"]["links"]["parent_needs"] == []


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": PROJECT,
            "confoverrides": {
                "needs_json_exclude_fields": [
                    "asil",
                    "implements",
                    "content",
                    "source",
                    "docname",
                    "lineno",
                    "sections",
                    "section_name",
                    "signature",
                    "external_url",
                    "is_import",
                    "is_external",
                    "lineno_content",
                ]
            },
        }
    ],
    indirect=True,
)
def test_exclude_fields_is_honoured(test_app: Any) -> None:
    """A field's or a link type's name leaves it out, ``content`` the content and
    ``source`` the hop list; a legacy location name has no 2a1 key, and warns once
    (``lineno_content`` among the defaults is written by neither format, and does
    not). ``collapse`` and ``hide`` are written once the list leaves them out."""
    app = test_app
    app.build()

    assert _config_warnings(app) == [
        "WARNING: needs_json_exclude_fields names 'docname', 'lineno', 'sections', "
        "'section_name', 'signature', 'external_url', 'is_import', 'is_external', which "
        'have no key under needs_json_format_version "2a1": they are read from the '
        "need's source; exclude 'source' to leave the source out [needs.config]"
    ]
    for record in _records(app).values():
        assert list(record) == ["id", "type", "fields", "links"]
        assert "asil" not in record["fields"]
        assert "implements" not in record["links"]
        assert record["fields"]["collapse"] is False
        assert record["fields"]["hide"] is False


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": PROJECT,
            "confoverrides": {"needs_json_exclude_fields": ["doctype", "parts"]},
        }
    ],
    indirect=True,
)
def test_exclude_fields_reaches_into_the_content(test_app: Any) -> None:
    """``doctype`` and ``parts``, keys of v1, are the content's keys of 2a1."""
    app = test_app
    app.build()

    assert _config_warnings(app) == []
    assert _records(app)["REQ_1"]["content"] == {
        "text": "A body with :np:`(p1) the part`."
    }


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": PROJECT,
            "confoverrides": {"needs_builder_filter": 'type == "spec"'},
        }
    ],
    indirect=True,
)
def test_the_builder_filter_is_honoured(test_app: Any) -> None:
    app = test_app
    app.build()

    assert list(_records(app)) == ["SPEC_1"]


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        (
            True,
            [
                {"id": "REQ_1", "part": "p1"},
                {"id": "REQ_3", "condition": 'status == "open"'},
            ],
        ),
        (False, [{"id": "REQ_1", "part": "p1"}, "REQ_3"]),
    ],
)
def test_link_conditions_are_optional(
    conditions: bool, expected: list[object], make_app: Any, tmp_path: Path
) -> None:
    """``needs_json_include_link_conditions = False`` drops ``condition``: a link
    left with neither part nor condition is a bare id."""
    import shutil

    srcdir = tmp_path / "src"
    shutil.copytree(Path(__file__).parent / PROJECT, srcdir)
    app = make_app(
        "needs",
        srcdir=srcdir,
        freshenv=True,
        confoverrides={"needs_json_include_link_conditions": conditions},
    )
    try:
        app.build()
        assert _records(app)["REQ_2"]["links"]["links"] == expected
    finally:
        app.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": PROJECT,
            "confoverrides": {"needs_reproducible_json": True},
        }
    ],
    indirect=True,
)
def test_reproducible_json_drops_created(test_app: Any) -> None:
    app = test_app
    app.build()

    assert list(_needs_json(app)) == ["format_version", "project", "creator", "needs"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": PROJECT,
            "confoverrides": {"needs_file": "old.json"},
        }
    ],
    indirect=True,
)
def test_needs_file_is_ignored_with_a_warning(test_app: Any) -> None:
    """``needs_file`` only accumulates the ``versions`` a 2a1 file does not have."""
    app = test_app
    Path(app.srcdir, "old.json").write_text(
        json.dumps(
            {
                "current_version": "0.9",
                "project": "up",
                "versions": {"0.9": {"needs": {"OLD_1": {"id": "OLD_1"}}}},
            }
        )
    )
    app.build()

    assert _config_warnings(app) == [
        'WARNING: needs_file is ignored under needs_json_format_version "2a1": a '
        "2a1 file has no versions to accumulate [needs.config]"
    ]
    data = _needs_json(app)
    assert "versions" not in data
    assert "OLD_1" not in _records(app)


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": PROJECT}], indirect=True
)
def test_a_build_that_writes_no_2a1_file_is_not_warned(test_app: Any) -> None:
    """The option set, and no needs.json written: no warning, so a ``-W`` build of
    another format passes."""
    app = test_app
    app.build()

    assert build_warnings(app) == []
    assert not Path(app.outdir, "needs.json").exists()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs_id",
            "srcdir": PROJECT,
            "confoverrides": {"needs_builder_filter": 'type == "spec"'},
        }
    ],
    indirect=True,
)
def test_the_per_id_builder_honours_the_builder_filter(test_app: Any) -> None:
    app = test_app
    app.build()

    assert sorted(p.name for p in Path(app.outdir, "needs_id").iterdir()) == [
        "SPEC_1.json"
    ]


def test_an_empty_semantic_location_is_written_empty() -> None:
    """A hop whose semantic location is determined and empty writes ``[]``; one where
    it is not determined (``None``) writes none."""
    from sphinx_needs._need_source import NeedSourceHop

    assert hop_to_json(NeedSourceHop(kind="page", semantic=())) == {
        "kind": "page",
        "semantic": [],
    }
    assert hop_to_json(NeedSourceHop(kind="page")) == {"kind": "page"}


def test_an_unnamed_project_writes_no_name(make_app: Any, tmp_path: Path) -> None:
    """A project that sets no ``project`` writes no ``project.name``, not Sphinx's
    placeholder, so that a reader names the file instead of every unnamed project
    alike."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nneeds_json_format_version = "2a1"\n'
    )
    (srcdir / "index.rst").write_text("T\n=\n\n.. req:: a\n   :id: REQ_001\n")
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert _needs_json(app)["project"] == {"version": ""}
    finally:
        app.cleanup()


def test_a_needs_file_without_versions_is_one_warning(
    make_app: Any, tmp_path: Path
) -> None:
    """Under format 1, a ``needs_file`` with no ``versions`` -- a 2a1 file, or no
    needs.json at all -- is one warning, and a new file is written (it raised a
    ``KeyError``)."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\nversion = "1.0"\nneeds_file = "old.json"\n'
    )
    (srcdir / "index.rst").write_text("T\n=\n\n.. req:: a\n   :id: REQ_001\n")
    (srcdir / "old.json").write_text(
        json.dumps({"format_version": "2a1", "project": {"name": "x"}, "needs": []})
    )
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert [w for w in build_warnings(app) if "[needs.json_load]" in w] == [
            "WARNING: needs_file <srcdir>/old.json has no versions to add the "
            "current one to (is it a needs.json of format 1?); a new file is written "
            "[needs.json_load]"
        ]
        data = _needs_json(app)
        assert list(data["versions"]) == ["1.0"]
        assert "REQ_001" in data["versions"]["1.0"]["needs"]
    finally:
        app.cleanup()


def test_excluding_a_field_named_source_says_the_source_goes_too(
    make_app: Any, tmp_path: Path
) -> None:
    """``source`` in ``needs_json_exclude_fields`` names both a field the project
    declares and the hop list: both are left out, and one warning says so."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(
        'extensions = ["sphinx_needs"]\n'
        'needs_json_format_version = "2a1"\n'
        'needs_fields = {"source": {"nullable": True}}\n'
        'needs_json_exclude_fields = ["source"]\n'
    )
    (srcdir / "index.rst").write_text(
        "T\n=\n\n.. req:: a\n   :id: REQ_001\n   :source: mine\n"
    )
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert _config_warnings(app) == [
            "WARNING: needs_json_exclude_fields names 'source', which is both a field "
            'of the project and, under needs_json_format_version "2a1", the need\'s '
            "source: both are left out [needs.config]"
        ]
        (record,) = _needs_json(app)["needs"]
        assert "source" not in record
        assert "source" not in record["fields"]
    finally:
        app.cleanup()
