"""A changed ``needs_types`` entry is applied on an incremental build (#2287).

``needs_types`` is registered with ``rebuild = "html"``, so a change to it re-read no
document, and the needs of every unchanged document kept what the previous entries gave
them. Since a need type declares fields, link types, their defaults and ``derive`` rules,
and its ``title`` and ``prefix`` are stored on each need, a changed entry changes need
data: the needs an incremental build ends with now equal those of a fresh build.

The option itself stays ``"html"``: the GitHub service appends its need types to it in
place after Sphinx compares the configurations (#2265), so ``"env"`` would re-read every
document on every build. The entries are compared once the list is complete instead, and
an unchanged list re-reads nothing more than the changed documents.
"""

from __future__ import annotations

import json
import pickle
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
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

    The GitHub service's need types are appended to the option on every build, so the
    comparison must see them on both sides rather than re-read everything each time.
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
