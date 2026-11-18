"""``needs_import_restrict_content``: the content of a need ``needimport`` creates is
parsed with docutils' file insertion and raw markup switched off.

Every project is built inline into ``<root>/proj``; each construct reads a canary file of
its own in ``<root>/outside``, OUTSIDE the project, or carries its canary in the record.
The needs.json is written once the application exists, so that its ``file://`` URLs can name
the canary files absolutely (nothing is fetched from the network). With the option on, no
canary reaches the doctree or the written HTML, and each construct is reported by the
warning of the directive it is; with it off, every canary does, and nothing is reported.

The five routes are the ways a record's content is parsed: the host state's own
``nested_parse`` (a reStructuredText page, a MyST page) and the declared-markup path of
``needs_import_parse_by_doctype`` (reStructuredText in either page, MyST in a
reStructuredText page).
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import requests
from docutils import nodes
from sphinx.testing.util import SphinxTestApp
from sphinx.util.docutils import patch_docutils

import ub_needs_exchange
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import assert_no_warnings, build_warnings

FLAG = "needs_import_restrict_content"

ROUTES = {
    # route: (importing page, needs_import_parse_by_doctype, record doctype)
    "rst-host": ("index.rst", False, ".rst"),
    "rst-declared": ("index.rst", True, ".rst"),
    "rst-in-myst-page": ("index.md", True, ".rst"),
    "myst-declared": ("index.rst", True, ".md"),
    "myst-host": ("index.md", False, ".md"),
}


class Construct:
    """One construct in an imported record's content.

    :param markup: The record doctype it is written in.
    :param body: The content; ``{OUT}`` is the outside directory relative to the
        importing page, ``{OUTURL}`` its ``file://`` URL.
    :param files: The canary files it reads, in the outside directory.
    :param token: The canary.
    :param kind: ``text``: the token is text of a file the construct reads; ``raw``: the
        token is in raw markup (the doctree's ``raw`` nodes, the unescaped HTML); ``need``:
        the token is the title of a need a nested needimport reads.
    :param warning: What the warning reporting it with the option on contains (``{OUT}``
        and ``{OUTURL}`` as in ``body``).
    """

    def __init__(
        self,
        markup: str,
        body: str,
        files: dict[str, str],
        token: str,
        kind: str,
        warning: str,
        html: str | None = None,
    ) -> None:
        self.markup, self.body, self.files = markup, body, files
        self.token, self.kind, self.warning = token, kind, warning
        self.html = html or token


def nested(need_id: str) -> str:
    """A needs.json holding one need, titled with its canary."""
    record = {"id": need_id, "type": "spec", "title": f"CANARY_{need_id}"}
    return json.dumps(
        {"current_version": "1.0", "versions": {"1.0": {"needs": {need_id: record}}}}
    )


def fill(text: str, outside: Path) -> str:
    """``{OUT}`` as the importing page names the outside directory, ``{OUTURL}`` its URL."""
    return text.replace("{OUT}", "../outside").replace(
        "{OUTURL}", outside.resolve().as_uri()
    )


INCLUDE_RST = '"include" directive disabled'
INCLUDE_MYST = 'Directive "include" disabled'
FILE_INSERTION = "File insertion disabled"
FILE_ACCESS = 'File and URL access deactivated; ignoring "csv-table" directive.'
RAW = '"raw" directive disabled'
RAW_ROLE = "raw (and derived) roles disabled"
RESTRICT_ON = "needs_import_restrict_content is on"


def refused(path: str) -> str:
    """The warning of a ``needimport`` met in imported content under the option."""
    return f"Could not load needs import file {path}: {RESTRICT_ON}"


def removed(need_id: str, count: int) -> str:
    """The warning of an imported need whose raw markup was removed."""
    return (
        "Raw markup (an HTML block or inline HTML) removed from "
        f"imported need {need_id!r} ({count} node(s)): {RESTRICT_ON}"
    )


CONSTRUCTS: dict[str, Construct] = {
    "include": Construct(
        ".rst",
        ".. include:: {OUT}/include.txt",
        {"include.txt": "CANARY_INCLUDE\n"},
        "CANARY_INCLUDE",
        "text",
        INCLUDE_RST,
    ),
    "literalinclude": Construct(
        ".rst",
        ".. literalinclude:: {OUT}/literalinclude.txt",
        {"literalinclude.txt": "CANARY_LITERALINCLUDE\n"},
        "CANARY_LITERALINCLUDE",
        "text",
        FILE_INSERTION,
    ),
    "csv_file": Construct(
        ".rst",
        ".. csv-table:: T\n   :file: {OUT}/csv_file.csv",
        {"csv_file.csv": "a,CANARY_CSV_FILE\n"},
        "CANARY_CSV_FILE",
        "text",
        FILE_ACCESS,
    ),
    "csv_url": Construct(
        ".rst",
        ".. csv-table:: T\n   :url: {OUTURL}/csv_url.csv",
        {"csv_url.csv": "a,CANARY_CSV_URL\n"},
        "CANARY_CSV_URL",
        "text",
        FILE_ACCESS,
    ),
    "raw": Construct(
        ".rst",
        ".. raw:: html\n\n   <b>CANARY_RAW_CONTENT</b>",
        {},
        "CANARY_RAW_CONTENT",
        "raw",
        RAW,
        "<b>CANARY_RAW_CONTENT</b>",
    ),
    "raw_file": Construct(
        ".rst",
        ".. raw:: html\n   :file: {OUT}/raw_file.html",
        {"raw_file.html": "<b>CANARY_RAW_FILE</b>\n"},
        "CANARY_RAW_FILE",
        "raw",
        RAW,
        "<b>CANARY_RAW_FILE</b>",
    ),
    "raw_url": Construct(
        ".rst",
        ".. raw:: html\n   :url: {OUTURL}/raw_url.html",
        {"raw_url.html": "<b>CANARY_RAW_URL</b>\n"},
        "CANARY_RAW_URL",
        "raw",
        RAW,
        "<b>CANARY_RAW_URL</b>",
    ),
    "raw_role": Construct(
        ".rst",
        ".. role:: rawhtml(raw)\n   :format: html\n\n:rawhtml:`<b>CANARY_RAW_ROLE</b>`",
        {},
        "CANARY_RAW_ROLE",
        "raw",
        RAW_ROLE,
        "<b>CANARY_RAW_ROLE</b>",
    ),
    "needimport": Construct(
        ".rst",
        ".. needimport:: {OUT}/nested_local.json",
        {"nested_local.json": nested("NESTED_LOCAL")},
        "NESTED_LOCAL",
        "need",
        refused("{OUT}/nested_local.json"),
        "CANARY_NESTED_LOCAL",
    ),
    "needimport_url": Construct(
        ".rst",
        ".. needimport:: {OUTURL}/nested_url.json",
        {"nested_url.json": nested("NESTED_URL")},
        "NESTED_URL",
        "need",
        refused("{OUTURL}/nested_url.json"),
        "CANARY_NESTED_URL",
    ),
    "m_include": Construct(
        ".md",
        "```{include} {OUT}/m_include.txt\n```",
        {"m_include.txt": "CANARY_M_INCLUDE\n"},
        "CANARY_M_INCLUDE",
        "text",
        INCLUDE_MYST,
    ),
    "m_literalinclude": Construct(
        ".md",
        "```{literalinclude} {OUT}/m_literalinclude.txt\n```",
        {"m_literalinclude.txt": "CANARY_M_LITERALINCLUDE\n"},
        "CANARY_M_LITERALINCLUDE",
        "text",
        FILE_INSERTION,
    ),
    "m_csv_file": Construct(
        ".md",
        "```{csv-table} T\n:file: {OUT}/m_csv_file.csv\n```",
        {"m_csv_file.csv": "a,CANARY_M_CSV_FILE\n"},
        "CANARY_M_CSV_FILE",
        "text",
        FILE_ACCESS,
    ),
    "m_eval_rst_include": Construct(
        ".md",
        "```{eval-rst}\n.. include:: {OUT}/m_eval_rst_include.txt\n```",
        {"m_eval_rst_include.txt": "CANARY_M_EVAL_RST_INCLUDE\n"},
        "CANARY_M_EVAL_RST_INCLUDE",
        "text",
        INCLUDE_RST,
    ),
    "m_eval_rst_raw": Construct(
        ".md",
        "```{eval-rst}\n.. raw:: html\n\n   <b>CANARY_M_EVAL_RST_RAW</b>\n```",
        {},
        "CANARY_M_EVAL_RST_RAW",
        "raw",
        RAW,
        "<b>CANARY_M_EVAL_RST_RAW</b>",
    ),
    "m_raw": Construct(
        ".md",
        "```{raw} html\n<b>CANARY_M_RAW_DIRECTIVE</b>\n```",
        {},
        "CANARY_M_RAW_DIRECTIVE",
        "raw",
        RAW,
        "<b>CANARY_M_RAW_DIRECTIVE</b>",
    ),
    "m_raw_file": Construct(
        ".md",
        "```{raw} html\n:file: {OUT}/m_raw_file.html\n```",
        {"m_raw_file.html": "<b>CANARY_M_RAW_FILE</b>\n"},
        "CANARY_M_RAW_FILE",
        "raw",
        RAW,
        "<b>CANARY_M_RAW_FILE</b>",
    ),
    "m_html_block": Construct(
        ".md",
        "<div>CANARY_M_HTML_BLOCK</div>",
        {},
        "CANARY_M_HTML_BLOCK",
        "raw",
        removed("IMP_M_HTML_BLOCK", 1),
        "<div>CANARY_M_HTML_BLOCK</div>",
    ),
    "m_html_inline": Construct(
        ".md",
        'Text <span data-c="CANARY_M_HTML_INLINE"></span> text.',
        {},
        "CANARY_M_HTML_INLINE",
        "raw",
        # the opening and the closing tag are a raw node each
        removed("IMP_M_HTML_INLINE", 2),
        '<span data-c="CANARY_M_HTML_INLINE">',
    ),
    "m_needimport": Construct(
        ".md",
        "```{needimport} {OUT}/m_nested_local.json\n```",
        {"m_nested_local.json": nested("M_NESTED_LOCAL")},
        "M_NESTED_LOCAL",
        "need",
        refused("{OUT}/m_nested_local.json"),
        "CANARY_M_NESTED_LOCAL",
    ),
    "m_needimport_url": Construct(
        ".md",
        "```{needimport} {OUTURL}/m_nested_url.json\n```",
        {"m_nested_url.json": nested("M_NESTED_URL")},
        "M_NESTED_URL",
        "need",
        refused("{OUTURL}/m_nested_url.json"),
        "CANARY_M_NESTED_URL",
    ),
}


def conf(*, by_doctype: bool, restricted: bool | None, extra: str = "") -> str:
    """A project that parses reStructuredText and MyST; ``restricted`` ``None`` leaves
    the option unset in ``conf.py``."""
    lines = [
        'extensions = ["myst_parser", "sphinx_needs"]',
        'source_suffix = {".rst": "restructuredtext", ".md": "markdown"}',
        'needs_id_regex = r"^[A-Za-z0-9_]+$"',
        "show_warning_types = True",
        f"needs_import_parse_by_doctype = {by_doctype}",
    ]
    if restricted is not None:
        lines.append(f"{FLAG} = {restricted}")
    return "\n".join(lines) + "\n" + extra


def importing_page(page: str, before: str = "", after: str = "") -> str:
    """A page holding one needimport of ``imported.json``, between ``before`` and
    ``after``."""
    if page.endswith(".rst"):
        head = "Host\n====\n\n"
        directive = ".. needimport:: imported.json\n"
    else:
        head = "# Host\n\n"
        directive = "```{needimport} imported.json\n```\n"
    return f"{head}{before}{directive}\n{after}"


def write_records(app: SphinxTestApp, records: list[dict[str, Any]]) -> Path:
    """Write ``imported.json`` holding ``records``; return the outside directory."""
    srcdir = Path(app.srcdir)
    (srcdir / "imported.json").write_text(
        json.dumps(
            {
                "current_version": "1.0",
                "versions": {"1.0": {"needs": {r["id"]: r for r in records}}},
            }
        ),
        encoding="utf-8",
    )
    outside = srcdir.parent / "outside"
    outside.mkdir(exist_ok=True)
    return outside


def write_import(
    app: SphinxTestApp, doctype: str, names: list[str] | None = None
) -> dict[str, Construct]:
    """Write the canary files outside the project, and ``imported.json``: a need per
    construct of ``doctype`` (or of ``names``), each holding that construct alone."""
    outside = Path(app.srcdir).parent / "outside"
    chosen = {
        name: c
        for name, c in CONSTRUCTS.items()
        if (c.markup == doctype if names is None else name in names)
    }
    records = []
    for name, construct in chosen.items():
        need_id = f"IMP_{name.upper()}"
        records.append(
            {
                "id": need_id,
                "type": "spec",
                "title": need_id,
                "doctype": doctype,
                "content": fill(construct.body, outside),
            }
        )
    write_records(app, records)
    for construct in chosen.values():
        for file, text in construct.files.items():
            (outside / file).write_text(text, encoding="utf-8")
    return chosen


def present(app: SphinxTestApp, construct: Construct, docname: str = "index") -> bool:
    """Whether the canary reached the doctree, asserting the written HTML agrees."""
    doctree = app.env.get_doctree(docname)
    if construct.kind == "text":
        in_doctree = construct.token in doctree.pformat()
    elif construct.kind == "raw":
        in_doctree = any(
            construct.token in raw.astext() for raw in doctree.findall(nodes.raw)
        )
    else:
        in_doctree = construct.token in SphinxNeedsData(app.env).get_needs_view()
    in_html = construct.html in Path(app.outdir, f"{docname}.html").read_text("utf8")
    assert in_doctree == in_html, (construct.token, in_doctree, in_html)
    return in_doctree


def reached(
    app: SphinxTestApp,
    token: str,
    kind: str,
    docname: str = "index",
    html: str | None = None,
) -> bool:
    """:func:`present` for a canary of a test's own: a ``raw`` one is written
    ``<b>…</b>`` unless ``html`` says how."""
    if html is None:
        html = f"<b>{token}</b>" if kind == "raw" else token
    return present(app, Construct("", "", {}, token, kind, "", html), docname)


def assert_warnings(app: SphinxTestApp, expected: list[str]) -> None:
    """The build's warnings are exactly ``expected``: each warning contains one of them,
    and each of them is contained as many times as it is listed."""
    warnings = build_warnings(app)
    wanted = Counter(expected)
    found = Counter(
        next((w for w in wanted if w in warning), warning) for warning in warnings
    )
    assert found == wanted, warnings


def project(
    page: str,
    text: str,
    *,
    by_doctype: bool = False,
    restricted: bool | None,
    extra_conf: str = "",
    files: list[tuple[Path, str]] | None = None,
) -> dict[str, Any]:
    """``test_app`` parameters: a project in ``<root>/proj`` with ``page`` as its index."""
    return {
        "buildername": "html",
        "files": [
            (
                Path("proj/conf.py"),
                conf(by_doctype=by_doctype, restricted=restricted, extra=extra_conf),
            ),
            (Path("proj", page), text),
            *(files or []),
        ],
        "files_srcdir": "proj",
    }


def matrix_params() -> list[Any]:
    params = []
    for route, (page, by_doctype, _) in ROUTES.items():
        for restricted in (False, True):
            params.append(
                pytest.param(
                    project(
                        page,
                        importing_page(page),
                        by_doctype=by_doctype,
                        restricted=restricted,
                    ),
                    route,
                    restricted,
                    id=f"{route}-{'on' if restricted else 'off'}",
                )
            )
    return params


@pytest.mark.parametrize(
    ("test_app", "route", "restricted"), matrix_params(), indirect=["test_app"]
)
def test_each_construct_in_each_route(
    test_app: SphinxTestApp,
    route: str,
    restricted: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    """On, no canary is read or written, and each construct is reported once by its own
    warning; off (in ``conf.py``), every canary is, and nothing is reported. A nested
    needimport leaves no trace when it is refused: its file and URL are not opened, its
    path is not looked for, and it is not noted as a dependency of the page."""
    constructs = write_import(test_app, ROUTES[route][2])
    outside = Path(test_app.srcdir).parent / "outside"
    opened: list[str] = []
    probed: list[str] = []
    load, get, exists = ub_needs_exchange.load, requests.Session.get, os.path.exists

    def spy_load(path: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(path))
        return load(path, *args, **kwargs)

    def spy_get(self: requests.Session, url: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(url))
        return get(self, url, *args, **kwargs)

    def spy_exists(path: Any) -> bool:
        probed.append(str(path))
        return exists(path)

    monkeypatch.setattr(ub_needs_exchange, "load", spy_load)
    monkeypatch.setattr(requests.Session, "get", spy_get)
    monkeypatch.setattr(os.path, "exists", spy_exists)
    test_app.build()
    monkeypatch.undo()
    reached_ = {name: present(test_app, c) for name, c in constructs.items()}
    nested_files = {
        file for c in constructs.values() if c.kind == "need" for file in c.files
    }
    local_files = {
        file
        for c in constructs.values()
        if c.kind == "need"
        and c.body.startswith((".. needimport:: {OUT}/", "```{needimport} {OUT}/"))
        for file in c.files
    }
    nested = sorted(
        Path(name).name for name in opened if not name.endswith("imported.json")
    )
    noted = {
        Path(p).name for p in test_app.env.dependencies.get("index", ())
    } & nested_files
    looked_for = {Path(p).name for p in probed} & nested_files
    if not restricted:
        assert reached_ == dict.fromkeys(constructs, True)
        assert nested == sorted(nested_files)
        assert noted == local_files
        assert local_files <= looked_for
        assert_no_warnings(test_app)
        return
    assert reached_ == dict.fromkeys(constructs, False)
    assert nested == []
    assert noted == set()
    assert looked_for == set()
    assert_warnings(test_app, [fill(c.warning, outside) for c in constructs.values()])


SCOPE_FILES = {
    "before.txt": "CANARY_BEFORE\n",
    "after.txt": "CANARY_AFTER\n",
    "other.txt": "CANARY_OTHER\n",
    "imported.txt": "CANARY_IMPORTED\n",
}


def scope_rst() -> tuple[str, str]:
    def need(name: str) -> str:
        return (
            f".. req:: {name}\n   :id: R_{name.upper()}\n\n"
            f"   .. include:: ../outside/{name}.txt\n\n"
            f"   .. raw:: html\n\n      <b>CANARY_RAW_{name.upper()}</b>\n\n"
        )

    page = importing_page(
        "index.rst",
        before=".. toctree::\n\n   other\n\n" + need("before"),
        after=need("after") + ".. raw:: html\n\n   <b>CANARY_RAW_PAGE</b>\n",
    )
    other = (
        "Other\n=====\n\n.. include:: ../outside/other.txt\n\n"
        ".. raw:: html\n\n   <b>CANARY_RAW_OTHER</b>\n"
    )
    return page, other


def scope_myst() -> tuple[str, str]:
    def need(name: str) -> str:
        return (
            f"````{{req}} {name}\n:id: R_{name.upper()}\n\n"
            f"```{{include}} ../outside/{name}.txt\n```\n\n"
            f"```{{raw}} html\n<b>CANARY_RAW_{name.upper()}</b>\n```\n````\n\n"
        )

    page = importing_page(
        "index.md",
        before="```{toctree}\nother\n```\n\n" + need("before"),
        after=need("after") + "```{raw} html\n<b>CANARY_RAW_PAGE</b>\n```\n",
    )
    other = (
        "# Other\n\n```{include} ../outside/other.txt\n```\n\n"
        "```{raw} html\n<b>CANARY_RAW_OTHER</b>\n```\n"
    )
    return page, other


def scope_params() -> list[Any]:
    params = []
    for route, (page, by_doctype, _) in ROUTES.items():
        text, other = scope_rst() if page.endswith(".rst") else scope_myst()
        params.append(
            pytest.param(
                project(
                    page,
                    text,
                    by_doctype=by_doctype,
                    restricted=True,
                    files=[(Path("proj", "other" + Path(page).suffix), other)],
                ),
                route,
                id=route,
            )
        )
    return params


def include_and_raw(doctype: str, name: str) -> str:
    """Content that includes ``../outside/<name>.txt`` and writes
    ``<b>CANARY_RAW_<NAME></b>`` as raw markup, in ``doctype``'s markup."""
    if doctype == ".rst":
        return (
            f".. include:: ../outside/{name}.txt\n\n"
            f".. raw:: html\n\n   <b>CANARY_RAW_{name.upper()}</b>"
        )
    return (
        f"```{{include}} ../outside/{name}.txt\n```\n\n"
        f"```{{raw}} html\n<b>CANARY_RAW_{name.upper()}</b>\n```"
    )


def include_warning(doctype: str) -> str:
    return INCLUDE_RST if doctype == ".rst" else INCLUDE_MYST


@pytest.mark.parametrize(("test_app", "route"), scope_params(), indirect=["test_app"])
def test_only_the_imported_content_is_restricted(test_app: SphinxTestApp, route: str):
    """The needs written before and after the import, the page's own raw block, and the
    next document still include and still pass raw markup through: the switches are put
    back after the imported content's parse."""
    doctype = ROUTES[route][2]
    outside = write_records(
        test_app,
        [
            {
                "id": "IMP",
                "type": "spec",
                "title": "IMP",
                "doctype": doctype,
                "content": include_and_raw(doctype, "imported"),
            }
        ],
    )
    for file, text in SCOPE_FILES.items():
        (outside / file).write_text(text, encoding="utf-8")
    test_app.build()

    assert reached(test_app, "CANARY_BEFORE", "text")
    assert reached(test_app, "CANARY_RAW_BEFORE", "raw")
    assert reached(test_app, "CANARY_AFTER", "text")
    assert reached(test_app, "CANARY_RAW_AFTER", "raw")
    assert reached(test_app, "CANARY_RAW_PAGE", "raw")
    assert reached(test_app, "CANARY_OTHER", "text", "other")
    assert reached(test_app, "CANARY_RAW_OTHER", "raw", "other")
    assert not reached(test_app, "CANARY_IMPORTED", "text")
    assert not reached(test_app, "CANARY_RAW_IMPORTED", "raw")
    assert_warnings(test_app, [include_warning(doctype), RAW])


ONE_IMPORT = ["include", "raw"]


@pytest.mark.parametrize(
    ("test_app", "value"),
    [
        pytest.param(
            project(
                "index.rst",
                importing_page("index.rst"),
                restricted=None,
                extra_conf='needs_from_toml = "ubproject.toml"\n',
                files=[
                    (
                        Path("proj/ubproject.toml"),
                        f"[needs]\nimport_restrict_content = {value}\n",
                    )
                ],
            ),
            value,
            id=value,
        )
        for value in ("true", "false")
    ],
    indirect=["test_app"],
)
def test_the_option_in_ubproject_toml(test_app: SphinxTestApp, value: str):
    """``[needs] import_restrict_content`` in ``ubproject.toml`` is the option."""
    constructs = write_import(test_app, ".rst", ONE_IMPORT)
    test_app.build()
    if value == "false":
        assert all(present(test_app, c) for c in constructs.values())
        assert_no_warnings(test_app)
        return
    assert not any(present(test_app, c) for c in constructs.values())
    assert_warnings(test_app, [INCLUDE_RST, RAW])


@pytest.mark.parametrize(
    ("test_app", "start"),
    [
        pytest.param(
            project("index.rst", importing_page("index.rst"), restricted=start),
            start,
            id=f"{'on' if start else 'off'}-to-{'off' if start else 'on'}",
        )
        for start in (False, True)
    ],
    indirect=["test_app"],
)
def test_changing_the_option_rereads_the_importing_page(
    test_app: SphinxTestApp, make_app: Any, start: bool
):
    """An incremental build that changes only the option re-reads the importing page,
    in either direction: nothing else in the project changed."""
    constructs = write_import(test_app, ".rst", ONE_IMPORT)

    def check(app: SphinxTestApp, restricted: bool) -> None:
        assert [present(app, c) for c in constructs.values()] == [not restricted] * 2
        assert_warnings(app, [INCLUDE_RST, RAW] if restricted else [])

    test_app.build()
    check(test_app, start)
    test_app.cleanup()

    again = make_app(
        buildername="html",
        srcdir=test_app.srcdir,
        builddir=Path(test_app.outdir).parent,
        confoverrides={FLAG: not start},
    )
    try:
        again.build()
        check(again, not start)
    finally:
        again.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            "index.rst",
            importing_page(
                "index.rst", after=".. raw:: html\n\n   <b>CANARY_RAW_PAGE</b>\n"
            ),
            restricted=True,
            files=[(Path("proj/docutils.conf"), "[general]\nraw_enabled: false\n")],
        )
    ],
    indirect=True,
)
def test_the_projects_own_settings_are_put_back(test_app: SphinxTestApp):
    """The switches are put back as the project had them, not switched on: a project
    that turns raw markup off itself (``docutils.conf``) has it off after the import."""
    constructs = write_import(test_app, ".rst", ["include"])
    # what ``sphinx-build`` does around a build, and ``SphinxTestApp`` does not: point
    # docutils at the project's ``docutils.conf``
    with patch_docutils(test_app.confdir):
        test_app.build()
    assert not present(test_app, constructs["include"])
    assert not reached(test_app, "CANARY_RAW_PAGE", "raw")
    assert_warnings(test_app, [INCLUDE_RST, RAW])


