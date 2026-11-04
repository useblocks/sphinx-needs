"""needimport and a record's template names: provenance, never instructions.

A needs.json record's ``content`` is already its templates' output, and its ``template``,
``pre_template``, ``post_template`` and ``jinja_content`` name files of the PRODUCING
project. ``needimport`` used to apply them again from the importing project's template
folder: the content was wrapped twice, Jinja in it was rendered twice, and every
templated record was lost where the importer had no such template. The conformance
corpus pins what is imported (``import-*`` cases); this pins sphinx-needs' deprecation
window for a record's pre and post templates, which are still applied where the
importer has the template (with one ``needs.deprecated`` per directive and template,
naming the directive's own option as the replacement) until 10.0.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import build_warnings
from tests.test_need_templates_incremental import _build, _edit, _write

CONF = 'extensions = ["sphinx_needs"]\nneeds_build_json = True\n'


def _needs_json(*records: dict[str, Any]) -> str:
    return json.dumps(
        {
            "current_version": "1.0",
            "versions": {"1.0": {"needs": {r["id"]: r for r in records}}},
        }
    )


def _record(need_id: str, **fields: Any) -> dict[str, Any]:
    return {
        "id": need_id,
        "type": "spec",
        "title": need_id,
        "content": "Body.",
    } | fields


RECORDS = _needs_json(
    _record("A_1", pre_template="pre", pre_content="PRODUCER PRE"),
    _record("A_2", pre_template="pre", post_template="gone"),
    _record("A_3", template="wrap", content="PRODUCER WRAP Body."),
)

INDEX = """\
Index
=====

.. needimport:: a.json

.. needimport:: a.json
   :id_prefix: OWN_
   :pre_template: own
