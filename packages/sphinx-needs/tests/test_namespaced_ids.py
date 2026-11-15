"""Namespaced ids: ``nc::m2::REQ_1`` is the namespace ``nc::m2`` and the local id ``REQ_1``.

The grammar (where an id splits, and what does not split cleanly) is
``ub_needs_exchange.need_id``'s and its own corpus pins it; this module pins what
sphinx-needs makes of it: the switch ``needs_namespaced_ids``, the two values stored on
every need at its creation (``need.id_ns``, ``need.id_ns_segments``, ``need.id_local``),
that they are no field (no mapping key, no ``needs.json`` key, no reserved name), and
that every way a need is copied or stored keeps them. The design record is
``design/namespaced-ids.md``.
"""

from __future__ import annotations

import ast
import copy
import io
import json
import pickle
import re
from pathlib import Path
from typing import Any

import pytest
from sphinx.util.parallel import parallel_available

import sphinx_needs
from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsCoreFields, SphinxNeedsData
from sphinx_needs.need_item import NeedItem
from sphinx_needs_testkit import build_warnings

#: a pattern every id of these projects passes as a whole, so that what they pin does
#: not depend on how the id patterns read a namespaced id
CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_id_regex = r"^[A-Za-z0-9_:]+$"
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_"},
    {"directive": "spec", "title": "Specification", "prefix": "nc::spec::"},
]
needs_external_needs = [
    {"base_url": "http://ext.example", "json_path": "ext.json", "id_prefix": "EXT::"}
]
"""

INDEX = """\
Index
=====

.. req:: Plain
   :id: PLAIN_001

.. req:: One segment
   :id: SUPPLIER::REQ_001

.. req:: Two segments
   :id: nc::m2::REQ_002

   A part :np:`(p1) of it`.

.. req:: One segment again
   :id: nc::REQ_003

.. req:: Same namespace as the two-segment one
   :id: nc::m2::REQ_004

.. spec:: Generated, with a prefix holding the separator

.. needimport:: imp.json
   :id_prefix: SUP::
"""

IMPORTED = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "IMP_001": {
                        "id": "IMP_001",
                        "type": "req",
                        "title": "Imported",
                        "content": "",
                    },
                    "up::IMP_002": {
                        "id": "up::IMP_002",
                        "type": "req",
                        "title": "Imported, namespaced upstream",
                        "content": "",
                    },
                }
            }
        },
    }
)

EXTERNAL = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "EX_001": {
                        "id": "EX_001",
                        "type": "req",
                        "title": "External",
                        "content": "",
                        "docname": "page",
                    }
                }
            }
        },
    }
)

#: what each need's namespace and local id are, the switch on
SPLIT = {
    "PLAIN_001": ((), "PLAIN_001"),
    "SUPPLIER::REQ_001": (("SUPPLIER",), "REQ_001"),
    "nc::m2::REQ_002": (("nc", "m2"), "REQ_002"),
    "nc::REQ_003": (("nc",), "REQ_003"),
    "nc::m2::REQ_004": (("nc", "m2"), "REQ_004"),
    "SUP::IMP_001": (("SUP",), "IMP_001"),
    "SUP::up::IMP_002": (("SUP", "up"), "IMP_002"),
    "EXT::EX_001": (("EXT",), "EX_001"),
}


def _project(
    conf: str = CONF, index: str = INDEX, buildername: str = "needs", **more: Any
) -> dict[str, Any]:
    return {
        "buildername": buildername,
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), index),
            (Path("imp.json"), IMPORTED),
            (Path("ext.json"), EXTERNAL),
        ],
        **more,
    }


def _needs(app: Any) -> Any:
    return SphinxNeedsData(app.env).get_needs_view()


def _generated(needs: Any) -> str:
    """The id of the one need of type ``spec``, generated from its type's prefix."""
    (need_id,) = (key for key, need in needs.items() if need["type"] == "spec")
    return need_id