@pytest.mark.parametrize(
    ("test_app", "restricted"),
    [
        pytest.param(
            project(
                "index.rst",
                importing_page(
                    "index.rst",
                    after=".. needimport:: second.json\n\n"
                    ".. include:: ../outside/page.txt\n",
                ),
                restricted=restricted,
                files=[
                    (
                        Path("proj/docutils.conf"),
                        "[general]\nfile_insertion_enabled: false\n",
                    )
                ],
            ),
            restricted,
            id="on" if restricted else "off",
        )
        for restricted in (False, True)
    ],
    indirect=["test_app"],
)
def test_a_project_without_file_insertion_still_imports(
    test_app: SphinxTestApp, restricted: bool
):
    """A project that switches file insertion off itself (``docutils.conf``) still
    imports with a page-level ``needimport``, with the option off and on: the directive
    refuses only inside imported content, and there only under the option. A second
    page-level import, after the first one's content was parsed, still reads."""
    outside = write_records(
        test_app,
        [
            {
                "id": "IMP_TOP",
                "type": "spec",
                "title": "IMP_TOP",
                "content": ".. needimport:: ../outside/nested_local.json",
            }
        ],
    )
    (outside / "nested_local.json").write_text(nested("NESTED_LOCAL"), "utf-8")
    Path(test_app.srcdir, "second.json").write_text(nested("SECOND"), "utf-8")
    (outside / "page.txt").write_text("CANARY_PAGE\n", encoding="utf-8")
    with patch_docutils(test_app.confdir):
        test_app.build()
    needs = SphinxNeedsData(test_app.env).get_needs_view()
    assert "IMP_TOP" in needs
    assert "SECOND" in needs
    # the project's own switch is in force on the page itself
    assert not reached(test_app, "CANARY_PAGE", "text")
    if not restricted:
        assert "NESTED_LOCAL" in needs
        assert_warnings(test_app, [INCLUDE_RST])
        return
    assert "NESTED_LOCAL" not in needs
    assert_warnings(test_app, [INCLUDE_RST, refused("../outside/nested_local.json")])


