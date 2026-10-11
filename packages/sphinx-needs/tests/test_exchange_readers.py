"""The two readers of a needs exchange file, ``needimport`` and ``needs_external_needs``,
on one corpus.

Each case is built twice from the same needs.json: once imported by a ``needimport``
directive on ``index.rst``, once loaded as an external source (a ``needs_external_needs``
config override). Both read the file through ``sphinx_needs.exchange`` and create each
need through one record path, so most rows assert the SAME outcome for both readers;
the rows where the two are different by design (the ten-field table, where a need is
recorded, its ``parts``) assert the difference as the rule.

The outcomes are the warnings of the build (``-W`` off, the list asserted whole) and the
needs read back from the build's own ``needs.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.parallel import parallel_available

from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs_testkit import build_warnings
from tests.util import needs_by_id

READERS = ("import", "external")

CONF = """\
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
extensions = ["sphinx_needs", "exchange_ingest_driver"]
project = "reader"
version = "9.9"
needs_build_json = True
needs_reproducible_json = True
needs_builder_filter = "True"
needs_id_regex = r"^[A-Z][A-Z0-9_]*$"
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
    dict(directive="spec", title="Specification", prefix="S_", color="#FEDCD2", style="node"),
]
needs_fields = {"priority": {"schema": {"type": "string"}}}
show_warning_types = True
"""
"""The reading project: its ``needs_id_regex`` is one a lowercase or dashed id breaks."""

DRIVER = '''\
"""Creates one need from a record the way sphinx-codelinks does: through
``ingest_need_record``, with a source that is neither an import nor external."""

from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from sphinx_needs.api import InvalidNeedException, ingest_need_record
from sphinx_needs.need_item import NeedItemSourceUnknown

logger = logging.getLogger(__name__)


class IngestProbe(SphinxDirective):
    required_arguments = 1

    def run(self):
        record = {"id": self.arguments[0], "type": "req", "title": "from a comment"}
        try:
            created, _ = ingest_need_record(
                self.env.app,
                self.state,
                record,
                need_source=NeedItemSourceUnknown(
                    docname=self.env.docname, lineno=self.lineno
                ),
            )
        except InvalidNeedException as err:
            logger.warning(
                f"Need {record['id']!r} could not be ingested: {err.message}",
                type="needs",
                subtype="test_ingest",
                location=self.get_location(),
            )
            return []
        return created


def setup(app):
    app.add_directive("ingest-probe", IngestProbe)
    return {"parallel_read_safe": True, "parallel_write_safe": True}
'''

PAGE = """\
Index
=====

.. req:: local need
   :id: LOCAL_001

   Local body.

"""
"""Every project's ``index.rst`` starts with a need of the project, on line 4; the
``needimport`` of the import reader follows on line 9."""

PAGE_NEED_LINE = 4
IMPORT_LINE = 9
BASE_URL = "http://ext.example/docs/"


def rec(need_id: Any, **fields: Any) -> dict[str, Any]:
    """A need record of type ``req``."""
    return {"id": need_id, "type": "req", "title": f"title {need_id}", **fields}


def envelope(needs: Any, *, version: str = "1.0", **version_keys: Any) -> str:
    """A one-version needs.json holding ``needs``, as text."""
    return json.dumps(
        {
            "project": "source",
            "current_version": version,
            "versions": {version: {"needs": needs, **version_keys}},
        }
    )


def project(
    reader: str,
    data: str | None,
    *,
    options: tuple[str, ...] = (),
    source: dict[str, Any] | None = None,
    files: dict[str, str] | None = None,
    imports: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
    sources: list[dict[str, Any]] | None = None,
    page_extra: str = "",
    **params: Any,
) -> dict[str, Any]:
    """The ``test_app`` parameters of one reader of ``data`` (``data.json``).

    :param options: The import reader's directive options (``":name: value"``).
    :param source: The external reader's source keys, beside ``base_url`` and
        ``json_path``.
    :param files: Further files of the project, by name.
    :param imports: Instead of one ``needimport`` of ``data.json``, these
        ``(file, options)`` (import reader).
    :param sources: Instead of one source of ``data.json``, these (external reader).
    :param page_extra: Text appended to ``index.rst``.
    """
    all_files: dict[str, str] = {
        "conf.py": CONF,
        "exchange_ingest_driver.py": DRIVER,
        **(files or {}),
    }
    if data is not None:
        all_files["data.json"] = data
    index = PAGE
    confoverrides: dict[str, Any] = {}
    if reader == "import":
        for name, opts in imports or (("data.json", options),):
            index += "\n".join([f".. needimport:: {name}", *(f"   {o}" for o in opts)])
            index += "\n\n"
    else:
        confoverrides["needs_external_needs"] = (
            sources
            if sources is not None
            else [{"base_url": BASE_URL, "json_path": "data.json", **(source or {})}]
        )
    index += page_extra
    all_files["index.rst"] = index
    return {
        "buildername": "html",
        "files": [(Path(name), text) for name, text in all_files.items()],
        "confoverrides": confoverrides,
        **params,
    }


def both(*args: Any, **kwargs: Any) -> list[Any]:
    """One ``test_app`` parameter per reader, ``reader`` passed beside it."""
    return [
        pytest.param(project(reader, *args, **kwargs), reader, id=reader)
        for reader in READERS
    ]


def at_import(message: str, code: str, line: int = IMPORT_LINE) -> str:
    """A warning located at the import reader's directive."""
    return f"<srcdir>/index.rst:{line}: WARNING: {message} [needs.{code}]"


