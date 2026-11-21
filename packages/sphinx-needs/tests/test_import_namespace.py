"""The ``namespace`` of an import: ``:namespace:`` on ``needimport``, and the key
``namespace`` of a ``needs_external_needs`` source.

``namespace = SUP`` is ``id_prefix = SUP::`` with the value checked: the option is
resolved once into the prefix text (``ub_needs_exchange.namespace_prefix``), and the
import then does exactly what that ``id_prefix`` does. The oracle of most tests is a
sibling project that imports the same file with ``:id_prefix: SUP::`` (or the source key
``id_prefix = "SUP::"``): its needs, field for field, its ``needs.json`` and its page
equal the namespace project's, and so do its warnings, but for the one notice the
namespace gives per import:

- with ``needs_namespaced_ids`` on, ``needs.import_namespace``, when some of the ids
  cannot be joined to the namespace (they are imported as plain ids, with the prefix);
- with it off, ``needs.namespaced_ids_off``: the ids are read as plain ids.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.external_needs import NeedsExternalException
from sphinx_needs_testkit import build_warnings


def _rec(key: str, **fields: Any) -> dict[str, Any]:
    return {
        "id": key,
        "type": "req",
        "title": f"Title of {key}",
        "docname": "index",
        **fields,
    }


#: one file of every kind of id and reference: a plain id, an already namespaced id,
#: two ids that cannot be joined to a namespace (``a::::b`` does not split cleanly,
#: ``:X`` starts with ``:``); links to each, a link to a part, a link with a condition,
#: a link to a need of the importing project, a link default of the file's schema
#: (``satisfies``, which ``REQ_1`` overrides), and content naming file ids
SRC_NEEDS = {
    "REQ_1": _rec("REQ_1", status="open", satisfies=[], content="Plain one."),
    "REQ_2": _rec(
        "REQ_2",
        links=[
            "REQ_1",
            "nc::REQ_1.p1",
            'REQ_1[status=="open"]',
            "LOCAL_1",
            "a::::b",
            ":X",
        ],
        content="Names REQ_1, nc::REQ_1 and :need:`REQ_1`.",
    ),
    "nc::REQ_1": _rec(
        "nc::REQ_1",
        links=["REQ_1"],
        content="Namespaced :np:`(p1) part one`.",
    ),
    "a::::b": _rec("a::::b", links=["nc::REQ_1"]),
    ":X": _rec(":X", links=["a::::b"]),
}


def _needs_json(needs: dict[str, dict[str, Any]]) -> str:
    return json.dumps(
        {
            "current_version": "1.0",
            "versions": {
                "1.0": {
                    "needs": needs,
                    "needs_schema": {
                        "properties": {"satisfies": {"default": ["REQ_1"]}}
                    },
                }
            },
        }
    )


SRC = _needs_json(SRC_NEEDS)
#: the external reader takes a need's parts from its record, not from its content
SRC_EXTERNAL = _needs_json(
    {
        **SRC_NEEDS,
        "nc::REQ_1": {
            **SRC_NEEDS["nc::REQ_1"],
            "parts": {"p1": {"id": "p1", "content": "part one"}},
        },
    }
)
#: a file whose every id can be joined to a namespace
CLEAN = _needs_json({k: v for k, v in SRC_NEEDS.items() if k in ("REQ_1", "nc::REQ_1")})
#: a file of eight ids that cannot be joined, to show how many the notice names
MANY = _needs_json({f":B{i}": _rec(f":B{i}") for i in range(8)})

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_reproducible_json = True
needs_builder_filter = ""
needs_extra_links = [
    {"option": "satisfies", "incoming": "is satisfied by", "outgoing": "satisfies"}
]
"""

PAGE_HEAD = """\
Index
=====

.. req:: A local need
   :id: LOCAL_1
   :links: SUP::nc::REQ_1.p1

"""
#: the references of the page: to a part, to a need, and the outgoing row of LOCAL_1
PAGE_REFS = """
Refs: :need:`SUP::nc::REQ_1.p1`, :need:`SUP::REQ_2` and :need_outgoing:`LOCAL_1`.
"""
#: the line of the first ``needimport`` of an import page
IMPORT_LINE = 8
BASE_URL = "http://ext.example"


def _conf(*, namespaced: bool | None = True, extra: str = "") -> str:
    conf = CONF
    if namespaced is not None:
        conf += f"needs_namespaced_ids = {namespaced}\n"
    return conf + extra