def nested_need(doctype: str) -> str:
    """Imported content holding a need written inside it, which includes a file and
    writes raw markup; in MyST, the outer content writes an HTML block too."""
    if doctype == ".rst":
        return (
            ".. spec:: Inner\n   :id: INNER\n\n"
            "   .. include:: ../outside/inner.txt\n\n"
            "   .. raw:: html\n\n      <b>CANARY_RAW_INNER</b>\n"
        )
    return (
        "<div>CANARY_RAW_OUTER</div>\n\n"
        "````{spec} Inner\n:id: INNER\n\n"
        "```{include} ../outside/inner.txt\n```\n\n"
        "<div>CANARY_RAW_INNER</div>\n````\n"
    )


@pytest.mark.parametrize(
    ("test_app", "route", "restricted"),
    [
        pytest.param(
            project(
                page,
                importing_page(page),
                by_doctype=by_doctype,
                restricted=restricted,
            ),
            route,
            restricted,
            id=f"{route}-{'on' if restricted else 'off'}",
        )
        for route, (page, by_doctype, _) in ROUTES.items()
        for restricted in (False, True)
    ],
    indirect=["test_app"],
)
def test_a_need_written_inside_imported_content(
    test_app: SphinxTestApp, route: str, restricted: bool
):
    """A need written inside an imported need's content is parsed restricted too: its
    ``include`` reads nothing, and its raw markup (a ``raw`` block in reStructuredText,
    an HTML block in MyST) is stopped or removed, and counted into the warning of the
    imported need that holds it."""
    doctype = ROUTES[route][2]
    outside = write_records(
        test_app,
        [
            {
                "id": "IMP",
                "type": "spec",
                "title": "IMP",
                "doctype": doctype,
                "content": nested_need(doctype),
            }
        ],
    )
    (outside / "inner.txt").write_text("CANARY_INNER\n", encoding="utf-8")
    test_app.build()
    assert "INNER" in SphinxNeedsData(test_app.env).get_needs_view()
    if doctype == ".rst":
        canaries = [reached(test_app, "CANARY_RAW_INNER", "raw")]
    else:
        canaries = [
            reached(
                test_app, f"CANARY_RAW_{name}", "raw", html=f"<div>CANARY_RAW_{name}"
            )
            for name in ("INNER", "OUTER")
        ]
    canaries.append(reached(test_app, "CANARY_INNER", "text"))
    assert canaries == [not restricted] * len(canaries)
    if not restricted:
        assert_no_warnings(test_app)
    elif doctype == ".rst":
        assert_warnings(test_app, [INCLUDE_RST, RAW])
    else:
        # the inner need's HTML block is counted into the imported need's warning
        assert_warnings(test_app, [INCLUDE_MYST, removed("IMP", 2)])