"""


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), INDEX),
                (Path("a.json"), RECORDS),
                (Path("needs_templates", "pre.need"), "IMPORTER PRE {{ id }}\n"),
                (Path("needs_templates", "own.need"), "OWN PRE {{ id }}\n"),
                (Path("needs_templates", "wrap.need"), "IMPORTER WRAP {{ content }}\n"),
            ],
        }
    ],
    indirect=True,
)
def test_a_records_decoration_is_deprecated_where_it_is_still_applied(
    test_app: Any,
) -> None:
    app = test_app
    app.build()
    needs = _needs(app)
    # the record's pre template, which the importer has: applied, from the importer
    assert needs["A_1"]["pre_content"] == "IMPORTER PRE A_1"
    assert needs["A_2"]["pre_content"] == "IMPORTER PRE A_2"
    # its post template, which the importer has not: dropped, nothing reported
    assert needs["A_2"]["post_template"] is None
    assert needs["A_2"]["post_content"] is None
    # its content template: never applied again
    assert needs["A_3"]["content"] == "PRODUCER WRAP Body."
    assert needs["A_3"]["template"] is None
    # the directive's own option replaces the record's, with no deprecation
    assert needs["OWN_A_1"]["pre_content"] == "OWN PRE OWN_A_1"
    assert needs["OWN_A_3"]["pre_content"] == "OWN PRE OWN_A_3"
    warnings = build_warnings(app)
    deprecated = [w for w in warnings if "[needs.deprecated]" in w]
    # once for the directive and template, though two records name it
    assert len(deprecated) == 1, warnings
    assert "pre_template 'pre'" in deprecated[0]
    assert ":pre_template: pre" in deprecated[0]
    assert "10.0" in deprecated[0]
    assert deprecated[0].startswith("<srcdir>/index.rst:4:")
    assert not any("[needs.template_" in w for w in warnings), warnings


PRODUCER_RECORD = _needs_json(_record("X_1", pre_template="producer_only"))
"""A record naming a template of the PRODUCER, which the importer has not: the normal
state of a cross-project import from a producer that decorates its needs."""

IMPORT_FILES = {
    "conf.py": CONF,
    "index.rst": "Index\n=====\n\n.. toctree::\n\n   imp\n   plain\n",
    "imp.rst": "Imp\n===\n\n.. needimport:: a.json\n",
    "plain.rst": "Plain\n=====\n\n.. req:: Plain\n   :id: REQ_PLAIN\n",
    "a.json": PRODUCER_RECORD,
}


@pytest.mark.parametrize("folder", [True, False], ids=["folder", "no-folder"])
def test_a_records_missing_decoration_re_reads_nothing(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, folder: bool
) -> None:
    """The existence probe for a record's pre/post template notes no missing file:
    builds with nothing changed read nothing, with the template folder present (other
    templates in it) or absent."""
    files = dict(IMPORT_FILES)
    if folder:
        files["needs_templates/other.need"] = "OTHER\n"
    srcdir = _write(tmp_path / "src", files)
    _, needs, _ = _build(make_app, srcdir, fresh=True)
    assert needs["X_1"]["pre_content"] is None
    reads = [_build(make_app, srcdir)[0] for _ in range(3)]
    assert reads == [[], [], []]
    if folder:
        # an editor that saves by writing a new file and renaming it over the old one
        # moves the folder's modification time: it is no dependency, so nothing is read
        other = srcdir / "needs_templates" / "other.need"
        saved = other.with_suffix(".tmp")
        saved.write_text("OTHER v2\n", encoding="utf-8")
        os.replace(saved, other)
        assert _build(make_app, srcdir)[0] == []


@pytest.mark.parametrize("parallel", [1, 2], ids=["serial", "parallel"])
def test_creating_and_deleting_a_records_decoration_re_reads_the_import_page(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, parallel: int
) -> None:
    """Creating the template a record names re-reads the import page (it is recorded as
    a probe of the page, merged from a parallel reader too) and applies it; deleting it
    re-reads the page again (the file is a dependency)."""
    if parallel > 1 and not parallel_available:
        pytest.skip("parallel reading is not available")
    # enough documents that a parallel build reads them in parallel
    extra = {f"p{i}.rst": f"P{i}\n==\n\ntext\n" for i in range(8)}
    index = IMPORT_FILES["index.rst"] + "".join(f"   p{i}\n" for i in range(8))
    srcdir = _write(
        tmp_path / "src",
        {
            **IMPORT_FILES,
            **extra,
            "index.rst": index,
            "needs_templates/other.need": "OTHER\n",
        },
    )
    _build(make_app, srcdir, fresh=True, parallel=parallel)
    _edit(srcdir / "needs_templates" / "producer_only.need", "LATER {{ id }}\n")
    read, needs, _ = _build(make_app, srcdir)
    assert read == ["imp"]
    assert needs["X_1"]["pre_content"] == "LATER X_1"
    assert _build(make_app, srcdir)[0] == []

    (srcdir / "needs_templates" / "producer_only.need").unlink()
    read, needs, _ = _build(make_app, srcdir)
    assert read == ["imp"]
    assert needs["X_1"]["pre_content"] is None


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), CONF),
                (Path("index.rst"), "Index\n=====\n\n.. needimport:: a.json\n"),
                (
                    Path("a.json"),
                    _needs_json(_record("B_1", pre_template="x", post_template="x")),
                ),
                (Path("needs_templates", "x.need"), "X {{ id }}\n"),
            ],
        }
    ],
    indirect=True,
)
def test_one_template_as_pre_and_post_is_two_deprecations(test_app: Any) -> None:
    """The deprecation is once per directive, OPTION and template: a record naming one
    template as both its pre and its post template is two."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["B_1"]["pre_content"] == "X B_1"
    assert needs["B_1"]["post_content"] == "X B_1"
    deprecated = [w for w in build_warnings(app) if "[needs.deprecated]" in w]
    assert len(deprecated) == 2, deprecated
    assert sum("the pre_template 'x'" in w for w in deprecated) == 1
    assert sum("the post_template 'x'" in w for w in deprecated) == 1