def _import_page(*imports: tuple[str, tuple[str, ...]]) -> str:
    """A page holding a ``needimport`` of each ``(file, options)``."""
    page = PAGE_HEAD
    for name, options in imports:
        page += "\n".join([f".. needimport:: {name}", *(f"   {o}" for o in options)])
        page += "\n\n"
    return page + PAGE_REFS


def _import_project(
    *options: str,
    namespaced: bool | None = True,
    data: str = SRC,
    extra: str = "",
    imports: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
) -> dict[str, str]:
    return {
        "conf.py": _conf(namespaced=namespaced, extra=extra),
        "src.json": data,
        "index.rst": _import_page(*(imports or (("src.json", options),))),
    }


def _external_project(
    *sources: dict[str, Any],
    namespaced: bool | None = True,
    data: str = SRC_EXTERNAL,
    extra: str = "",
) -> dict[str, str]:
    full = [{"json_path": "src.json", "base_url": BASE_URL, **s} for s in sources]
    return {
        "conf.py": _conf(namespaced=namespaced, extra=extra)
        + f"needs_external_needs = {json.dumps(full, indent=4)}\n",
        "src.json": data,
        "index.rst": PAGE_HEAD + PAGE_REFS,
    }


@dataclass
class Built:
    """What a build gives that the tests compare."""

    warnings: list[str]
    needs: dict[str, dict[str, Any]]
    """Every field of every need, from the environment."""
    split: dict[str, tuple[tuple[str, ...], str]]
    """Each need's namespace and local id, as the project read them."""
    needs_json: dict[str, Any]
    page: str


def _write(srcdir: Path, files: dict[str, str]) -> Path:
    srcdir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    return srcdir


@contextmanager
def _app(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, *, fresh: bool = True
) -> Iterator[SphinxTestApp]:
    app = make_app("html", srcdir=srcdir, freshenv=fresh)
    try:
        yield app
    finally:
        app.cleanup()


def _build(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, files: dict[str, str]
) -> Built:
    with _app(make_app, _write(srcdir, files)) as app:
        app.build()
        view = SphinxNeedsData(app.env).get_needs_view()
        data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
        return Built(
            warnings=build_warnings(app),
            needs={k: dict(v) for k, v in view.items()},
            split={k: (v.id_ns_segments, v.id_local) for k, v in view.items()},
            needs_json=data,
            page=Path(app.outdir, "index.html").read_text(encoding="utf-8"),
        )


def _assert_same(namespace: Built, prefix: Built, notices: list[str]) -> None:
    """The namespace build equals the ``id_prefix`` build, but for ``notices``."""
    assert namespace.needs == prefix.needs
    assert namespace.split == prefix.split
    assert namespace.needs_json == prefix.needs_json
    assert namespace.page == prefix.page
    assert [w for w in namespace.warnings if w not in notices] == prefix.warnings
    assert [w for w in namespace.warnings if w in notices] == notices


def at_import(message: str, code: str, line: int = IMPORT_LINE) -> str:
    return f"<srcdir>/index.rst:{line}: WARNING: {message} [needs.{code}]"


def unlocated(message: str, code: str) -> str:
    return f"WARNING: {message} [needs.{code}]"


IMPORT_SOURCE = "Needs import file <srcdir>/src.json"
EXTERNAL_SOURCE = "External needs source 'src.json'"


def outside(source: str, count: int, total: int, ns: str, ids: str) -> str:
    """The text of the ``needs.import_namespace`` notice."""
    return (
        f"{source}: {count} of the {total} needs imported into the namespace {ns!r} "
        f"are outside it: {ids}. An id that starts with ':', or holds '::' but is not "
        "a namespaced id, cannot be joined to a namespace, so each of these is a plain "
        f"id, imported with {ns + '::'!r} in front. Correct the ids in the file, or "
        "suppress needs.import_namespace."
    )


def switched_off(source: str, ns: str) -> str:
    """The text of the ``needs.namespaced_ids_off`` notice of an import."""
    return (
        f"{source}: the namespace {ns!r} puts {ns + '::'!r} in front of the file's ids, "
        "but namespaced ids are off for this project, so they are read as plain ids, "
        "in no namespace. Set needs_namespaced_ids = True to read '::' in an id as a "
        "namespace separator, or suppress needs.namespaced_ids_off."
    )


SRC_OUTSIDE = "'a::::b', ':X'"


# ------------------------------------------------------------------------------------
# (a) equality with the id_prefix of the same text