def templates_project(page: str, restricted: bool) -> dict[str, Any]:
    """A project with the docs' own example ``pre_template``, a ``template`` rendering
    the content, and a need WRITTEN on the page with the pre template, whose title writes
    raw markup."""
    docs_pre = (
        Path(__file__).parent.parent
        / "docs"
        / "needs_templates"
        / "spec_pre_template.need"
    ).read_text("utf8")
    if page.endswith(".rst"):
        written = (
            ".. role:: rawhtml(raw)\n   :format: html\n\n"
            ".. spec:: x** :rawhtml:`<b>CANARY_RAW_WRITTEN</b>` **y\n"
            "   :id: WRITTEN\n   :pre_template: spec_pre_template\n\n"
        )
    else:
        written = (
            '```{spec} x** <span data-c="CANARY_RAW_WRITTEN"></span> **y\n'
            ":id: WRITTEN\n:pre_template: spec_pre_template\n```\n\n"
        )
    return project(
        page,
        importing_page(page, before=written),
        restricted=restricted,
        files=[
            (Path("proj/needs_templates/spec_pre_template.need"), docs_pre),
            (Path("proj/needs_templates/content.need"), "{{ content }}\n"),
        ],
    )


@pytest.mark.parametrize(
    ("test_app", "index", "restricted"),
    [
        pytest.param(
            templates_project(index, restricted),
            index,
            restricted,
            id=f"{index}-{'on' if restricted else 'off'}",
        )
        for index in ("index.rst", "index.md")
        for restricted in (False, True)
    ],
    indirect=["test_app"],
)
def test_the_text_templates_render_is_restricted(
    test_app: SphinxTestApp, index: str, restricted: bool
):
    """The text a ``template``, ``pre_template`` or ``post_template`` renders for an
    imported need is parsed restricted too: the record names the template, and a
    template renders the record's fields (the docs' example pre template renders its
    title). A need written on the page with the same pre template is untouched."""
    doctype = Path(index).suffix

    def include_and_html(name: str) -> str:
        # in MyST, the raw markup is an HTML block, which the restricted parse removes
        if doctype == ".rst":
            return include_and_raw(doctype, name)
        return (
            f"```{{include}} ../outside/{name}.txt\n```\n\n"
            f"<div>CANARY_RAW_{name.upper()}</div>"
        )

    def title(name: str) -> str:
        return f"x**\n\n{include_and_html(name)}\n\n**y"

    outside = write_records(
        test_app,
        [
            {
                "id": "IMP_TEMPLATE",
                "type": "spec",
                "title": "IMP_TEMPLATE",
                "template": "content",
                "content": include_and_html("template"),
            },
            {
                "id": "IMP_PRE",
                "type": "spec",
                "title": title("pre"),
                "pre_template": "spec_pre_template",
                "content": "plain",
            },
            {
                "id": "IMP_POST",
                "type": "spec",
                "title": title("post"),
                "post_template": "spec_pre_template",
                "content": "plain",
            },
        ],
    )
    for name in ("template", "pre", "post"):
        (outside / f"{name}.txt").write_text(
            f"CANARY_{name.upper()}\n", encoding="utf-8"
        )
    test_app.build()
    if doctype == ".rst":
        assert reached(test_app, "CANARY_RAW_WRITTEN", "raw")
    else:
        html = '<span data-c="CANARY_RAW_WRITTEN">'
        assert reached(test_app, "CANARY_RAW_WRITTEN", "raw", html=html)
    names = ("TEMPLATE", "PRE", "POST")
    found = [reached(test_app, f"CANARY_{name}", "text") for name in names]
    for name in names:
        html = None if doctype == ".rst" else f"<div>CANARY_RAW_{name}</div>"
        found.append(reached(test_app, f"CANARY_RAW_{name}", "raw", html=html))
    assert found == [not restricted] * len(found)
    if not restricted:
        assert_no_warnings(test_app)
    elif doctype == ".rst":
        assert_warnings(test_app, [INCLUDE_RST, RAW] * 3)
    else:
        assert_warnings(
            test_app,
            [INCLUDE_MYST] * 3 + [removed(f"IMP_{name}", 1) for name in names],
        )


