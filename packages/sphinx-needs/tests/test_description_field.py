"""A field or link type named ``description`` on the record routes (#2465).

sphinx-needs before 4.0 wrote a need's content to needs.json as ``description`` and
wrote no ``content`` at all; every later writer writes ``content``, or leaves it to the
version's ``needs_schema`` default. So the legacy ``description`` is the content only
when a record has no ``content`` key once its schema defaults are merged
(``ub_needs_exchange`` contract section 6.3). A record that has one -- even an empty
one -- keeps its ``description`` as the field (or link type) of that name, so a
project's own needs.json reads back as written, on ``needimport`` and on
``needs_external_needs`` alike; a genuine pre-4.0 file still reads its ``description``
as the content, whatever the reading project declares.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

READERS = ("import", "external")

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
    dict(directive="impl", title="Implementation", prefix="I_", color="#FEDCD2", style="node"),
]
show_warning_types = True
"""

DECLARED = 'needs_fields = {"description": {"nullable": True}}\n'
"""The project declares a field named ``description``."""

PAGE = """\
Index
=====

.. req:: A target
   :id: REQ_T

"""

ISSUE_FILE = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "IMP_1": {
                        "id": "IMP_1",
                        "type": "req",
                        "title": "Imported",
                        "content": "",
                        "description": "kept?",
                    }
                }
            }
        },
    }
)
"""The file of the issue: a record with an empty ``content`` and a ``description``."""

PRE_3_0_FILE = json.dumps(
    {
        "created": "2017-08-25T21:17:17.640061",
        "current_version": "0.1.33",
        "project": "Sphinx-Needs",
        "versions": {
            "0.1.33": {
                "created": "2017-08-25T21:17:17.640058",
                "needs": {
                    "TEST_01": {
                        "description": "TEST IMPORT DESCRIPTION",
                        "id": "TEST_01",
                        "links": [],
                        "status": None,
                        "tags": [],
                        "title": "TEST IMPORT TITLE",
                        "type": "impl",
                        "type_name": "Implementation",
                    }
                },
                "needs_amount": 1,
            }
        },
    }
)
"""What sphinx-needs wrote before 3.0: no ``content``, the content as ``description``."""

THREE_X_FILE = json.dumps(
    {
        "current_version": "0.1",
        "project": "three",
        "versions": {
            "0.1": {
                "needs_amount": 2,
                "needs_defaults_removed": True,
                "needs_schema": {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "field_type": "core"},
                        "description": {
                            "type": "string",
                            "field_type": "core",
                            "default": "",
                        },
                    },
                },
                "needs": {
                    "TEST_01": {
                        "id": "TEST_01",
                        "type": "impl",
                        "title": "TEST IMPORT TITLE",
                        "description": "TEST IMPORT DESCRIPTION",
                    },
                    "TEST_02": {"id": "TEST_02", "type": "impl", "title": "no body"},
                },
            }
        },
    }
)
"""What a 3.x writer wrote: a ``needs_schema`` whose ``description`` default fills a
record left without it, its defaults removed, still no ``content``."""


def _project(
    tmp_path: Path,
    reader: str,
    data: str,
    *,
    conf: str = DECLARED,
    options: tuple[str, ...] = (),
) -> Path:
    """A project reading ``data`` (``data.json``) by ``reader``; return its srcdir."""
    srcdir = tmp_path / f"reader_{reader}"
    srcdir.mkdir()
    (srcdir / "data.json").write_text(data, encoding="utf-8")
    index = PAGE
    extra = ""
    if reader == "import":
        index += "\n".join([".. needimport:: data.json", *(f"   {o}" for o in options)])
        index += "\n"
    else:
        extra = (
            "needs_external_needs = [{'base_url': 'http://ext.example/docs/', "
            "'json_path': 'data.json'}]\n"
        )
    (srcdir / "conf.py").write_text(CONF + conf + extra, encoding="utf-8")
    (srcdir / "index.rst").write_text(index, encoding="utf-8")
    return srcdir


def _build(make_app: Any, srcdir: Path, buildername: str = "html") -> Any:
    app = make_app(
        srcdir=srcdir, buildername=buildername, freshenv=True, warning=io.StringIO()
    )
    app.build()
    return app