def unlocated(message: str, code: str) -> str:
    return f"WARNING: {message} [needs.{code}]"


def from_file(app: SphinxTestApp) -> dict[str, dict[str, Any]]:
    """The needs of the build's needs.json that came from the file (not ``LOCAL_001``,
    unless the file's own replaced it)."""
    return {k: v for k, v in needs_by_id(app).items() if k != "LOCAL_001"}


DATA_PATH = "<srcdir>/data.json"


def diagnostic(reader: str, message: str, path: str) -> str:
    """How each reader reports a record or version diagnostic of the file."""
    if reader == "import":
        return at_import(
            f"Needs import file {DATA_PATH}: {message} (at {path})", "needimport"
        )
    return unlocated(
        f"External needs source 'data.json': {message} (at {path})", "external_needs"
    )


def refused_source(reader: str, message: str) -> str:
    """How each reader reports a file it cannot read a single record from."""
    if reader == "import":
        return at_import(
            f"Could not load needs import file {DATA_PATH}: {message}", "needimport"
        )
    return unlocated(
        f"Could not load external needs from 'data.json': {message}", "external_needs"
    )


def refused_need(
    reader: str, need_id: str, message: str, file: str = "data.json"
) -> str:
    """How each reader reports a record it cannot create a need from."""
    if reader == "import":
        return at_import(
            f"Need {need_id!r} could not be imported: {message}", "import_need"
        )
    return unlocated(
        f"External need {need_id!r} in {file!r} could not be added: {message}",
        "load_external_need",
    )


# ------------------------------------------------------------------------------------
# R2: the map key is the id (#1414); a missing or non-string id no longer crashes (#2158)


@pytest.mark.parametrize(
    ("test_app", "reader"),
    both(
        envelope(
            {
                "REQ_001": rec("REQ_001"),
                "REQ_012": rec("REQ_001", title="under key REQ_012"),
                "NUM_ID": rec(5, title="numeric id"),
                "NO_ID": {"type": "req", "title": "no id"},
            }
        )
    ),
    indirect=["test_app"],
)
def test_the_key_is_the_id(test_app: SphinxTestApp, reader: str):
    app = test_app
    app.build()
    assert build_warnings(app) == [
        diagnostic(
            reader,
            "the need keyed 'REQ_012' has the id 'REQ_001'; the key is its id",
            "versions.1.0.needs.REQ_012.id",
        ),
        diagnostic(
            reader,
            "the need keyed 'NUM_ID' has the id 5; the key is its id",
            "versions.1.0.needs.NUM_ID.id",
        ),
    ]
    needs = from_file(app)
    assert {k: v["title"] for k, v in needs.items()} == {
        "REQ_001": "title REQ_001",
        "REQ_012": "under key REQ_012",
        "NUM_ID": "numeric id",
        "NO_ID": "no id",
    }