MYST_OWN_RAW = (
    "line one\\\nline two\n\n"
    "~~struck~~ text\n\n"
    "- [ ] open task\n- [x] done task\n\n"
    'Text <br onclick="CANARY_BR"> and <s class="CANARY_S">x</s>.'
)


@pytest.mark.parametrize(
    ("test_app", "route", "restricted"),
    [
        pytest.param(
            project(
                ROUTES[route][0],
                importing_page(ROUTES[route][0]),
                by_doctype=ROUTES[route][1],
                restricted=restricted,
                extra_conf=(
                    'myst_enable_extensions = ["strikethrough", "tasklist"]\n'
                    'suppress_warnings = ["myst.strikethrough"]\n'
                ),
            ),
            route,
            restricted,
            id=f"{route}-{'on' if restricted else 'off'}",
        )
        for route in ("myst-declared", "myst-host")
        for restricted in (False, True)
    ],
    indirect=["test_app"],
)
def test_what_myst_parser_writes_as_raw_itself_is_kept(
    test_app: SphinxTestApp, route: str, restricted: bool
):
    """A hard line break, strikethrough and a task-list checkbox are raw nodes
    myst-parser makes for ordinary Markdown: kept, exactly those texts (``<s>`` and
    ``</s>`` as a pair), and not counted; HTML that only starts like them is removed."""
    write_records(
        test_app,
        [
            {
                "id": "IMP",
                "type": "spec",
                "title": "IMP",
                "doctype": ".md",
                "content": MYST_OWN_RAW,
            }
        ],
    )
    test_app.build()
    raws = Counter(
        (raw.get("format"), raw.astext())
        for raw in test_app.env.get_doctree("index").findall(nodes.raw)
    )
    html = Path(test_app.outdir, "index.html").read_text("utf8")
    kept = {
        ("html", "<br />\n"): 1,
        ("latex", "\\\\\n"): 1,
        ("html", "<s>"): 1,
        ("html", "</s>"): 1,
        (
            "html",
            '<input class="task-list-item-checkbox" disabled="disabled" type="checkbox">',
        ): 1,
        (
            "html",
            '<input class="task-list-item-checkbox" checked="checked" '
            'disabled="disabled" type="checkbox">',
        ): 1,
    }
    foreign = {
        ("html", '<br onclick="CANARY_BR">'): 1,
        ("html", '<s class="CANARY_S">'): 1,
        # the closing tag of the ``<s class=…>`` is exactly myst-parser's own, but it
        # closes no ``<s>`` of myst-parser's
        ("html", "</s>"): 1,
    }
    assert "<s>struck</s>" in html
    assert html.count('class="task-list-item-checkbox"') == 2
    assert "line one<br />" in html
    if not restricted:
        assert raws == Counter(kept) + Counter(foreign)
        assert '<br onclick="CANARY_BR">' in html
        assert '<s class="CANARY_S">' in html
        assert_no_warnings(test_app)
        return
    assert raws == Counter(kept)
    assert "CANARY_BR" not in html
    assert "CANARY_S" not in html
    assert html.count("</s>") == 1
    assert_warnings(test_app, [removed("IMP", 3)])


