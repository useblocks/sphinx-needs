"""``needs_import_inert_content``: the content of a need ``needimport`` creates is parsed
with docutils' file insertion and raw markup switched off.

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

FLAG = "needs_import_inert_content"

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
    :param warning: What the warning reporting it with the option on contains.
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


INCLUDE_RST = '"include" directive disabled'
INCLUDE_MYST = 'Directive "include" disabled'
FILE_INSERTION = "File insertion disabled"
FILE_ACCESS = 'File and URL access deactivated; ignoring "csv-table" directive.'
RAW = '"raw" directive disabled'
RAW_ROLE = "raw (and derived) roles disabled"
NESTED = "file insertion is disabled here"
RAW_REMOVED = "Raw markup removed from the content of imported need"

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
        NESTED,
        "CANARY_NESTED_LOCAL",
    ),
    "needimport_url": Construct(
        ".rst",
        ".. needimport:: {OUTURL}/nested_url.json",
        {"nested_url.json": nested("NESTED_URL")},
        "NESTED_URL",
        "need",
        NESTED,
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
        RAW_REMOVED,
        "<div>CANARY_M_HTML_BLOCK</div>",
    ),
    "m_html_inline": Construct(
        ".md",
        'Text <span data-c="CANARY_M_HTML_INLINE"></span> text.',
        {},
        "CANARY_M_HTML_INLINE",
        "raw",
        RAW_REMOVED,
        '<span data-c="CANARY_M_HTML_INLINE">',
    ),
    "m_needimport": Construct(
        ".md",
        "```{needimport} {OUT}/m_nested_local.json\n```",
        {"m_nested_local.json": nested("M_NESTED_LOCAL")},
        "M_NESTED_LOCAL",
        "need",
        NESTED,
        "CANARY_M_NESTED_LOCAL",
    ),
    "m_needimport_url": Construct(
        ".md",
        "```{needimport} {OUTURL}/m_nested_url.json\n```",
        {"m_nested_url.json": nested("M_NESTED_URL")},
        "M_NESTED_URL",
        "need",
        NESTED,
        "CANARY_M_NESTED_URL",
    ),
}


def conf(*, by_doctype: bool, inert: bool | None) -> str:
    """A project that parses reStructuredText and MyST; ``inert`` ``None`` leaves the
    option unset in ``conf.py``."""
    lines = [
        'extensions = ["myst_parser", "sphinx_needs"]',
        'source_suffix = {".rst": "restructuredtext", ".md": "markdown"}',
        'needs_id_regex = r"^[A-Za-z0-9_]+$"',
        "show_warning_types = True",
        f"needs_import_parse_by_doctype = {by_doctype}",
    ]
    if inert is not None:
        lines.append(f"{FLAG} = {inert}")
    return "\n".join(lines) + "\n"


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


def write_import(
    app: SphinxTestApp, doctype: str, names: list[str] | None = None
) -> dict[str, Construct]:
    """Write the canary files outside the project, and ``imported.json``: a need per
    construct of ``doctype`` (or of ``names``), each holding that construct alone."""
    srcdir = Path(app.srcdir)
    outside = srcdir.parent / "outside"
    outside.mkdir(exist_ok=True)
    chosen = {
        name: c
        for name, c in CONSTRUCTS.items()
        if (c.markup == doctype if names is None else name in names)
    }
    needs = {}
    for name, construct in chosen.items():
        for file, text in construct.files.items():
            (outside / file).write_text(text, encoding="utf-8")
        need_id = f"IMP_{name.upper()}"
        needs[need_id] = {
            "id": need_id,
            "type": "spec",
            "title": need_id,
            "doctype": doctype,
            "content": construct.body.replace("{OUT}", "../outside").replace(
                "{OUTURL}", outside.resolve().as_uri()
            ),
        }
    (srcdir / "imported.json").write_text(
        json.dumps({"current_version": "1.0", "versions": {"1.0": {"needs": needs}}}),
        encoding="utf-8",
    )
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


def matrix_params() -> list[Any]:
    params = []
    for route, (page, by_doctype, _) in ROUTES.items():
        for inert in (False, True):
            files = [
                (Path("proj/conf.py"), conf(by_doctype=by_doctype, inert=inert)),
                (Path("proj", page), importing_page(page)),
            ]
            params.append(
                pytest.param(
                    {"buildername": "html", "files": files, "files_srcdir": "proj"},
                    route,
                    inert,
                    id=f"{route}-{'on' if inert else 'off'}",
                )
            )
    return params


@pytest.mark.parametrize(
    ("test_app", "route", "inert"), matrix_params(), indirect=["test_app"]
)
def test_each_construct_in_each_route(
    test_app: SphinxTestApp, route: str, inert: bool, monkeypatch: pytest.MonkeyPatch
):
    """On, no canary is read or written, and each construct is reported once by its own
    warning; off (in ``conf.py``), every canary is, and nothing is reported. A nested
    needimport reads nothing when it is refused: neither its file nor its URL is opened."""
    constructs = write_import(test_app, ROUTES[route][2])
    opened: list[str] = []
    load, get = ub_needs_exchange.load, requests.Session.get

    def spy_load(path: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(path))
        return load(path, *args, **kwargs)

    def spy_get(self: requests.Session, url: Any, *args: Any, **kwargs: Any) -> Any:
        opened.append(str(url))
        return get(self, url, *args, **kwargs)

    monkeypatch.setattr(ub_needs_exchange, "load", spy_load)
    monkeypatch.setattr(requests.Session, "get", spy_get)
    test_app.build()
    reached = {name: present(test_app, c) for name, c in constructs.items()}
    nested = sorted(
        Path(name).name for name in opened if not name.endswith("imported.json")
    )
    if not inert:
        assert reached == dict.fromkeys(constructs, True)
        assert nested == sorted(
            file for c in constructs.values() if c.kind == "need" for file in c.files
        )
        assert_no_warnings(test_app)
        return
    assert reached == dict.fromkeys(constructs, False)
    assert nested == []
    warnings = build_warnings(test_app)
    expected = Counter(c.warning for c in constructs.values())
    found = Counter(
        next((w for w in expected if w in warning), warning) for warning in warnings
    )
    assert found == expected, warnings


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
    for route in ("rst-host", "rst-declared", "myst-declared", "myst-host"):
        page, by_doctype, _ = ROUTES[route]
        text, other = scope_rst() if page.endswith(".rst") else scope_myst()
        files = [
            (Path("proj/conf.py"), conf(by_doctype=by_doctype, inert=True)),
            (Path("proj", page), text),
            (Path("proj", "other" + Path(page).suffix), other),
        ]
        params.append(
            pytest.param(
                {"buildername": "html", "files": files, "files_srcdir": "proj"},
                route,
                id=route,
            )
        )
    return params


@pytest.mark.parametrize(("test_app", "route"), scope_params(), indirect=["test_app"])
def test_only_the_imported_content_is_inert(test_app: SphinxTestApp, route: str):
    """The needs written before and after the import, the page's own raw block, and the
    next document still include and still pass raw markup through: the switches are put
    back after the imported content's parse."""
    doctype = ROUTES[route][2]
    outside = Path(test_app.srcdir).parent / "outside"
    outside.mkdir()
    for file, text in SCOPE_FILES.items():
        (outside / file).write_text(text, encoding="utf-8")
    if doctype == ".rst":
        content = (
            ".. include:: ../outside/imported.txt\n\n"
            ".. raw:: html\n\n   <b>CANARY_RAW_IMPORTED</b>"
        )
    else:
        content = (
            "```{include} ../outside/imported.txt\n```\n\n"
            "```{raw} html\n<b>CANARY_RAW_IMPORTED</b>\n```"
        )
    record = {
        "id": "IMP",
        "type": "spec",
        "title": "IMP",
        "doctype": doctype,
        "content": content,
    }
    Path(test_app.srcdir, "imported.json").write_text(
        json.dumps(
            {"current_version": "1.0", "versions": {"1.0": {"needs": {"IMP": record}}}}
        ),
        encoding="utf-8",
    )
    test_app.build()

    def reached(token: str, kind: str, docname: str = "index") -> bool:
        html = f"<b>{token}</b>" if kind == "raw" else token
        return present(test_app, Construct("", "", {}, token, kind, "", html), docname)

    assert reached("CANARY_BEFORE", "text")
    assert reached("CANARY_RAW_BEFORE", "raw")
    assert reached("CANARY_AFTER", "text")
    assert reached("CANARY_RAW_AFTER", "raw")
    assert reached("CANARY_RAW_PAGE", "raw")
    assert reached("CANARY_OTHER", "text", "other")
    assert reached("CANARY_RAW_OTHER", "raw", "other")
    assert not reached("CANARY_IMPORTED", "text")
    assert not reached("CANARY_RAW_IMPORTED", "raw")
    assert len(build_warnings(test_app)) == 2, build_warnings(test_app)