# ------------------------------------------------------------------------------------
# R3: a file no record can be read from is ONE warning; the build continues


def _json_error(text: str) -> str:
    try:
        json.loads(text)
    except json.JSONDecodeError as err:
        return str(err)
    raise AssertionError("valid JSON")


ONE = {"REQ_A": rec("REQ_A")}

REFUSED_SOURCES = {
    # case: (needs.json text, the reason both readers give)
    "invalid_json": ("{ not json", f"not valid JSON: {_json_error('{ not json')}"),
    "not_an_object": ("[1, 2]", "the top level is not a JSON object"),
    "versions_missing": (
        json.dumps({"current_version": "1.0"}),
        "'versions' is missing or not an object",
    ),
    "current_version_missing": (
        json.dumps({"versions": {"1.0": {"needs": ONE}}}),
        "no version is requested and 'current_version' is missing, empty or not a string",
    ),
    "current_version_empty": (
        json.dumps({"current_version": "", "versions": {"1.0": {"needs": ONE}}}),
        "no version is requested and 'current_version' is missing, empty or not a string",
    ),
    "current_version_number": (
        json.dumps({"current_version": 1.0, "versions": {"1.0": {"needs": ONE}}}),
        "no version is requested and 'current_version' is missing, empty or not a string",
    ),
    "version_not_found": (
        json.dumps({"current_version": "3.0", "versions": {"1.0": {"needs": ONE}}}),
        "Version 3.0 not found in the file: ['1.0']",
    ),
    "versions_empty": (
        json.dumps({"current_version": "1.0", "versions": {}}),
        "Version 1.0 not found in the file: []",
    ),
    "needs_missing": (
        json.dumps(
            {"current_version": "1.0", "versions": {"1.0": {"needs_amount": 0}}}
        ),
        "Version 1.0 has no 'needs' object",
    ),
}


