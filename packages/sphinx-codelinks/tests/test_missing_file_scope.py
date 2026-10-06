# @Test suite for a src-trace file scope naming no file, TEST_MISSING_FILE_1, test, [IMPL_DISC_1]
"""A ``:file:`` scope naming no file warns at the directive, and the build goes on (#2069).

Every case builds a copy of ``doc_test/need_id_refs`` (see ``test_need_id_refs``) whose
``index`` traces ``:file: traced.cpp`` only: a one-line need and a reference.
"""

from pathlib import Path

import sphinx
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import FIXTURE, _build, _json, _MakeApp, _project, _refs

#: Sphinx 8 renders a warning's ``[type.subtype]`` itself; 7.4 does not
_SHOWS_WARNING_TYPES = sphinx.version_info >= (8,)

INDEX = (FIXTURE / "docs" / "index.rst").read_text(encoding="utf-8")
DIRECTIVE = ".. src-trace::\n   :project: src\n"
assert DIRECTIVE in INDEX
#: the line of ``index``'s directive, where the warning is located
LINE = INDEX.splitlines().index(".. src-trace::") + 1

FILE_SCOPE = {
    "docs/index.rst": INDEX.replace(DIRECTIVE, f"{DIRECTIVE}   :file: traced.cpp\n")
}
SOURCE = "// @traced need, IMPL_TRACED\n// @need-ids: REQ_002\n"


def _status(app: SphinxTestApp) -> str:
    return strip_colors(app._status.getvalue())


def _missing(root: Path) -> str:
    suffix = " [codelinks.missing_file]" if _SHOWS_WARNING_TYPES else ""
    src = (root / "src").resolve().as_posix()
    return (
        f"<srcdir>/index.rst:{LINE}: WARNING: src-trace: traced.cpp is not a file "
        f"below {src}{suffix}"
    )


def _codelinks_warnings(app: SphinxTestApp) -> list[str]:
    """The build's warnings but the unknown-id one every fixture build has, and the
    node re-registration a second application in one test reports."""
    return [
        w
        for w in build_warnings(app)
        if "NOSUCH_ID" not in w and "already registered" not in w
    ]


def test_a_removed_file_warns_at_the_directive_and_the_build_goes_on(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """The target removed between builds: the document is read again, warns once at
    the directive, and its need and references are gone; re-created, the next build
    reads the document again and they are back."""
    _project(tmp_path, files={**FILE_SCOPE, "src/traced.cpp": SOURCE})
    first = _build(tmp_path, make_app)
    assert "IMPL_TRACED" in _json(first)["needs"]

    (tmp_path / "src" / "traced.cpp").unlink()
    removed = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(removed)
    assert _codelinks_warnings(removed) == [_missing(tmp_path)]
    assert "IMPL_TRACED" not in _json(removed)["needs"]
    assert _refs(removed)["REQ_002"] is None

    (tmp_path / "src" / "traced.cpp").write_text(SOURCE, encoding="utf-8")
    back = _build(tmp_path, make_app, freshenv=False)

    assert "0 added, 1 changed, 0 removed" in _status(back)
    assert "IMPL_TRACED" in _json(back)["needs"]
    assert _refs(back)["REQ_002"] is not None


def test_a_file_scope_naming_no_file_warns_in_a_fresh_build(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _project(tmp_path, files=FILE_SCOPE)
    app = _build(tmp_path, make_app)

    assert _codelinks_warnings(app) == [_missing(tmp_path)]
    assert "IMPL_TRACED" not in _json(app)["needs"]