def _warnings(app: Any) -> list[str]:
    """:func:`build_warnings` without the notes a second application in one process
    logs as it registers the extensions again."""
    return [w for w in build_warnings(app) if "is already registered" not in w]


def _needs(app: Any) -> dict[str, dict[str, Any]]:
    """The needs the build read, by id, as plain dicts."""
    return {
        key: dict(need)
        for key, need in SphinxNeedsData(app.env).get_needs_view().items()
    }


@pytest.mark.parametrize("reader", READERS)
def test_a_declared_description_is_kept_beside_an_empty_content(
    tmp_path: Path, make_app: Any, reader: str
) -> None:
    """The issue's file: the field keeps its value, the content stays empty."""
    app = _build(make_app, _project(tmp_path, reader, ISSUE_FILE))
    assert _warnings(app) == []
    need = _needs(app)["IMP_1"]
    assert (need["description"], need["content"]) == ("kept?", "")


OWN_PAGE = """\
Own
===

.. req:: Own need
   :id: OWN_1
   :description: own text

.. req:: Own with body
   :id: OWN_2
   :description: own text 2

   the body

.. req:: Bare need
   :id: OWN_3
"""


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("remove_defaults", [False, True], ids=["full", "no-defaults"])
def test_a_project_s_own_needs_json_reads_back_as_written(
    tmp_path: Path, make_app: Any, reader: str, remove_defaults: bool
) -> None:
    """A project declaring ``description`` writes a body-less need as ``"content": ""``
    (or, with ``needs_json_remove_defaults``, leaves ``content`` to the schema default)
    beside its ``description``; read again, the field is the field and the content the
    content. A bare need (no body, no ``description``) imports too: without defaults
    its nullable field's ``null`` default is not taken as its content."""
    writer = tmp_path / "writer"
    writer.mkdir()
    (writer / "conf.py").write_text(
        CONF + DECLARED + f"needs_json_remove_defaults = {remove_defaults}\n",
        encoding="utf-8",
    )
    (writer / "index.rst").write_text(OWN_PAGE, encoding="utf-8")
    written = _build(make_app, writer, "needs")
    assert _warnings(written) == []
    text = Path(written.outdir, "needs.json").read_text(encoding="utf-8")
    data = json.loads(text)
    record = data["versions"][data["current_version"]]["needs"]["OWN_1"]
    # the two shapes a >= 4.0 writer gives a body-less need
    if remove_defaults:
        assert "content" not in record
    else:
        assert record["content"] == ""
    assert record["description"] == "own text"

    app = _build(make_app, _project(tmp_path, reader, text))
    assert _warnings(app) == []
    needs = _needs(app)
    assert (needs["OWN_1"]["description"], needs["OWN_1"]["content"]) == (
        "own text",
        "",
    )
    assert (needs["OWN_2"]["description"], needs["OWN_2"]["content"]) == (
        "own text 2",
        "the body",
    )
    assert (needs["OWN_3"]["description"], needs["OWN_3"]["content"]) == (None, "")


@pytest.mark.parametrize("reader", READERS)
def test_a_link_type_named_description_is_kept(
    tmp_path: Path, make_app: Any, reader: str
) -> None:
    """A LINK type named ``description`` beside an empty ``content``: the need keeps
    the link, where the legacy rename made the list its content and refused the need."""
    data = json.dumps(
        {
            "current_version": "1.0",
            "versions": {
                "1.0": {
                    "needs": {
                        "IMP_1": {
                            "id": "IMP_1",
                            "type": "req",
                            "title": "Imported",
                            "content": "",
                            "description": ["REQ_T"],
                        }
                    }
                }
            },
        }
    )
    srcdir = _project(
        tmp_path, reader, data, conf='needs_links = {"description": {}}\n'
    )
    app = _build(make_app, srcdir)
    assert _warnings(app) == []
    need = _needs(app)["IMP_1"]
    assert (need["description"], need["content"]) == (["REQ_T"], "")