def _split(need: Any) -> tuple[tuple[str, ...], str]:
    return need.id_ns_segments, need.id_local


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_every_route_splits_its_ids_at_creation(test_app: Any) -> None:
    """On by default: an authored, a generated, an imported and an external id each
    split at the last ``::``, once, where the need is created; ``id`` is the whole id
    and the key."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert NeedsSphinxConfig(app.config).namespaced_ids is True
    needs = _needs(app)
    generated = _generated(needs)
    assert generated.startswith("nc::spec::")
    assert {key: _split(need) for key, need in needs.items()} == {
        **SPLIT,
        generated: (("nc", "spec"), generated[len("nc::spec::") :]),
    }
    for key, need in needs.items():
        assert need.id == need["id"] == key
        assert need.id_ns == "::".join(need.id_ns_segments)
        assert isinstance(need.id_ns_segments, tuple)
    assert needs["nc::m2::REQ_002"].id_ns == "nc::m2"
    assert needs["PLAIN_001"].id_ns == ""


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_one_tuple_per_namespace(test_app: Any) -> None:
    """The needs of one namespace share one tuple of its segments."""
    app = test_app
    app.build()
    needs = _needs(app)
    assert needs["nc::m2::REQ_002"].id_ns_segments is (
        needs["nc::m2::REQ_004"].id_ns_segments
    )


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_a_part_answers_with_its_need(test_app: Any) -> None:
    """A part has its own ``id`` (the part's), and its need's namespace and local id."""
    app = test_app
    app.build()
    part = _needs(app)["nc::m2::REQ_002"].get_part_item("p1")
    assert part is not None
    assert part["id"] == "p1"
    assert part["id_complete"] == "nc::m2::REQ_002.p1"
    assert (part.id_ns, part.id_ns_segments, part.id_local) == (
        "nc::m2",
        ("nc", "m2"),
        "REQ_002",
    )
    table_row = part.copy_for_needtable()
    assert table_row["id"] == "nc::m2::REQ_002.p1"
    assert (table_row.id_ns, table_row.id_local) == ("nc::m2", "REQ_002")


@pytest.mark.parametrize(
    "test_app",
    [
        _project(CONF + "needs_namespaced_ids = False\n"),
        {
            **_project(CONF + 'needs_from_toml = "ubproject.toml"\n'),
            "files": [
                *_project(CONF + 'needs_from_toml = "ubproject.toml"\n')["files"],
                (Path("ubproject.toml"), "[needs]\nnamespaced_ids = false\n"),
            ],
        },
    ],
    indirect=True,
    ids=["conf.py", "ubproject.toml"],
)
def test_switched_off_no_id_splits(test_app: Any) -> None:
    """``needs_namespaced_ids = False`` (``[needs] namespaced_ids = false``): every
    need is plain, whatever its id holds."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert NeedsSphinxConfig(app.config).namespaced_ids is False
    for key, need in _needs(app).items():
        assert (need.id_ns, need.id_ns_segments, need.id_local) == ("", (), key)


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_the_values_are_no_field(test_app: Any) -> None:
    """Not a mapping key, not a core field, not a needs.json key: the two values are
    attributes of the need alone."""
    app = test_app
    app.build()
    need = _needs(app)["nc::m2::REQ_002"]
    for name in ("id_ns", "id_ns_segments", "id_local", "ns", "local_id"):
        assert name not in need
        assert name not in dict(need.items())
        assert name not in NeedsCoreFields
        assert name not in need.filter_context()
    data = json.loads(Path(app.outdir, "needs.json").read_text("utf-8"))
    version = data["versions"][data["current_version"]]
    assert set(version["needs"]["nc::m2::REQ_002"]) == set(
        version["needs"]["PLAIN_001"]
    )
    assert not {"id_ns", "id_local", "id_ns_segments"} & set(
        version["needs_schema"]["properties"]
    )


@pytest.mark.parametrize("test_app", [_project()], indirect=True)
def test_copying_and_pickling_keep_the_values(test_app: Any) -> None:
    """``copy()``, ``copy.copy``, ``copy.deepcopy`` and a pickle round trip (how the
    environment and a parallel read store a need) each keep both values."""
    app = test_app
    app.build()
    need = _needs(app)["nc::m2::REQ_002"]
    for other in (
        need.copy(),
        copy.copy(need),
        copy.deepcopy(need),
        pickle.loads(pickle.dumps(need)),
    ):
        assert isinstance(other, NeedItem)
        assert _split(other) == (("nc", "m2"), "REQ_002")
        assert other.id_ns == "nc::m2"
        assert other == need


#: the names a project may declare as fields, as before: the stored values are no field
FREE_NAMES = ("ns", "local_id", "id_ns", "id_local")


@pytest.mark.parametrize(
    "test_app",
    [
        _project(
            CONF
            + "needs_fields = {"
            + ", ".join(f'"{name}": {{"nullable": True}}' for name in FREE_NAMES)
            + "}\n",
            INDEX.replace(
                "   :id: nc::REQ_003\n",
                "   :id: nc::REQ_003\n"
                + "".join(f"   :{name}: v_{name}\n" for name in FREE_NAMES),
            )
            + "\n.. needtable::\n   :filter: ns == 'v_ns' and id_local == 'v_id_local'\n"
            "   :columns: id\n",
            buildername="html",
        )
    ],
    indirect=True,
)
def test_the_names_stay_free_for_fields(test_app: Any) -> None:
    """A project declaring fields named ``ns``, ``local_id``, ``id_ns`` and
    ``id_local`` builds as before: each is a field, which a filter reads, and the
    need's attributes are left as they are."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    need = _needs(app)["nc::REQ_003"]
    assert {name: need[name] for name in FREE_NAMES} == {
        name: f"v_{name}" for name in FREE_NAMES
    }
    assert (need.id_ns, need.id_local) == ("nc", "REQ_003")
    html = Path(app.outdir, "index.html").read_text("utf-8")
    assert 'data-need-id="nc::REQ_003"' in html


def _needs_json(app: Any) -> bytes:
    """The needs.json the build wrote, but for the time it was written at."""
    return re.sub(
        rb'"created": "[^"]*"',
        b'"created": ""',
        Path(app.outdir, "needs.json").read_bytes(),
    )


@pytest.mark.parametrize("format_version", ["1", "2a1"])
def test_needs_json_is_the_same_bytes_either_way(
    format_version: str, make_app: Any, tmp_path: Path
) -> None:
    """A project holding namespaced ids writes the same needs.json, format 1 and the
    draft ``"2a1"`` alike, with the switch on and off: the values reach no file."""
    written = []
    for switch in (True, False):
        srcdir = tmp_path / f"src_{switch}"
        srcdir.mkdir()
        conf = CONF + f"needs_namespaced_ids = {switch}\n"
        if format_version != "1":
            conf += f'needs_json_format_version = "{format_version}"\n'
        for name, text in _project(conf)["files"]:
            (srcdir / name).write_text(text, "utf-8")
        app = make_app(
            srcdir=srcdir,
            buildername="needs",
            freshenv=True,
            status=io.StringIO(),
            warning=io.StringIO(),
        )
        app.build()
        # a second application in one process re-registers Sphinx's own nodes
        assert [
            w for w in build_warnings(app) if "[needs." in w and "[needs.beta]" not in w
        ] == []
        written.append(_needs_json(app))
    assert written[0] == written[1]
    assert b"nc::m2::REQ_002" in written[0]


def _string_constants(path: Path) -> list[tuple[int, str]]:
    """The ``str`` and ``bytes`` constants of a module equal to the separator."""
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    return [
        (node.lineno, repr(node.value))
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and node.value in ("::", b"::")
    ]


def test_only_the_exchange_package_spells_the_separator() -> None:
    """No string constant of sphinx-needs is ``"::"``: every split, join, parse and
    format of a namespaced id goes through ``ub_needs_exchange.need_id``, the one module
    that knows the separator (it is imported there as ``SEPARATOR`` where a test for it
    is needed).

    What this cannot see: a separator built at run time (``":" * 2``), a constant that
    holds ``::`` inside a longer string (a regular expression, a message, a docstring:
    ``"a::b"`` is not the separator), and code outside ``src/sphinx_needs``. It needs no
    allow-list.
    """
    package = Path(sphinx_needs.__file__).parent
    found = {
        str(path.relative_to(package)): hits
        for path in sorted(package.rglob("*.py"))
        if (hits := _string_constants(path))
    }
    assert found == {}


@pytest.mark.parametrize("parallel", [0, 2], ids=["serial", "parallel"])
def test_the_environment_keeps_the_values(
    parallel: int, make_app: Any, tmp_path: Path
) -> None:
    """A need read in a parallel worker (``-j 2``: merged into the main environment),
    and a need of an unchanged document in a second, incremental build (read back from
    the pickled environment), keep their namespace and local id."""
    if parallel and not parallel_available:
        pytest.skip("this platform reads in one process")
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    for name, text in _project()["files"]:
        (srcdir / name).write_text(text, "utf-8")
    # Sphinx reads in parallel from six documents on
    pages = [f"page{i}" for i in range(6)]
    for i, page in enumerate(pages):
        (srcdir / f"{page}.rst").write_text(
            f"Page {i}\n======\n\n.. req:: On page {i}\n   :id: pg::p{i}::REQ_{i}\n",
            "utf-8",
        )
    (srcdir / "index.rst").write_text(
        INDEX + "\n.. toctree::\n\n   " + "\n   ".join(pages) + "\n", "utf-8"
    )

    def build() -> Any:
        app = make_app(
            "html",
            srcdir=srcdir,
            status=io.StringIO(),
            warning=io.StringIO(),
            parallel=parallel,
        )
        app.build()
        return app

    expected = {
        **SPLIT,
        **{f"pg::p{i}::REQ_{i}": (("pg", f"p{i}"), f"REQ_{i}") for i in range(6)},
    }
    first = build()
    # the parallel build did read in chunks, in worker processes
    chunked = re.search(
        r"reading sources\.\.\. \[ *\d+%\] \S+ \.\. ",
        re.sub(r"\x1b\[[0-9;]*m", "", first._status.getvalue()),
    )
    assert (chunked is not None) is bool(parallel)
    needs = _needs(first)
    assert {key: _split(needs[key]) for key in expected} == expected
    # change one page only: the others are read back from the pickled environment
    (srcdir / "page0.rst").write_text(
        "Page 0\n======\n\n.. req:: Changed\n   :id: pg::p0::REQ_0\n", "utf-8"
    )
    second = build()
    status = re.sub(r"\x1b\[[0-9;]*m", "", second._status.getvalue())
    assert "updating environment: 0 added, 1 changed, 0 removed" in status, status
    needs = _needs(second)
    assert {key: _split(needs[key]) for key in expected} == expected
    assert needs["pg::p0::REQ_0"]["title"] == "Changed"