STRIKETHROUGH = {
    # case: (record content, the html raw nodes kept, how many removed)
    "pair": ("~~x~~ text", {"<s>": 1, "</s>": 1}, 0),
    "close-alone": ("a </s> b", {}, 1),
    "open-twice": ("x <s>a<s>b</s>", {"<s>": 1, "</s>": 1}, 1),
    # a pair is matched among the children of one parent, never across paragraphs
    "across-paragraphs": ("Open <s>left\n\nThen </s> closed", {}, 2),
}


@pytest.mark.parametrize(
    ("test_app", "case"),
    [
        pytest.param(
            project(
                ROUTES[route][0],
                importing_page(ROUTES[route][0]),
                by_doctype=ROUTES[route][1],
                restricted=True,
                extra_conf=(
                    'myst_enable_extensions = ["strikethrough"]\n'
                    'suppress_warnings = ["myst.strikethrough"]\n'
                ),
            ),
            case,
            id=f"{route}-{case}",
        )
        for route in ("myst-declared", "myst-host")
        for case in STRIKETHROUGH
    ],
    indirect=["test_app"],
)
def test_strikethrough_is_kept_only_as_a_pair(test_app: SphinxTestApp, case: str):
    """``<s>`` and ``</s>`` are kept only as a pair among one parent's children, as
    myst-parser writes ``~~x~~``: an ``<s>`` a record leaves open, or a ``</s>`` that
    closes nothing, is removed and counted."""
    content, kept, count = STRIKETHROUGH[case]
    write_records(
        test_app,
        [
            {
                "id": "IMP",
                "type": "spec",
                "title": "IMP",
                "doctype": ".md",
                "content": content,
            }
        ],
    )
    test_app.build()
    raws = Counter(
        raw.astext()
        for raw in test_app.env.get_doctree("index").findall(nodes.raw)
        if raw.get("format") == "html"
    )
    assert raws == Counter(kept)
    html = Path(test_app.outdir, "index.html").read_text("utf8")
    assert html.count("<s>") == kept.get("<s>", 0)
    assert html.count("</s>") == kept.get("</s>", 0)
    if count:
        assert_warnings(test_app, [removed("IMP", count)])
    else:
        assert "<s>x</s>" in html
        assert_no_warnings(test_app)