@pytest.mark.parametrize(
    ("test_app", "reader", "message"),
    [
        pytest.param(project(reader, text), reader, message, id=f"{case}-{reader}")
        for case, (text, message) in REFUSED_SOURCES.items()
        for reader in READERS
    ],
    indirect=["test_app"],
)
def test_a_source_that_cannot_be_read_is_one_warning(
    test_app: SphinxTestApp, reader: str, message: str
):
    app = test_app
    app.build()
    assert app.statuscode == 0
    assert build_warnings(app) == [refused_source(reader, message)]
    assert from_file(app) == {}
    assert "Local body." in Path(app.outdir, "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("test_app", "reader"),
    both(json.dumps({"current_version": "", "versions": {"": {"needs": ONE}}})),
    indirect=["test_app"],
)
def test_an_unnamed_current_version_is_read(test_app: SphinxTestApp, reader: str):
    """A needs.json of a project whose ``version`` is unset: its one version is ``""``."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert sorted(from_file(app)) == ["REQ_A"]


@pytest.mark.parametrize(("test_app", "reader"), both(None), indirect=["test_app"])
def test_a_missing_file_is_one_warning(test_app: SphinxTestApp, reader: str):
    app = test_app
    app.build()
    assert app.statuscode == 0
    if reader == "import":
        expected = at_import(
            f"Could not load needs import file {DATA_PATH}", "needimport"
        )
    else:
        expected = refused_source(reader, f"the file {DATA_PATH} does not exist")
    assert build_warnings(app) == [expected]
    assert from_file(app) == {}


@pytest.mark.parametrize(
    ("test_app", "reader"),
    both(envelope({"STR_001": "just a string", **ONE})),
    indirect=["test_app"],
)
def test_a_record_that_is_not_an_object_is_skipped(
    test_app: SphinxTestApp, reader: str
):
    app = test_app
    app.build()
    assert build_warnings(app) == [
        diagnostic(
            reader,
            "the need 'STR_001' is not an object; it is skipped",
            "versions.1.0.needs.STR_001",
        )
    ]
    assert sorted(from_file(app)) == ["REQ_A"]


@pytest.mark.parametrize(
    ("test_app", "reader"),
    both(envelope(ONE, needs_defaults_removed=True)),
    indirect=["test_app"],
)
def test_defaults_removed_without_a_schema_warns(test_app: SphinxTestApp, reader: str):
    app = test_app
    app.build()
    assert build_warnings(app) == [
        diagnostic(
            reader,
            "Version 1.0 was written without its default values "
            "('needs_defaults_removed') and has no 'needs_schema' to restore them "
            "from; the reading project's defaults are used",
            "versions.1.0.needs_defaults_removed",
        )
    ]
    assert sorted(from_file(app)) == ["REQ_A"]


# ------------------------------------------------------------------------------------
# R4: one record path -- the same records are refused by both readers


RECORD_CHECKS = {
    # case: (the record, the refusal)
    "title_missing": ({"id": "BAD", "type": "req", "content": "x"}, "title is missing"),
    "title_not_string": (rec("BAD", title=5), "title must be a string, not int"),
    "content_not_string": (
        rec("BAD", content=123),
        "content must be a string, not int",
    ),
    "type_not_string": (rec("BAD", type=5), "type must be a string, not int"),
    "parts_not_mapping": (
        rec("BAD", parts="some text"),
        "parts must be a mapping, not str",
    ),
    "part_not_mapping": (
        rec("BAD", parts={"p1": "x"}),
        "part 'p1' must be a mapping, not str",
    ),
}


@pytest.mark.parametrize(
    ("test_app", "reader", "message"),
    [
        pytest.param(
            project(reader, envelope({"BAD": record, "GOOD": rec("GOOD")})),
            reader,
            message,
            id=f"{case}-{reader}",
        )
        for case, (record, message) in RECORD_CHECKS.items()
        for reader in READERS
    ],
    indirect=["test_app"],
)
def test_a_record_is_checked_alike_by_both_readers(
    test_app: SphinxTestApp, reader: str, message: str
):
    app = test_app
    app.build()
    assert build_warnings(app) == [refused_need(reader, "BAD", message)]
    assert sorted(from_file(app)) == ["GOOD"]


# ------------------------------------------------------------------------------------
# R5: the ten fields each reader keeps differently -- kept, as the rule


def test_the_ten_field_table():
    """``needimport`` renders a need on the importing page, so it keeps how the need is
    rendered and takes where it is from the page; an external need lives elsewhere, so
    it keeps where it was and drops how it was rendered."""
    from sphinx_needs.api.need import _import_key_sets

    class Schema:
        def iter_link_field_names(self):
            return iter(["links"])

        def iter_extra_field_names(self):
            return iter(["priority"])

    import_only = {
        k
        for k, v in NeedsCoreFields.items()
        if v.get("exclude_external") and not v.get("exclude_import")
    }
    external_only = {
        k
        for k, v in NeedsCoreFields.items()
        if v.get("exclude_import") and not v.get("exclude_external")
    }
    assert import_only == {
        "collapse",
        "hide",
        "layout",
        "style",
        "jinja_content",
        "template",
        "pre_template",
        "post_template",
    }
    assert external_only == {"sections", "signature"}
    known_import, omitted_import = _import_key_sets(Schema(), reader="import")
    known_external, omitted_external = _import_key_sets(Schema(), reader="external")
    assert known_import == known_external
    assert omitted_external - omitted_import == import_only
    assert omitted_import - omitted_external == external_only


KEPT = envelope(
    {
        "REQ_A": rec(
            "REQ_A",
            layout="clean",
            style="green",
            collapse=True,
            sections=["Sec A", "Top"],
            signature="sig()",
            docname="spec/page",
            lineno=12,
            parts={"p1": {"id": "p1", "content": "part one"}},
            content="no part role here",
        )
    }
)


@pytest.mark.parametrize(("test_app", "reader"), both(KEPT), indirect=["test_app"])
def test_the_readers_differ_by_design(test_app: SphinxTestApp, reader: str):
    """The ten-field table, where the need is recorded, and its ``parts`` (read from the
    environment: ``collapse`` is not written to needs.json)."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    need = SphinxNeedsData(app.env).get_needs_view()["REQ_A"]
    fields = (
        "layout",
        "style",
        "collapse",
        "sections",
        "signature",
        "docname",
        "lineno",
        "doctype",
        "parts",
    )
    got = {k: list(need[k]) if k == "sections" else need[k] for k in fields}
    if reader == "import":
        assert got == {
            "layout": "clean",
            "style": "green",
            "collapse": True,
            "sections": ["Index"],
            "signature": None,
            "docname": "index",
            "lineno": IMPORT_LINE,
            "doctype": ".rst",
            "parts": {},
        }
    else:
        assert got == {
            "layout": None,
            "style": None,
            "collapse": False,
            "sections": ["Sec A", "Top"],
            "signature": "sig()",
            "docname": None,
            "lineno": None,
            "doctype": "",
            "parts": {"p1": {"content": "part one", "id": "p1"}},
        }