ONE_IMPORT = ["include", "raw"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("proj/conf.py"),
                    conf(by_doctype=False, inert=None)
                    + 'needs_from_toml = "ubproject.toml"\n',
                ),
                (Path("proj/ubproject.toml"), "[needs]\nimport_inert_content = true\n"),
                (Path("proj/index.rst"), importing_page("index.rst")),
            ],
            "files_srcdir": "proj",
        }
    ],
    indirect=True,
)
def test_the_option_in_ubproject_toml(test_app: SphinxTestApp):
    """``[needs] import_inert_content`` in ``ubproject.toml`` is the option."""
    constructs = write_import(test_app, ".rst", ONE_IMPORT)
    test_app.build()
    assert not any(present(test_app, c) for c in constructs.values())
    assert len(build_warnings(test_app)) == 2, build_warnings(test_app)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("proj/conf.py"), conf(by_doctype=False, inert=None)),
                (Path("proj/index.rst"), importing_page("index.rst")),
            ],
            "files_srcdir": "proj",
        }
    ],
    indirect=True,
)
def test_changing_the_option_rereads_the_importing_page(
    test_app: SphinxTestApp, make_app: Any
):
    """An incremental build that changes only the option re-reads the importing page:
    nothing else in the project changed, and the canaries the first build read are gone."""
    constructs = write_import(test_app, ".rst", ONE_IMPORT)
    test_app.build()
    assert all(present(test_app, c) for c in constructs.values())
    assert_no_warnings(test_app)
    test_app.cleanup()

    again = make_app(
        buildername="html",
        srcdir=test_app.srcdir,
        builddir=Path(test_app.outdir).parent,
        confoverrides={FLAG: True},
    )
    try:
        again.build()
        assert not any(present(again, c) for c in constructs.values())
        assert len(build_warnings(again)) == 2, build_warnings(again)
    finally:
        again.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (Path("proj/conf.py"), conf(by_doctype=False, inert=True)),
                (Path("proj/docutils.conf"), "[general]\nraw_enabled: false\n"),
                (
                    Path("proj/index.rst"),
                    importing_page(
                        "index.rst",
                        after=".. raw:: html\n\n   <b>CANARY_RAW_PAGE</b>\n",
                    ),
                ),
            ],
            "files_srcdir": "proj",
        }
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
    page_raw = Construct(
        "", "", {}, "CANARY_RAW_PAGE", "raw", "", "<b>CANARY_RAW_PAGE</b>"
    )
    assert not present(test_app, page_raw)
    warnings = build_warnings(test_app)
    assert len(warnings) == 2, warnings
    assert sum(RAW in w for w in warnings) == 1, warnings