def pre_template_project(restricted: bool) -> dict[str, Any]:
    """A MyST page importing ``imported.json`` with a host paragraph after it, and the
    docs' own example pre and post template, which render the need's title."""
    docs_pre = (
        Path(__file__).parent.parent
        / "docs"
        / "needs_templates"
        / "spec_pre_template.need"
    ).read_text("utf8")
    return project(
        "index.md",
        importing_page("index.md", after="AFTER_HOST\n\n## Next\n\nNEXT_HOST\n"),
        restricted=restricted,
        files=[(Path("proj/needs_templates/spec_pre_template.need"), docs_pre)],
    )


@pytest.mark.parametrize(
    ("test_app", "restricted"),
    [
        pytest.param(
            pre_template_project(restricted),
            restricted,
            id="on" if restricted else "off",
        )
        for restricted in (False, True)
    ],
    indirect=["test_app"],
)
def test_an_open_strikethrough_in_a_template_is_removed(
    test_app: SphinxTestApp, restricted: bool
):
    """An ``<s>`` a record title leaves open, rendered by a pre template on a MyST page,
    sits outside the need: kept, it would strike through the rest of the page."""
    write_records(
        test_app,
        [
            {
                "id": "IMP_S",
                "type": "spec",
                "title": "T <s>OPEN_S",
                "pre_template": "spec_pre_template",
                "content": "plain",
            }
        ],
    )
    test_app.build()
    html = Path(test_app.outdir, "index.html").read_text("utf8")
    assert "AFTER_HOST" in html
    assert "NEXT_HOST" in html
    if not restricted:
        assert html.count("<s>") == 1
        assert "<s>OPEN_S" in html
        assert_no_warnings(test_app)
        return
    assert "<s>" not in html
    assert not any(
        raw.astext() == "<s>"
        for raw in test_app.env.get_doctree("index").findall(nodes.raw)
    )
    assert_warnings(test_app, [removed("IMP_S", 1)])


@pytest.mark.parametrize(
    "test_app", [pytest.param(pre_template_project(True), id="on")], indirect=True
)
def test_one_warning_carries_every_parse(test_app: SphinxTestApp):
    """An imported need whose pre template, content and post template all lose raw
    markup gets ONE warning, carrying the total."""
    write_records(
        test_app,
        [
            {
                "id": "IMP_ALL",
                "type": "spec",
                "title": "T <b>CANARY_T</b>",
                "pre_template": "spec_pre_template",
                "post_template": "spec_pre_template",
                "content": "<div>CANARY_C</div>",
            }
        ],
    )
    test_app.build()
    html = Path(test_app.outdir, "index.html").read_text("utf8")
    assert "<b>CANARY_T</b>" not in html
    assert "<div>CANARY_C</div>" not in html
    # two inline tags in each template, one HTML block in the content
    assert_warnings(test_app, [removed("IMP_ALL", 5)])
