"""A field per reference marker, through a build: one tree, several fields.

The ``need_id_refs`` fixture with its source replaced by Doxygen-style comments:
``\\satisfies`` sends its references to ``impl_url``, ``@verifies`` and ``\\verifies``
to ``test_url``, the plain ``@need-ids:`` marker to the project's ``ref_url_field``
(``code_url``), and ``\\ignored`` to no field at all.
"""

import os
from pathlib import Path

from sphinx_codelinks.sphinx_extension.need_id_refs import need_id_refs_store
from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import _build, _json, _MakeApp, _project, _url

SOURCE = (
    "/// \\satisfies REQ_001\n"  # 1
    "void start() {}\n"
    "/// @verifies REQ_001\n"  # 3
    "void test_start() {}\n"
    "// @need-ids: REQ_002\n"  # 5
    "void helper() {}\n"
    "/// \\satisfies REQ_002 \\verifies REQ_003\n"  # 7
    "void both() {}\n"
    "/// \\ignored REQ_003 NOSUCH_ID\n"  # 9
    "void ignored() {}\n"
)

MARKERS = (
    "\n[codelinks.projects.src.analyse.oneline_comment_style]\n"
    'start_sequence = "@@"\n'
    "[codelinks.projects.src.analyse.need_id_refs]\n"
    "markers = [\n"
    '  "@need-ids:",\n'
    '  { marker = "\\\\satisfies", field = "impl_url" },\n'
    '  { marker = "@verifies", field = "test_url" },\n'
    '  { marker = "\\\\verifies", field = "test_url" },\n'
    '  { marker = "\\\\ignored", field = "" },\n'
    "]\n"
)

FIELDS = ("code_url", "impl_url", "test_url")


def _fields(app: object) -> dict[str, dict[str, object]]:
    needs = _json(app)["needs"]  # ty: ignore[invalid-argument-type]
    return {
        need_id: {name: need.get(name, "<absent>") for name in FIELDS}
        for need_id, need in needs.items()
    }


def test_each_marker_fills_its_own_field(tmp_path: Path, make_app: _MakeApp) -> None:
    """``impl_url`` and ``test_url`` from one tree; the plain marker still goes to
    ``ref_url_field``; ``field = ""`` attaches nothing and, making no record, warns
    about no unknown id either; two markers on one line each keep their own ids."""
    commit = _project(
        tmp_path, toml_extra=MARKERS, files={"src/refs.cpp": SOURCE}
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == []
    assert _fields(app) == {
        "REQ_001": {
            "code_url": None,
            "impl_url": [_url(commit, 1)],
            "test_url": [_url(commit, 3)],
        },
        "REQ_002": {
            "code_url": [_url(commit, 5)],
            "impl_url": [_url(commit, 7)],
            "test_url": None,
        },
        "REQ_003": {
            "code_url": None,
            "impl_url": None,
            "test_url": [_url(commit, 7)],
        },
        "SPEC_001": {"code_url": None, "impl_url": None, "test_url": None},
    }
    # the marker without a field makes no record at all
    markers = {ref.marker for refs in need_id_refs_store(app.env).values() for ref in refs}
    assert markers == {"@need-ids:", "\\satisfies", "@verifies", "\\verifies"}
    properties = _json(app)["needs_schema"]["properties"]
    for name in FIELDS:
        assert properties[name]["type"] == ["array", "null"]


def test_ref_url_field_is_not_registered_when_every_marker_is_a_table(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    markers = MARKERS.replace('  "@need-ids:",\n', "")
    source = SOURCE.replace("// @need-ids: REQ_002\n", "// nothing here\n")
    commit = _project(tmp_path, toml_extra=markers, files={"src/refs.cpp": source})
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == []
    assert "code_url" not in _json(app)["needs_schema"]["properties"]
    assert _json(app)["needs"]["REQ_001"]["impl_url"] == [_url(commit, 1)]


def test_python_configuration_takes_a_marker_dict(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """In ``conf.py`` the table is a dict."""
    conf = (
        "src_trace_config_from_toml = None\n"
        "src_trace_set_remote_url = True\n"
        "src_trace_projects = {'src': {\n"
        "    'remote_url_pattern': "
        "'https://github.com/example/demo/blob/{commit}/{path}#L{line}',\n"
        "    'source_discover': {'src_dir': '../src', 'comment_type': 'cpp'},\n"
        "    'analyse': {\n"
        "        'oneline_comment_style': {'start_sequence': '@@'},\n"
        "        'need_id_refs': {'markers': [\n"
        "            {'marker': '\\\\satisfies', 'field': 'impl_url'},\n"
        "            {'marker': '@verifies', 'field': 'test_url'},\n"
        "        ]},\n"
        "    },\n"
        "}}\n"
    )
    source = "/// \\satisfies REQ_001\nvoid a() {}\n/// @verifies REQ_001\nvoid b() {}\n"
    commit = _project(
        tmp_path, files={"src/refs.cpp": source}, append={"docs/conf.py": conf}
    )
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == []
    need = _json(app)["needs"]["REQ_001"]
    assert need["impl_url"] == [_url(commit, 1)]
    assert need["test_url"] == [_url(commit, 3)]


def test_a_changed_marker_moves_the_reference_to_the_other_field(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """An incremental build after ``\\satisfies REQ_001`` became ``\\verifies
    REQ_001``: ``impl_url`` loses the reference, ``test_url`` gains it."""
    commit = _project(tmp_path, toml_extra=MARKERS, files={"src/refs.cpp": SOURCE})
    _build(tmp_path, make_app)
    source = tmp_path / "src" / "refs.cpp"
    source.write_text(
        SOURCE.replace("/// \\satisfies REQ_001\n", "/// \\verifies REQ_001\n"),
        encoding="utf-8",
    )
    later = source.stat().st_mtime + 10
    os.utime(source, (later, later))
    app = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in app._status.getvalue()
    assert _fields(app)["REQ_001"] == {
        "code_url": None,
        "impl_url": None,
        "test_url": [_url(commit, 1), _url(commit, 3)],
    }