@pytest.mark.parametrize("namespaced", [True, False], ids=["on", "off"])
def test_needimport_namespace_is_its_prefix(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, namespaced: bool
) -> None:
    """``:namespace: SUP`` gives what ``:id_prefix: SUP::`` gives: every field of every
    need, the needs.json and the page; the only difference is the notice."""
    namespace = _build(
        make_app,
        tmp_path / "namespace",
        _import_project(":namespace: SUP", namespaced=namespaced),
    )
    prefix = _build(
        make_app,
        tmp_path / "prefix",
        _import_project(":id_prefix: SUP::", namespaced=namespaced),
    )
    notice = (
        at_import(outside(IMPORT_SOURCE, 2, 5, "SUP", SRC_OUTSIDE), "import_namespace")
        if namespaced
        else at_import(switched_off(IMPORT_SOURCE, "SUP"), "namespaced_ids_off")
    )
    _assert_same(namespace, prefix, [notice])
    assert sorted(namespace.needs) == [
        "LOCAL_1",
        "SUP:::X",
        "SUP::REQ_1",
        "SUP::REQ_2",
        "SUP::a::::b",
        "SUP::nc::REQ_1",
    ]
    if namespaced:
        assert namespace.split["SUP::nc::REQ_1"] == (("SUP", "nc"), "REQ_1")
        assert namespace.split["SUP::a::::b"] == ((), "SUP::a::::b")
    else:
        assert namespace.split["SUP::nc::REQ_1"] == ((), "SUP::nc::REQ_1")
    req_2 = namespace.needs["SUP::REQ_2"]
    assert req_2["links"] == [
        "SUP::REQ_1",
        "SUP::nc::REQ_1.p1",
        'SUP::REQ_1[status=="open"]',
        "LOCAL_1",
        "SUP::a::::b",
        "SUP:::X",
    ]
    assert req_2["satisfies"] == ["SUP::REQ_1"]
    assert (
        req_2["content"] == "Names SUP::REQ_1, SUP::nc::REQ_1 and :need:`SUP::REQ_1`."
    )


@pytest.mark.parametrize("namespaced", [True, False], ids=["on", "off"])
def test_external_namespace_is_its_prefix(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, namespaced: bool
) -> None:
    """A source's ``namespace = "SUP"`` gives what ``id_prefix = "SUP::"`` gives, the
    external URLs included, and a reference to a part of an external need links the
    part's anchor, from ``:need:`` and from ``:need_outgoing:`` alike."""
    namespace = _build(
        make_app,
        tmp_path / "namespace",
        _external_project({"namespace": "SUP"}, namespaced=namespaced),
    )
    prefix = _build(
        make_app,
        tmp_path / "prefix",
        _external_project({"id_prefix": "SUP::"}, namespaced=namespaced),
    )
    notice = (
        unlocated(
            outside(EXTERNAL_SOURCE, 2, 5, "SUP", SRC_OUTSIDE), "import_namespace"
        )
        if namespaced
        else unlocated(switched_off(EXTERNAL_SOURCE, "SUP"), "namespaced_ids_off")
    )
    _assert_same(namespace, prefix, [notice])
    assert {k: v["external_url"] for k, v in namespace.needs.items()} == {
        "LOCAL_1": None,
        "SUP:::X": f"{BASE_URL}/index.html#:X",
        "SUP::REQ_1": f"{BASE_URL}/index.html#REQ_1",
        "SUP::REQ_2": f"{BASE_URL}/index.html#REQ_2",
        "SUP::a::::b": f"{BASE_URL}/index.html#a::::b",
        "SUP::nc::REQ_1": f"{BASE_URL}/index.html#nc::REQ_1",
    }
    part_href = f'href="{BASE_URL}/index.html#nc::REQ_1.p1"'
    # once from :need:, once from :need_outgoing:
    assert namespace.page.count(part_href) == 2


# ------------------------------------------------------------------------------------
# (b) several levels