# ------------------------------------------------------------------------------------
# R6: id_prefix is added as written, by both readers


PREFIXED = envelope({"REQ_A": rec("REQ_A", links=["REQ_B"]), "REQ_B": rec("REQ_B")})


@pytest.mark.parametrize(
    ("test_app", "reader"),
    [
        pytest.param(
            project("import", PREFIXED, options=(":id_prefix: px_",)),
            "import",
            id="import",
        ),
        pytest.param(
            project("external", PREFIXED, source={"id_prefix": "px_"}),
            "external",
            id="external",
        ),
    ],
    indirect=["test_app"],
)
def test_the_prefix_is_added_as_written(test_app: SphinxTestApp, reader: str):
    app = test_app
    app.build()
    assert build_warnings(app) == []
    needs = from_file(app)
    assert sorted(needs) == ["px_REQ_A", "px_REQ_B"]
    assert needs["px_REQ_A"]["links"] == ["px_REQ_B"]


# ------------------------------------------------------------------------------------
# R7: needs_id_regex applies to the project's own needs, not to either reader's


@pytest.mark.parametrize(
    ("test_app", "reader"),
    both(envelope({"bad-id": rec("bad-id")})),
    indirect=["test_app"],
)
def test_the_id_regex_is_not_applied_to_read_needs(
    test_app: SphinxTestApp, reader: str
):
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert sorted(from_file(app)) == ["bad-id"]


@pytest.mark.parametrize(
    "test_app",
    [project("external", None, sources=[], page_extra=".. ingest-probe:: bad-id\n")],
    indirect=True,
)
def test_the_id_regex_still_applies_to_a_record_of_the_project(test_app: SphinxTestApp):
    """A record created through ``ingest_need_record`` the way sphinx-codelinks creates
    one -- a source that is neither imported nor external -- is still validated."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:{IMPORT_LINE}: WARNING: Need 'bad-id' could not be "
        "ingested: Given ID 'bad-id' does not match configured regex "
        "'^[A-Z][A-Z0-9_]*$' [needs.test_ingest]"
    ]
    assert "bad-id" not in needs_by_id(app)


# ------------------------------------------------------------------------------------
# R8: a need of the project replaces an external need of its id; any other duplicate is
# refused, naming where the first one is from


def _is_external(app: SphinxTestApp, need_id: str) -> bool:
    return SphinxNeedsData(app.env).get_needs_view()[need_id]["is_external"]


REPLACES = (
    f"<srcdir>/index.rst:{PAGE_NEED_LINE}: WARNING: Need 'LOCAL_001' replaces the "
    "external need of the same id from http://ext.example/docs/spec.html#LOCAL_001 "
    "[needs.create_need]"
)
LOCAL_DATA = envelope(
    {"LOCAL_001": rec("LOCAL_001", title="external title", docname="spec")}
)


@pytest.mark.parametrize("test_app", [project("external", LOCAL_DATA)], indirect=True)
def test_a_need_of_the_project_replaces_an_external_need(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert build_warnings(app) == [REPLACES]
    assert needs_by_id(app)["LOCAL_001"]["title"] == "local need"
    assert not _is_external(app, "LOCAL_001")
    assert "Local body." in Path(app.outdir, "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("test_app", [project("external", LOCAL_DATA)], indirect=True)
def test_on_an_incremental_build_the_external_need_is_refused(test_app: SphinxTestApp):
    """The need of the project is in the environment before the source is read again."""
    app = test_app
    app.build()
    first = build_warnings(app)
    assert first == [REPLACES]
    app.build()
    assert build_warnings(app)[len(first) :] == [
        refused_need(
            "external",
            "LOCAL_001",
            f"A need with ID 'LOCAL_001' already exists (defined at index:{PAGE_NEED_LINE}).",
        )
    ]
    assert not _is_external(app, "LOCAL_001")


PAD_PAGES = {f"pad_{n}.rst": f":orphan:\n\nPad {n}\n=====\n" for n in range(5)}


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            project("external", LOCAL_DATA, files=PAD_PAGES, parallel=2),
            marks=pytest.mark.skipif(
                not parallel_available, reason="Parallel execution not supported"
            ),
        )
    ],
    indirect=True,
)
def test_a_need_of_the_project_replaces_an_external_need_in_parallel(
    test_app: SphinxTestApp,
):
    """A worker that read the page hands its need back over the external one."""
    app = test_app
    app.build()
    assert build_warnings(app) == [REPLACES]
    assert not _is_external(app, "LOCAL_001")
    assert needs_by_id(app)["LOCAL_001"]["title"] == "local need"


@pytest.mark.parametrize(
    "test_app",
    [project("import", LOCAL_DATA)],
    indirect=True,
)
def test_an_imported_duplicate_of_a_page_need_is_refused_naming_it(
    test_app: SphinxTestApp,
):
    """Import and a page need: read order decides, as it always has."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        refused_need(
            "import",
            "LOCAL_001",
            f"A need with ID 'LOCAL_001' already exists (defined at index:{PAGE_NEED_LINE}).",
        )
    ]
    assert needs_by_id(app)["LOCAL_001"]["title"] == "local need"