@pytest.mark.parametrize("reader", READERS)
@pytest.mark.parametrize("data", [PRE_3_0_FILE, THREE_X_FILE], ids=["pre-3-0", "3-x"])
@pytest.mark.parametrize(
    ("conf", "field"),
    [
        (DECLARED, "description"),
        ('needs_fields = {"Description": {"nullable": True}}\n', "Description"),
    ],
    ids=["declared", "declared-capitalised"],
)
def test_a_pre_4_0_file_reads_its_description_as_the_content(
    tmp_path: Path, make_app: Any, reader: str, data: str, conf: str, field: str
) -> None:
    """A file written before 4.0 has no ``content`` anywhere: its ``description`` is
    the content, also in a project that declares a field of that name, in either case."""
    app = _build(make_app, _project(tmp_path, reader, data, conf=conf))
    assert _warnings(app) == []
    need = _needs(app)["TEST_01"]
    assert need["content"] == "TEST IMPORT DESCRIPTION"
    assert need[field] is None


def test_a_body_less_record_is_no_doctype_fallback(
    tmp_path: Path, make_app: Any
) -> None:
    """``:parse_by_doctype:`` with a doctype the project cannot parse warns only for a
    record whose content is not blank: a declared ``description`` is not content."""
    data = json.dumps(
        {
            "current_version": "1.0",
            "versions": {
                "1.0": {
                    "creator": {"program": "sphinx_needs", "version": "9.2.0"},
                    "needs": {
                        "DT_1": {
                            "id": "DT_1",
                            "type": "req",
                            "title": "dt",
                            "content": "",
                            "description": "field text",
                            "doctype": ".xyz",
                        }
                    },
                }
            },
        }
    )
    srcdir = _project(tmp_path, "import", data, options=(":parse_by_doctype: true",))
    app = _build(make_app, srcdir)
    assert _warnings(app) == []
    need = _needs(app)["DT_1"]
    assert (need["description"], need["content"]) == ("field text", "")


INGEST_DRIVER = """\
import json
from pathlib import Path

from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import ingest_need_record
from sphinx_needs.need_item import NeedItemSource


class IngestRecords(SphinxDirective):
    \"\"\"Creates a need from each record of ``records.json`` through
    ``ingest_need_record``, as an extension building records does.\"\"\"

    def run(self):
        path = Path(self.env.srcdir, "records.json")
        created = []
        for record in json.loads(path.read_text(encoding="utf-8")):
            nodes, _ = ingest_need_record(
                self.env.app,
                self.state,
                record,
                need_source=NeedItemSource.on_page(
                    self.env.docname, lineno=self.lineno
                ),
            )
            created.extend(nodes)
        return created


def setup(app):
    app.add_directive("ingest-records", IngestRecords)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
"""


def test_ingest_need_record_takes_a_description_as_content_only_without_one(
    tmp_path: Path, make_app: Any
) -> None:
    """The record path itself, with no needs.json reader before it: a record with no
    ``content`` key has its ``description`` taken as its content, and one with a
    ``content``, even an empty one, keeps its declared ``description`` field."""
    srcdir = tmp_path / "ingest"
    srcdir.mkdir()
    (srcdir / "ingest_driver.py").write_text(INGEST_DRIVER, encoding="utf-8")
    (srcdir / "records.json").write_text(
        json.dumps(
            [
                {"id": "ING_1", "type": "req", "title": "t", "description": "x"},
                {
                    "id": "ING_2",
                    "type": "req",
                    "title": "t",
                    "content": "",
                    "description": "x",
                },
            ]
        ),
        encoding="utf-8",
    )
    (srcdir / "conf.py").write_text(
        "import sys\nfrom pathlib import Path\n\n"
        "sys.path.insert(0, str(Path(__file__).parent))\n"
        + CONF.replace('["sphinx_needs"]', '["sphinx_needs", "ingest_driver"]')
        + DECLARED,
        encoding="utf-8",
    )
    (srcdir / "index.rst").write_text(
        "Ingest\n======\n\n.. ingest-records::\n", encoding="utf-8"
    )
    app = _build(make_app, srcdir)
    assert _warnings(app) == []
    needs = _needs(app)
    assert (needs["ING_1"]["description"], needs["ING_1"]["content"]) == (None, "x")
    assert (needs["ING_2"]["description"], needs["ING_2"]["content"]) == ("x", "")