def test_needimport_namespace_of_several_levels(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """``:namespace: sup::m2`` puts the file's needs in ``sup::m2``."""
    built = _build(
        make_app,
        tmp_path / "src",
        _import_project(":namespace: sup::m2", data=CLEAN),
    )
    assert built.split == {
        "LOCAL_1": ((), "LOCAL_1"),
        "sup::m2::REQ_1": (("sup", "m2"), "REQ_1"),
        "sup::m2::nc::REQ_1": (("sup", "m2", "nc"), "REQ_1"),
    }
    assert built.needs["sup::m2::nc::REQ_1"]["links"] == ["sup::m2::REQ_1"]


def test_external_namespace_of_several_levels(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """``namespace = "sup::m2"`` puts the source's needs in ``sup::m2``."""
    built = _build(
        make_app,
        tmp_path / "src",
        _external_project({"namespace": "sup::m2"}, data=CLEAN),
    )
    assert built.split == {
        "LOCAL_1": ((), "LOCAL_1"),
        "sup::m2::REQ_1": (("sup", "m2"), "REQ_1"),
        "sup::m2::nc::REQ_1": (("sup", "m2", "nc"), "REQ_1"),
    }


# ------------------------------------------------------------------------------------
# (c) the refusals


NEEDIMPORT_REFUSALS = {
    "both": (
        (":namespace: SUP", ":id_prefix: SUP::"),
        "needimport: :namespace: and :id_prefix: cannot both be given: "
        "':namespace: SUP' is ':id_prefix: SUP::'; give one of them",
    ),
    "both-invalid-namespace": (
        (":namespace: a b", ":id_prefix: SUP::"),
        "needimport: :namespace: and :id_prefix: cannot both be given: "
        "':namespace: SUP' is ':id_prefix: SUP::'; give one of them",
    ),
    "trailing-separator": (
        (":namespace: SUP::",),
        "needimport: :namespace: 'SUP::' is not a namespace: write the namespace "
        "without the trailing '::', 'SUP'",
    ),
    "not-a-segment": (
        (":namespace: a b",),
        "needimport: :namespace: 'a b' is not a namespace: its piece 'a b' is not a "
        "segment, which is one or more ASCII letters, ASCII digits, '_' or '-'",
    ),
    "empty-segment": (
        (":namespace: ::SUP",),
        "needimport: :namespace: '::SUP' is not a namespace: its piece '' is not a "
        "segment, which is one or more ASCII letters, ASCII digits, '_' or '-'",
    ),
}


@pytest.mark.parametrize(
    ("options", "message"),
    NEEDIMPORT_REFUSALS.values(),
    ids=NEEDIMPORT_REFUSALS.keys(),
)
def test_needimport_refuses(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    options: tuple[str, ...],
    message: str,
) -> None:
    """A refused option is one ``needs.needimport`` warning at the directive, and the
    directive imports nothing."""
    built = _build(make_app, tmp_path / "src", _import_project(*options))
    assert sorted(built.needs) == ["LOCAL_1"]
    assert at_import(message, "needimport") in built.warnings
    assert [w for w in built.warnings if "[needs.needimport]" in w] == [
        at_import(message, "needimport")
    ]
    assert "[needs.import_namespace]" not in "".join(built.warnings)
    assert 'class="admonition warning"' in built.page


def test_needimport_empty_namespace_is_docutils_error(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """An empty ``:namespace:`` is docutils' own error: an argument is required."""
    built = _build(make_app, tmp_path / "src", _import_project(":namespace:"))
    assert sorted(built.needs) == ["LOCAL_1"]
    assert any(
        w.startswith(f'<srcdir>/index.rst:{IMPORT_LINE}: ERROR: Error in "needimport"')
        and "argument required but none supplied" in w
        for w in built.warnings
    ), built.warnings


EXTERNAL_REFUSALS = {
    "both": (
        {"namespace": "SUP", "id_prefix": "SUP::"},
        "namespace and id_prefix are both configured in external_needs item 0, but "
        "only one is allowed: namespace 'SUP' is id_prefix 'SUP::'.",
    ),
    "empty": (
        {"namespace": ""},
        "namespace is empty in external_needs item 0: an empty namespace puts no need "
        "into a namespace; remove the key.",
    ),
    "trailing-separator": (
        {"namespace": "SUP::"},
        "namespace 'SUP::' in external_needs item 0 is not a namespace: write the "
        "namespace without the trailing '::', 'SUP'.",
    ),
    "not-a-segment": (
        {"namespace": "a b"},
        "namespace 'a b' in external_needs item 0 is not a namespace: its piece 'a b' "
        "is not a segment, which is one or more ASCII letters, ASCII digits, '_' or "
        "'-'.",
    ),
    "not-a-string": (
        {"namespace": 1},
        "namespace 1 in external_needs item 0 is not a namespace: it must be a string.",
    ),
}


@pytest.mark.parametrize(
    ("keys", "message"), EXTERNAL_REFUSALS.values(), ids=EXTERNAL_REFUSALS.keys()
)
def test_external_source_refuses(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    keys: dict[str, Any],
    message: str,
) -> None:
    """A refused key is a configuration error, as a missing ``base_url`` is: the build
    stops with ``NeedsExternalException``, naming the source."""
    srcdir = _write(tmp_path / "src", _external_project(keys))
    with _app(make_app, srcdir) as app, pytest.raises(NeedsExternalException) as raised:
        app.build()
    assert str(raised.value) == message


def test_external_source_refusal_names_its_item(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The message names the source by its index, as the other refusals do."""
    srcdir = _write(
        tmp_path / "src",
        _external_project({"id_prefix": "A_"}, {"namespace": "SUP::"}),
    )
    with _app(make_app, srcdir) as app, pytest.raises(NeedsExternalException) as raised:
        app.build()
    assert "in external_needs item 1 " in str(raised.value)


def test_external_namespace_from_ubproject_toml(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """``[[needs.external_needs]]`` in ``ubproject.toml`` takes the key too."""
    toml = (
        "[needs]\n"
        "namespaced_ids = true\n"
        "[[needs.external_needs]]\n"
        'json_path = "src.json"\n'
        f'base_url = "{BASE_URL}"\n'
        'namespace = "SUP"\n'
    )
    built = _build(
        make_app,
        tmp_path / "src",
        {
            "conf.py": CONF + 'needs_from_toml = "ubproject.toml"\n',
            "ubproject.toml": toml,
            "src.json": CLEAN,
            "index.rst": "Index\n=====\n",
        },
    )
    assert built.split == {
        "SUP::REQ_1": (("SUP",), "REQ_1"),
        "SUP::nc::REQ_1": (("SUP", "nc"), "REQ_1"),
    }
    assert built.warnings == []


# ------------------------------------------------------------------------------------
# (d) the notice for ids left outside the namespace


def test_needimport_notice_once_per_import(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Two imports of the file, two notices, each at its directive; an import whose ids
    all join gives none; an ``id_prefix`` gives none."""
    built = _build(
        make_app,
        tmp_path / "src",
        _import_project(
            imports=(
                ("src.json", (":namespace: SUP",)),
                ("src.json", (":namespace: OTHER",)),
                ("clean.json", (":namespace: CLEAN",)),
                ("src.json", (":id_prefix: PRE::",)),
            ),
        )
        | {"clean.json": CLEAN},
    )
    notices = [w for w in built.warnings if "[needs.import_namespace]" in w]
    assert notices == [
        at_import(outside(IMPORT_SOURCE, 2, 5, "SUP", SRC_OUTSIDE), "import_namespace"),
        at_import(
            outside(IMPORT_SOURCE, 2, 5, "OTHER", SRC_OUTSIDE),
            "import_namespace",
            line=IMPORT_LINE + 3,
        ),
    ]
    assert "[needs.namespaced_ids_off]" not in "".join(built.warnings)


def test_needimport_notice_counts_the_needs_imported(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """The notice counts the needs the directive imports (``:ids:`` selects two, one of
    them outside), and none when none it imports is outside."""
    built = _build(
        make_app,
        tmp_path / "src",
        _import_project(
            imports=(
                ("src.json", (":namespace: SUP", ":ids: REQ_1, :X")),
                ("src.json", (":namespace: OTHER", ":ids: REQ_1, nc::REQ_1")),
            ),
        ),
    )
    assert [w for w in built.warnings if "[needs.import_namespace]" in w] == [
        at_import(outside(IMPORT_SOURCE, 1, 2, "SUP", "':X'"), "import_namespace")
    ]


def test_notice_names_the_first_five(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Of eight ids outside, the notice names the first five, and how many more."""
    built = _build(
        make_app, tmp_path / "src", _import_project(":namespace: SUP", data=MANY)
    )
    names = "':B0', ':B1', ':B2', ':B3', ':B4' and 3 more"
    assert [w for w in built.warnings if "[needs.import_namespace]" in w] == [
        at_import(outside(IMPORT_SOURCE, 8, 8, "SUP", names), "import_namespace")
    ]


def test_external_notice_once_per_source(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Two sources of the file under two namespaces, two notices; a source whose ids
    all join gives none."""
    built = _build(
        make_app,
        tmp_path / "src",
        _external_project(
            {"namespace": "SUP"},
            {"namespace": "OTHER"},
            {"namespace": "CLEAN", "json_path": "clean.json"},
        )
        | {"clean.json": CLEAN},
    )
    assert [w for w in built.warnings if "[needs.import_namespace]" in w] == [
        unlocated(
            outside(EXTERNAL_SOURCE, 2, 5, "SUP", SRC_OUTSIDE), "import_namespace"
        ),
        unlocated(
            outside(EXTERNAL_SOURCE, 2, 5, "OTHER", SRC_OUTSIDE), "import_namespace"
        ),
    ]


def test_no_notice_when_every_id_joins(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A namespace whose every id joins gives no warning at all."""
    for reader, files in (
        ("import", _import_project(":namespace: SUP", data=CLEAN)),
        ("external", _external_project({"namespace": "SUP"}, data=CLEAN)),
    ):
        files["index.rst"] = (
            files["index.rst"]
            .replace(PAGE_REFS, "")
            .replace("   :links: SUP::nc::REQ_1.p1\n", "")
        )
        built = _build(make_app, tmp_path / reader, files)
        assert built.warnings == [], reader


# ------------------------------------------------------------------------------------
# (e) with namespaced ids off


@pytest.mark.parametrize("namespaced", [False, None], ids=["off", "default"])
def test_switched_off_notice_once_per_import(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, namespaced: bool | None
) -> None:
    """With namespaced ids off (the default in 9.x), each import under a namespace
    gives one ``needs.namespaced_ids_off``, whether or not its ids join, and no
    ``needs.import_namespace``; an ``id_prefix`` gives neither."""
    built = _build(
        make_app,
        tmp_path / "import",
        _import_project(
            namespaced=namespaced,
            imports=(
                ("src.json", (":namespace: SUP",)),
                ("clean.json", (":namespace: CLEAN",)),
                ("src.json", (":id_prefix: PRE::",)),
            ),
        )
        | {"clean.json": CLEAN},
    )
    assert "[needs.import_namespace]" not in "".join(built.warnings)
    assert [w for w in built.warnings if "[needs.namespaced_ids_off]" in w] == [
        at_import(switched_off(IMPORT_SOURCE, "SUP"), "namespaced_ids_off"),
        at_import(
            switched_off("Needs import file <srcdir>/clean.json", "CLEAN"),
            "namespaced_ids_off",
            line=IMPORT_LINE + 3,
        ),
    ]
    external = _build(
        make_app,
        tmp_path / "external",
        _external_project(
            {"namespace": "SUP"},
            {"namespace": "CLEAN", "json_path": "clean.json"},
            {"id_prefix": "PRE::"},
            namespaced=namespaced,
        )
        | {"clean.json": CLEAN},
    )
    assert "[needs.import_namespace]" not in "".join(external.warnings)
    assert [w for w in external.warnings if "[needs.namespaced_ids_off]" in w] == [
        unlocated(switched_off(EXTERNAL_SOURCE, "SUP"), "namespaced_ids_off"),
        unlocated(
            switched_off("External needs source 'clean.json'", "CLEAN"),
            "namespaced_ids_off",
        ),
    ]


# ------------------------------------------------------------------------------------
# (f) suppression, each type alone


@pytest.mark.parametrize("reader", ["import", "external"])
@pytest.mark.parametrize(
    ("namespaced", "suppressed", "silenced"),
    [
        (True, "needs.import_namespace", True),
        (True, "needs.namespaced_ids_off", False),
        (False, "needs.namespaced_ids_off", True),
        (False, "needs.import_namespace", False),
    ],
    ids=["on-own", "on-other", "off-own", "off-other"],
)
def test_suppression_by_type(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    reader: str,
    namespaced: bool,
    suppressed: str,
    silenced: bool,
) -> None:
    """``suppress_warnings`` with the notice's type alone silences that notice and
    nothing else; with the other type alone, the notice stays."""

    def files(option: str, suppress: str = "") -> dict[str, str]:
        extra = f"suppress_warnings = [{suppress!r}]\n" if suppress else ""
        if reader == "import":
            return _import_project(option, namespaced=namespaced, extra=extra)
        key, value = option.split(": ")[0].strip(":"), option.split(": ")[1]
        return _external_project({key: value}, namespaced=namespaced, extra=extra)

    namespace = _build(make_app, tmp_path / "ns", files(":namespace: SUP", suppressed))
    prefix = _build(make_app, tmp_path / "prefix", files(":id_prefix: SUP::"))
    notice_type = "import_namespace" if namespaced else "namespaced_ids_off"
    notices = [w for w in namespace.warnings if f"[needs.{notice_type}]" in w]
    assert len(notices) == (0 if silenced else 1)
    assert [w for w in namespace.warnings if w not in notices] == prefix.warnings