SHARED = envelope({"SHARED_1": rec("SHARED_1", title="external title", docname="spec")})


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **project("import", SHARED),
            "confoverrides": {
                "needs_external_needs": [
                    {"base_url": BASE_URL, "json_path": "data.json"}
                ]
            },
        }
    ],
    indirect=True,
)
def test_an_imported_need_replaces_an_external_need(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert build_warnings(app) == [
        at_import(
            "Need 'SHARED_1' replaces the external need of the same id from "
            "http://ext.example/docs/spec.html#SHARED_1",
            "create_need",
        )
    ]
    assert not _is_external(app, "SHARED_1")
    assert SphinxNeedsData(app.env).get_needs_view()["SHARED_1"]["is_import"]


# ------------------------------------------------------------------------------------
# R9: across this build's sources the first definition of an id wins, warned (#2003);
# an external need left from the previous build is replaced


DUP_A = envelope({"DUP_1": rec("DUP_1", title="from a", docname="index")})
DUP_B = envelope({"DUP_1": rec("DUP_1", title="from b", docname="index")})


@pytest.mark.parametrize(
    ("test_app", "second"),
    [
        pytest.param(
            project(
                "external",
                None,
                files={"a.json": DUP_A, "b.json": DUP_B},
                sources=[
                    {"base_url": BASE_URL, "json_path": "a.json"},
                    {"base_url": BASE_URL, "json_path": "b.json"},
                ],
            ),
            "b.json",
            id="two_inventories_one_base_url",
        ),
        pytest.param(
            project(
                "external",
                None,
                files={"a.json": DUP_A},
                sources=[
                    {"base_url": BASE_URL, "json_path": "a.json"},
                    {"base_url": BASE_URL, "json_path": "a.json"},
                ],
            ),
            "a.json",
            id="one_source_listed_twice",
        ),
    ],
    indirect=["test_app"],
)
def test_external_duplicates_keep_the_first(test_app: SphinxTestApp, second: str):
    app = test_app
    app.build()
    assert build_warnings(app) == [
        refused_need(
            "external",
            "DUP_1",
            "A need with ID 'DUP_1' already exists "
            "(external, http://ext.example/docs/index.html#DUP_1).",
            file=second,
        )
    ]
    assert needs_by_id(app)["DUP_1"]["title"] == "from a"


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            "import",
            None,
            files={"a.json": DUP_A, "b.json": DUP_B},
            imports=(("a.json", ()), ("b.json", ())),
        )
    ],
    indirect=True,
)
def test_imported_duplicates_keep_the_first(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert build_warnings(app) == [
        at_import(
            "Need 'DUP_1' could not be imported: A need with ID 'DUP_1' already "
            f"exists (imported at index:{IMPORT_LINE}).",
            "import_need",
            line=IMPORT_LINE + 2,
        )
    ]
    assert needs_by_id(app)["DUP_1"]["title"] == "from a"


@pytest.mark.parametrize(
    "test_app", [project("external", envelope(ONE))], indirect=True
)
def test_an_external_need_of_the_previous_build_is_replaced(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert build_warnings(app) == []
    app.build()
    assert build_warnings(app) == []
    assert _is_external(app, "REQ_A")


# ------------------------------------------------------------------------------------
# R10: the prefix is applied against the whole file; :ids: and :filter: warn once


@pytest.mark.parametrize(
    "test_app",
    [
        pytest.param(
            project("import", PREFIXED, options=(":id_prefix: px_", ":ids: REQ_A")),
            id="ids",
        ),
        pytest.param(
            project(
                "import",
                PREFIXED,
                options=(":id_prefix: px_", ":filter: id == 'REQ_A'"),
            ),
            id="filter",
        ),
    ],
    indirect=True,
)
def test_a_link_to_a_need_left_out_is_prefixed(test_app: SphinxTestApp):
    """The target is still that file's need, so it gets that file's prefix."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        at_import(
            "Need 'px_REQ_A' has unknown outgoing link 'px_REQ_B' in field 'links'",
            "link_outgoing",
        )
    ]
    assert from_file(app)["px_REQ_A"]["links"] == ["px_REQ_B"]


def _prefixed(reader: str, data: str) -> dict[str, Any]:
    if reader == "import":
        return project("import", data, options=(":id_prefix: px_",))
    return project("external", data, source={"id_prefix": "px_"})


@pytest.mark.parametrize(
    ("test_app", "expected"),
    [
        pytest.param(
            _prefixed(
                reader,
                envelope(
                    {
                        "REQ_A": rec("REQ_A", links="REQ_B, OUTSIDE"),
                        "REQ_B": rec("REQ_B"),
                    }
                ),
            ),
            ["OUTSIDE", "px_REQ_B"],
            id=f"string-{reader}",
        )
        for reader in READERS
    ]
    + [
        pytest.param(
            _prefixed(
                reader,
                envelope({"REQ_A": rec("REQ_A", links=None), "REQ_B": rec("REQ_B")}),
            ),
            [],
            id=f"none-{reader}",
        )
        for reader in READERS
    ],
    indirect=["test_app"],
)
def test_string_and_null_links_with_a_prefix(test_app: SphinxTestApp, expected):
    app = test_app
    app.build()
    assert [w for w in build_warnings(app) if "OUTSIDE" not in w] == []
    assert from_file(app)["px_REQ_A"]["links"] == expected


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            "import",
            envelope({"REQ_A": rec("REQ_A"), "REQ_B": rec("REQ_B")}),
            options=(":ids: REQ_A, NOPE, ALSO_NOPE",),
        )
    ],
    indirect=True,
)
def test_ids_the_file_does_not_have_warn(test_app: SphinxTestApp):
    """#1472."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        at_import(
            f"Needs import file {DATA_PATH} has no needs with the ids "
            "['NOPE', 'ALSO_NOPE']",
            "needimport",
        )
    ]
    assert sorted(from_file(app)) == ["REQ_A"]


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            "import",
            envelope({k: rec(k) for k in ("REQ_A", "REQ_B", "REQ_C")}),
            options=(":filter: no_such_name == 1",),
        )
    ],
    indirect=True,
)
def test_a_filter_that_fails_warns_once(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert build_warnings(app) == [
        at_import(
            "needimport: Filter 'no_such_name == 1' not valid. Error: name "
            "'no_such_name' is not defined.",
            "needimport",
        )
    ]
    assert from_file(app) == {}


# ------------------------------------------------------------------------------------
# legacy content, read the same by both readers


@pytest.mark.parametrize(
    ("test_app", "reader"),
    both(envelope({"REQ_A": rec("REQ_A", description="legacy text")})),
    indirect=["test_app"],
)
def test_a_legacy_description_is_the_content(test_app: SphinxTestApp, reader: str):
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert from_file(app)["REQ_A"]["content"] == "legacy text"
