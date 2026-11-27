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
import contextlib
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
needs_namespaced_ids = True
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


@pytest.mark.parametrize("format_version", ["1", "2a2"])
def test_needs_json_is_the_same_bytes_either_way(
    format_version: str, make_app: Any, tmp_path: Path
) -> None:
    """A project holding namespaced ids writes the same needs.json, format 1 and the
    draft ``"2a2"`` alike, with the switch on and off: the values reach no file."""
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


# --- the warning for an id that holds the separator and does not split cleanly ---

#: the switch on, nothing else: the project the pattern pins read
ON = 'extensions = ["sphinx_needs"]\nneeds_namespaced_ids = True\n'

#: no id pattern: what these pin does not depend on how the patterns read an id
UNCHECKED = """\
extensions = ["sphinx_needs"]
needs_namespaced_ids = True
needs_id_regex = ""
"""


def _unclean(need_id: str, reason: str) -> str:
    """The warning for an authored id that does not split cleanly, without a location."""
    return (
        f"WARNING: Need id {need_id!r} contains '::' but is not a namespaced id "
        f"({reason}), so it is read as a plain id. Correct the id, set "
        "needs_namespaced_ids = False to read no id as namespaced, or suppress the "
        "warning type needs.id_namespace. [needs.id_namespace]"
    )


#: each problem class of the grammar, with the reason the warning gives for it
UNCLEAN = {
    "NS::": "nothing follows the last '::'",
    "A::::B": "a namespace segment is empty",
    "std::vector<int>::size": (
        "a namespace segment holds a character other than a letter, a digit, '_' or '-'"
    ),
}

UNCLEAN_INDEX = "Index\n=====\n" + "".join(
    f"\n.. req:: Unclean {i}\n   :id: {need_id}\n" for i, need_id in enumerate(UNCLEAN)
)


def _unclean_project(conf: str = UNCHECKED, index: str = UNCLEAN_INDEX) -> Any:
    return {
        "buildername": "needs",
        "files": [(Path("conf.py"), conf), (Path("index.rst"), index)],
    }


@pytest.mark.parametrize("test_app", [_unclean_project()], indirect=True)
def test_an_authored_id_that_does_not_split_is_warned_and_kept(test_app: Any) -> None:
    """One warning per need, at the need, naming the problem's class and the three ways
    out; the need is kept, as a plain id."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:{4 + 3 * i}: {_unclean(need_id, reason)}"
        for i, (need_id, reason) in enumerate(UNCLEAN.items())
    ]
    needs = _needs(app)
    assert sorted(needs) == sorted(UNCLEAN)
    for need_id in UNCLEAN:
        assert (needs[need_id].id_ns, needs[need_id].id_local) == ("", need_id)


@pytest.mark.parametrize(
    "test_app",
    [
        _unclean_project(UNCHECKED + "needs_namespaced_ids = False\n"),
        _unclean_project(UNCHECKED + 'suppress_warnings = ["needs.id_namespace"]\n'),
    ],
    indirect=True,
    ids=["switched-off", "suppressed"],
)
def test_no_warning_switched_off_or_suppressed(test_app: Any) -> None:
    """With the switch off no id is read as namespaced, so none is warned; the warning
    type can be suppressed. Either way the needs are kept."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    assert sorted(_needs(app)) == sorted(UNCLEAN)


@pytest.mark.parametrize(
    "test_app",
    [_unclean_project(ON + 'needs_id_regex = "^X"\n')],
    indirect=True,
)
def test_a_refused_need_is_reported_for_its_refusal(test_app: Any) -> None:
    """The warning is the funnel's last act: a need an id pattern refuses is reported
    for that, and not for its id not splitting cleanly."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    assert len(warnings) == len(UNCLEAN)
    assert all(w.endswith("[needs.create_need]") for w in warnings), warnings
    assert dict(_needs(app)) == {}


def _record_file(need_id: str, **more: str) -> str:
    return json.dumps(
        {
            "current_version": "1.0",
            "versions": {
                "1.0": {
                    "needs": {
                        need_id: {
                            "id": need_id,
                            "type": "req",
                            "title": "From outside",
                            "content": "",
                            **more,
                        }
                    }
                }
            },
        }
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (Path("conf.py"), UNCHECKED),
                (Path("index.rst"), "Index\n=====\n\n.. needimport:: imp.json\n"),
                (Path("imp.json"), _record_file("A::::B")),
            ],
        },
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    UNCHECKED + "needs_external_needs = [{'base_url': 'http://x', "
                    "'json_path': 'ext.json'}]\n",
                ),
                (Path("index.rst"), "Index\n=====\n"),
                (Path("ext.json"), _record_file("A::::B", docname="page")),
            ],
        },
    ],
    indirect=True,
    ids=["imported", "external"],
)
def test_an_id_from_outside_is_not_warned(test_app: Any) -> None:
    """An imported and an external need are the source's data: their id is not warned,
    and it is a plain id."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    need = _needs(app)["A::::B"]
    assert (need.id_ns, need.id_local) == ("", "A::::B")


@pytest.mark.parametrize(
    "test_app",
    [
        _unclean_project(
            UNCHECKED
            + 'needs_types = [{"directive": "req", "title": "R", "prefix": "A::::"}]\n',
            "Index\n=====\n\n.. req:: Generated from a prefix\n",
        ),
        _unclean_project(
            UNCHECKED + "needs_id_from_title = True\nneeds_id_length = 30\n",
            "Index\n=====\n\n.. req:: std::vector<int>::size\n",
        ),
    ],
    indirect=True,
    ids=["type-prefix", "id-from-title"],
)
def test_a_generated_id_is_the_projects_own(test_app: Any) -> None:
    """An id the project generates (a type's prefix, ``needs_id_from_title``) is
    warned as an authored one is."""
    app = test_app
    app.build()
    ((need_id, need),) = _needs(app).items()
    if need_id.startswith("A::::"):
        problem = "a namespace segment is empty"
    else:
        assert need_id.startswith("R_STD::VECTOR<INT>::SIZE")
        problem = UNCLEAN["std::vector<int>::size"]
    assert build_warnings(app) == [
        f"<srcdir>/index.rst:4: {_unclean(need_id, problem)}"
    ]
    assert need.id_local == need_id


# --- id patterns: the local id, or the whole id ---

#: the default needs_id_regex, ``^[A-Z0-9_]{5,}``, applied with ``re.match``
PATTERN_INDEX = """\
Index
=====

.. req:: Namespaced, the local id matches
   :id: nc::REQ_00001

.. req:: Namespaced, nothing matches
   :id: nc::req

.. req:: Namespaced, the whole id matches
   :id: SUPPLIER::REQ_1

.. req:: Accepted by master as a whole, its local id does not match
   :id: REQ_1::A
"""


def _refused(need_id: str, line: int, local: str | None, pattern: str) -> str:
    nor = "" if local is None else f", nor does its local id {local!r}"
    return (
        f"<srcdir>/index.rst:{line}: WARNING: Need could not be created: Given ID "
        f"{need_id!r} does not match {pattern}{nor} [needs.create_need]"
    )


DEFAULT = "configured regex '^[A-Z0-9_]{5,}'"


@pytest.mark.parametrize(
    "test_app",
    [_unclean_project(ON, PATTERN_INDEX)],
    indirect=True,
)
def test_the_default_pattern_accepts_a_matching_local_id(test_app: Any) -> None:
    """``needs_id_regex`` accepts an id whose local id matches, or which matches as a
    whole: ``nc::REQ_00001`` (refused before namespaces) and ``REQ_1::A`` (accepted
    before, as a whole) are both accepted; the refusal names the local id too."""
    app = test_app
    app.build()
    assert build_warnings(app) == [_refused("nc::req", 7, "req", DEFAULT)]
    assert sorted(_needs(app)) == ["REQ_1::A", "SUPPLIER::REQ_1", "nc::REQ_00001"]


@pytest.mark.parametrize(
    "test_app",
    [
        _unclean_project(
            'extensions = ["sphinx_needs"]\nneeds_namespaced_ids = False\n',
            PATTERN_INDEX,
        )
    ],
    indirect=True,
)
def test_switched_off_the_pattern_reads_the_whole_id(test_app: Any) -> None:
    """With the switch off every id is plain: the pattern reads it whole, as before."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        _refused("nc::REQ_00001", 4, None, DEFAULT),
        _refused("nc::req", 7, None, DEFAULT),
    ]
    assert sorted(_needs(app)) == ["REQ_1::A", "SUPPLIER::REQ_1"]


TYPE_PATTERN = """\
extensions = ["sphinx_needs"]
needs_namespaced_ids = True
needs_id_regex = ""
needs_from_toml = "ubproject.toml"
"""

TYPE_TOML = """\
[needs.types.req]
title = "Requirement"
prefix = "R_"
id_regex = "^REQ_[0-9]+$"
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **_unclean_project(TYPE_PATTERN, PATTERN_INDEX),
            "files": [
                *_unclean_project(TYPE_PATTERN, PATTERN_INDEX)["files"],
                (Path("ubproject.toml"), TYPE_TOML),
            ],
        }
    ],
    indirect=True,
)
def test_a_type_pattern_accepts_a_matching_local_id(test_app: Any) -> None:
    """A need type's ``id_regex`` reads the id as ``needs_id_regex`` does."""
    app = test_app
    app.build()
    pattern = "the id_regex '^REQ_[0-9]+$' of need type 'req'"
    assert build_warnings(app) == [
        _refused("nc::req", 7, "req", pattern),
        _refused("REQ_1::A", 13, "A", pattern),
    ]
    assert sorted(_needs(app)) == ["SUPPLIER::REQ_1", "nc::REQ_00001"]


EXTRACT_INDEX = """\
Index
=====

.. req:: Present
   :id: nc::REQ_00001

.. needextract:: nc::REQ_00002

.. needextract:: nc::REQ_00001
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **_unclean_project(ON, EXTRACT_INDEX),
            "buildername": "html",
        }
    ],
    indirect=True,
)
def test_needextract_reads_a_namespaced_argument_as_an_id(test_app: Any) -> None:
    """The argument of a needextract is an id that names no need, rather than a filter,
    when ``needs_id_regex`` matches its local id or the whole of it (in full)."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:7: WARNING: Requested need 'nc::REQ_00002' not found. "
        "[needs.needextract]"
    ]
    html = Path(app.outdir, "index.html").read_text("utf-8")
    assert html.count('id="nc::REQ_00001"') == 2


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **_unclean_project(
                'extensions = ["sphinx_needs"]\nneeds_id_regex = "^[a-z]"\n',
                "Index\n=====\n\n.. req:: Present\n   :id: req_1\n\n"
                '.. needextract:: type == "req"\n',
            ),
            "buildername": "html",
        }
    ],
    indirect=True,
)
def test_needextract_matches_an_argument_as_an_id_in_full(test_app: Any) -> None:
    """An argument whose start alone matches ``needs_id_regex`` is a filter, as before:
    the id test is a full match (``re.fullmatch``), of the local id or the whole id."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    html = Path(app.outdir, "index.html").read_text("utf-8")
    assert html.count('id="req_1"') == 2


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **_unclean_project(
                'extensions = ["sphinx_needs"]\nneeds_namespaced_ids = False\n',
                EXTRACT_INDEX,
            ),
            "buildername": "html",
        }
    ],
    indirect=True,
)
def test_needextract_follows_the_switch(test_app: Any) -> None:
    """With the switch off the argument's id is read whole: ``nc::REQ_00002`` is not
    id-shaped under the default pattern, so it is not "not found" but a filter (which
    fails: this branch does not change how a filter that is no Python is reported)."""
    app = test_app
    # the filter's failure is not this test's
    with contextlib.suppress(Exception):
        app.build()
    assert not [w for w in build_warnings(app) if "not found" in w]


def test_flipping_the_switch_re_reads_every_document(
    make_app: Any, tmp_path: Path
) -> None:
    """``needs_namespaced_ids`` changes what is stored on every need: flipping it between
    two builds of one source directory re-reads every document, so the stored values
    and the filters follow it."""
    from sphinx_needs.filter_common import filter_needs_view

    srcdir = tmp_path / "src"
    srcdir.mkdir()
    for name, text in _project()["files"]:
        (srcdir / name).write_text(text, "utf-8")
    answers = []
    for switch in (True, False, True):
        app = make_app(
            "html",
            srcdir=srcdir,
            status=io.StringIO(),
            warning=io.StringIO(),
            confoverrides={"needs_namespaced_ids": switch},
        )
        app.build()
        needs = _needs(app)
        answers.append(
            (
                needs["nc::REQ_003"].id_ns_segments,
                sorted(
                    n["id"]
                    for n in filter_needs_view(
                        needs, NeedsSphinxConfig(app.config), 'c.in_namespace("nc")'
                    )
                ),
            )
        )
    on = (("nc",), ["nc::REQ_003", "nc::m2::REQ_002", "nc::m2::REQ_004"])
    assert answers[0][0] == on[0]
    assert answers[1] == ((), [])
    assert answers[2] == answers[0]


# --- filters: c.id.ns, c.id.local, c.in_namespace() ---

FILTER_INDEX = """\
Index
=====

.. req:: Plain
   :id: PLAIN_001

.. req:: One segment
   :id: nc::REQ_001

.. req:: Two segments
   :id: nc::m2::REQ_002

   A part :np:`(p1) of it`.

.. req:: A look-alike namespace
   :id: ncx::REQ_001

.. req:: Not split cleanly
   :id: A::::B
"""

FILTER_CONF = (
    UNCHECKED
    + 'suppress_warnings = ["needs.id_namespace"]\nneeds_filter_data = {"nsv": "nc"}\n'
)

#: each filter, and what it selects of FILTER_INDEX with the switch on and off
FILTERS: dict[str, tuple[list[str], list[str]]] = {
    'c.id.ns == "nc"': (["nc::REQ_001"], []),
    'c.id.ns == "nc::m2"': (["nc::m2::REQ_002"], []),
    'c.id.ns == ""': (
        ["A::::B", "PLAIN_001"],
        [
            *sorted(
                [
                    "A::::B",
                    "PLAIN_001",
                    "nc::REQ_001",
                    "nc::m2::REQ_002",
                    "ncx::REQ_001",
                ]
            )
        ],
    ),
    'c.id.local == "REQ_001"': (["nc::REQ_001", "ncx::REQ_001"], []),
    'c.id.local == "A::::B"': (["A::::B"], ["A::::B"]),
    "c.id.local == id": (
        ["A::::B", "PLAIN_001"],
        [
            *sorted(
                [
                    "A::::B",
                    "PLAIN_001",
                    "nc::REQ_001",
                    "nc::m2::REQ_002",
                    "ncx::REQ_001",
                ]
            )
        ],
    ),
    'c.id.ns in ["nc", "ncx"]': (["nc::REQ_001", "ncx::REQ_001"], []),
    'c.id.ns.startswith("nc")': (
        ["nc::REQ_001", "nc::m2::REQ_002", "ncx::REQ_001"],
        [],
    ),
    'c.in_namespace("nc")': (["nc::REQ_001", "nc::m2::REQ_002"], []),
    'c.in_namespace("nc::m2")': (["nc::m2::REQ_002"], []),
    'c.in_namespace("m2")': ([], []),
    'not c.in_namespace("nc")': (
        ["A::::B", "PLAIN_001", "ncx::REQ_001"],
        [
            *sorted(
                [
                    "A::::B",
                    "PLAIN_001",
                    "nc::REQ_001",
                    "nc::m2::REQ_002",
                    "ncx::REQ_001",
                ]
            )
        ],
    ),
    "c.in_namespace(nsv)": (["nc::REQ_001", "nc::m2::REQ_002"], []),
    'id == "nc::REQ_001"': (["nc::REQ_001"], ["nc::REQ_001"]),
}


def _filter_project(on: bool) -> dict[str, Any]:
    conf = FILTER_CONF + ("" if on else "needs_namespaced_ids = False\n")
    return _unclean_project(conf, FILTER_INDEX)


def _both_tiers(app: Any, filter_string: str, parts: bool = False) -> Any:
    """What a filter selects, by the engine and by ``eval`` alone, need by need."""
    from unittest.mock import patch

    from sphinx_needs import filter_common
    from sphinx_needs.filter_common import filter_needs_parts, filter_needs_view
    from sphinx_needs.ubquery import CompiledFilter

    view = _needs(app)
    config = NeedsSphinxConfig(app.config)

    def select() -> list[str]:
        if parts:
            found = filter_needs_parts(view.to_list_with_parts(), config, filter_string)
        else:
            found = filter_needs_view(view, config, filter_string)
        return sorted(item["id_complete"] for item in found)

    engine = select()
    refused = CompiledFilter(None, "refused", False)
    with patch.object(filter_common, "compile_portable", lambda _: refused):
        evaluated = select()
    return engine, evaluated


@pytest.mark.parametrize("on", [True, False], ids=["on", "off"])
@pytest.mark.parametrize("filter_string", list(FILTERS))
def test_the_filter_names_in_both_tiers(
    filter_string: str, on: bool, make_app: Any, tmp_path: Path
) -> None:
    """``c.id.ns`` (text), ``c.id.local`` and ``c.in_namespace()`` (by segments) select
    the same needs in the portable tier and in ``eval``; with the switch off every need
    is plain and the names stay defined."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    for name, text in _filter_project(on)["files"]:
        (srcdir / name).write_text(text, "utf-8")
    app = make_app(
        srcdir=srcdir,
        buildername="needs",
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()
    engine, evaluated = _both_tiers(app, filter_string)
    expected = FILTERS[filter_string][0 if on else 1]
    assert engine == expected
    assert evaluated == expected


@pytest.mark.parametrize("test_app", [_filter_project(True)], indirect=True)
def test_a_part_reads_its_needs_facets(test_app: Any) -> None:
    """A part answers with its need's namespace and local id; its ``id`` is its own."""
    app = test_app
    app.build()
    for filter_string, expected in {
        'c.in_namespace("nc::m2")': ["nc::m2::REQ_002", "nc::m2::REQ_002.p1"],
        'c.id.local == "REQ_002"': ["nc::m2::REQ_002", "nc::m2::REQ_002.p1"],
        'id == "p1"': ["nc::m2::REQ_002.p1"],
    }.items():
        assert _both_tiers(app, filter_string, parts=True) == (expected, expected)


@pytest.mark.parametrize(
    "test_app",
    [
        _unclean_project(
            UNCHECKED + 'suppress_warnings = ["needs.id_namespace"]\n',
            FILTER_INDEX + '\n.. needextend:: c.in_namespace("nc")\n   :+tags: x\n',
        )
    ],
    indirect=True,
)
def test_a_needextend_written_without_spaces_extends_the_namespace(
    test_app: Any,
) -> None:
    """``c.in_namespace("nc")`` written as one word is a needextend filter, not an id: it
    extends the needs of ``nc`` and below, and neither the look-alike ``ncx`` nor a
    need in no namespace."""
    app = test_app
    app.build()
    assert build_warnings(app) == []
    extended = sorted(key for key, need in _needs(app).items() if "x" in need["tags"])
    assert extended == ["nc::REQ_001", "nc::m2::REQ_002"]


#: the error of comparing ``c.id`` itself with a value: it holds the facets, not the id
ID_IS_NO_ID = (
    "c.id holds the facets of the id, not the id: compare id, c.id.local or c.id.ns"
)


@pytest.mark.parametrize(
    ("filter_string", "error"),
    [
        (
            'c.in_namespace("")',
            "c.in_namespace('') names no namespace; a need in no namespace is "
            "c.id.ns == ''",
        ),
        ('c.in_namespace("nc::")', "c.in_namespace: 'nc::' is not a namespace"),
        ('c.in_namespace("a b")', "c.in_namespace: 'a b' is not a namespace"),
        ("c.in_namespace(1)", "c.in_namespace takes a namespace as a string, not int"),
        ("c.id.nss", "c.id has no facet 'nss' (did you mean 'ns'?)"),
        ("c.id.local_id", "c.id has no facet 'local_id' (did you mean 'local'?)"),
        (
            'c.in_namespace(namespace="nc")',
            "positional-only arguments passed as keyword",
        ),
        ('c.in_namespace("nc", "m2")', "takes 2 positional arguments but 3 were given"),
        ('c.id == "nc::REQ_001"', ID_IS_NO_ID),
        ('c.id != "nc::REQ_001"', ID_IS_NO_ID),
        ('c.id in ["nc::REQ_001"]', ID_IS_NO_ID),
        ('c.id in {"nc::REQ_001"}', ID_IS_NO_ID),
        ("{c.id: 1} == {}", ID_IS_NO_ID),
        ("len({c.id}) == 1", ID_IS_NO_ID),
        ("c.id == None", ID_IS_NO_ID),
        ("c.id == 1", ID_IS_NO_ID),
        ("c.id in [1]", ID_IS_NO_ID),
    ],
)
def test_an_argument_that_is_no_namespace_is_an_error_of_the_filter(
    filter_string: str, error: str, make_app: Any, tmp_path: Path
) -> None:
    """An empty argument, and a text that is no namespace, never match everything: the
    filter is invalid, in both tiers, with one message; an unknown facet names the
    closest."""
    from unittest.mock import patch

    from sphinx_needs import filter_common
    from sphinx_needs.exceptions import NeedsInvalidFilter
    from sphinx_needs.filter_common import filter_single_need
    from sphinx_needs.ubquery import CompiledFilter

    srcdir = tmp_path / "src"
    srcdir.mkdir()
    for name, text in _filter_project(True)["files"]:
        (srcdir / name).write_text(text, "utf-8")
    app = make_app(
        srcdir=srcdir,
        buildername="needs",
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()
    need = _needs(app)["nc::REQ_001"]
    config = NeedsSphinxConfig(app.config)
    messages = []
    with pytest.raises(NeedsInvalidFilter) as parsed:
        filter_single_need(need, config, filter_string)
    messages.append(str(parsed.value))
    refused = CompiledFilter(None, "refused", False)
    with (
        patch.object(filter_common, "compile_portable", lambda _: refused),
        pytest.raises(NeedsInvalidFilter) as evaluated,
    ):
        filter_single_need(need, config, filter_string)
    messages.append(str(evaluated.value))
    assert messages[0] == messages[1]
    assert error in messages[0]


@pytest.mark.parametrize("test_app", [_filter_project(True)], indirect=True)
def test_the_text_of_c_id_stays_printable(test_app: Any) -> None:
    """``str(c.id)`` and ``f"{c.id}"`` are text for messages: not the id, and not an
    error. A filter comparing that text is answered, and it matches no id."""
    from sphinx_needs.filter_common import filter_single_need

    app = test_app
    app.build()
    need = _needs(app)["nc::REQ_001"]
    config = NeedsSphinxConfig(app.config)
    for filter_string in ('str(c.id) == "nc::REQ_001"', 'f"{c.id}" == "nc::REQ_001"'):
        assert filter_single_need(need, config, filter_string) is False


@pytest.mark.parametrize(
    ("filter_string", "tier"),
    [
        ('c.in_namespace("nc")', ("fast", None)),
        ('c.in_namespace("")', ("fast", None)),
        ('c.id.ns == "nc"', ("fast", None)),
        ('c.id.local.startswith("REQ")', ("fast", None)),
        ("c.in_namespace(nsv)", ("eval", "call:c.in_namespace")),
        ('c.in_namespace("a", "b")', ("eval", "call:c.in_namespace")),
        ('c.in_namespace("nc", x=1)', ("eval", "call:c.in_namespace")),
        ('c.in_namespace(namespace="nc")', ("eval", "call:c.in_namespace")),
        ("c.id.nss", ("eval", "attribute:c")),
        ("c.id", ("eval", "attribute:c")),
        ('c.id == "nc::REQ_001"', ("eval", "attribute:c")),
    ],
)
def test_the_tier_of_each(filter_string: str, tier: tuple[str, Any]) -> None:
    """One string literal argument is compiled, as ``c.is_a``; anything else is
    answered by ``eval``."""
    from sphinx_needs.filter_common import _filter_tier

    assert _filter_tier(filter_string) == tier


#: ``parse_namespace``'s refusal, as ``c.in_namespace`` reports it
NO_NAMESPACE = (
    "c.in_namespace: {text!r} is not a namespace: its piece {piece!r} is not a "
    "segment, which is one or more ASCII letters, ASCII digits, '_' or '-'"
)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ('c.id.ns == "nc"', None),
        ('c.id.local == "REQ_1"', None),
        ('c.in_namespace("nc")', None),
        (
            "c.in_namespace(status)",
            "calls 'c.in_namespace', which a declared rule cannot read",
        ),
        ("c.id.nope", "calls 'c.id', which a declared rule cannot read"),
        ("c.id", "calls 'c.id', which a declared rule cannot read"),
        (
            'c.in_namespace("nc", x=1)',
            "calls 'c.in_namespace', which a declared rule cannot read",
        ),
        (
            'c.in_namespace("a", "b")',
            "calls 'c.in_namespace', which a declared rule cannot read",
        ),
        (
            'c.in_namespace("")',
            "c.in_namespace('') names no namespace; a need in no namespace is "
            "c.id.ns == ''",
        ),
        ('c.in_namespace("a b")', NO_NAMESPACE.format(text="a b", piece="a b")),
        ('c.in_namespace("nc::")', NO_NAMESPACE.format(text="nc::", piece="")),
    ],
)
def test_a_declared_rule_reads_them(text: str, problem: str | None) -> None:
    """A derived field's ``where`` admits the facets and ``c.in_namespace`` with one
    string literal naming a namespace, as it admits ``c.source`` and ``c.is_a``; an
    empty literal, or one that is no namespace, is the rule's problem, as it is an
    error of every other filter."""
    from sphinx_needs.derive import filter_problem

    assert filter_problem(text) == problem


@pytest.mark.parametrize(
    "filter_string",
    ['c.id.ns == "nc"', 'c.id.local == "x"', 'c.in_namespace("nc")'],
)
def test_they_read_the_id_not_the_document(filter_string: str) -> None:
    """The order of the dynamic functions sees them read ``id``, which never changes
    after creation, and not ``docname`` (what any other use of ``c`` reads)."""
    from sphinx_needs.functions.order import filter_names

    assert filter_names(filter_string).names == frozenset({"id"})


@pytest.mark.parametrize(
    ("expression", "said"),
    [
        ('c.id.ns == "nc"', "the c.id facets are not available in a needimport filter"),
        (
            'c.in_namespace("nc")',
            "c.in_namespace() is not available in a needimport filter",
        ),
    ],
)
def test_where_there_is_no_check_context_it_says_so(
    expression: str, said: str, make_app: Any, tmp_path: Path
) -> None:
    """A needimport filter reads the imported record: it has no check context, and says
    so, as for the source facets."""
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(UNCHECKED, "utf-8")
    (srcdir / "index.rst").write_text(
        f"Index\n=====\n\n.. needimport:: imp.json\n   :filter: {expression}\n", "utf-8"
    )
    (srcdir / "imp.json").write_text(_record_file("nc::IMP_1"), "utf-8")
    app = make_app(
        srcdir=srcdir,
        buildername="needs",
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
    )
    app.build()
    (warning,) = [w for w in build_warnings(app) if "[needs.needimport]" in w]
    assert "name 'c' is not defined; " + said in warning


# --- did-you-mean hints on a dead link and a :need: role naming no need ---

HINT_INDEX = """\
Index
=====

.. req:: Target
   :id: nc::REQ_002

   A part :np:`(p1) of it`.

.. req:: Two candidates, one
   :id: nc::REQ_003

.. req:: Two candidates, two
   :id: sup::REQ_003

.. req:: Linking
   :id: SRC_001
   :links: REQ_002, REQ_002.p1, REQ_003, REQ_009, other::REQ_002

:need:`REQ_002` :need:`REQ_002.p1` :need:`REQ_003` :need:`REQ_009`

.. req:: A target with one part
   :id: nc::REQ_010

   A part :np:`(p1) of it`.

.. req:: A plain need, with a part
   :id: REQ_011

   A part :np:`(p1) of it`.

.. req:: Its namesake in a namespace
   :id: nc::REQ_011

   A part :np:`(p9) of it`.

.. req:: Linking to parts
   :id: SRC_002
   :links: REQ_010.p1, REQ_010.p2, REQ_011.p9

:need:`REQ_010.p1` :need:`REQ_010.p2` :need:`REQ_011.p9`

.. req:: Two candidates, the one with the part
   :id: nc::REQ_012

   A part :np:`(p1) of it`.

.. req:: Two candidates, the one without
   :id: sup::REQ_012

.. req:: Linking to a part one of two candidates has
   :id: SRC_003
   :links: REQ_012.p1
"""

#: an external need whose link is dead in this project
HINT_EXTERNAL = json.dumps(
    {
        "current_version": "1.0",
        "versions": {
            "1.0": {
                "needs": {
                    "EXT_001": {
                        "id": "EXT_001",
                        "type": "req",
                        "title": "External",
                        "content": "",
                        "docname": "page",
                        "links": ["REQ_002"],
                    }
                }
            }
        },
    }
)

HINT_CONF = (
    UNCHECKED
    + "needs_external_needs = [{'base_url': 'http://x', 'json_path': 'ext.json'}]\n"
)


def _hint_project(conf: str = HINT_CONF) -> dict[str, Any]:
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), HINT_INDEX),
            (Path("ext.json"), HINT_EXTERNAL),
        ],
    }


def _dead(target: str, hint: str = "", source: str = "SRC_001", line: int = 15) -> str:
    return (
        f"<srcdir>/index.rst:{line}: WARNING: Need {source!r} has unknown outgoing "
        f"link {target!r} in field 'links'{hint} [needs.link_outgoing]"
    )


def _role(target: str, hint: str = "", line: int = 19, part: bool = False) -> str:
    what = "need part" if part else "need"
    return (
        f"<srcdir>/index.rst:{line}: WARNING: linked {what} {target} not found{hint} "
        "[needs.link_ref]"
    )


def _external(hint: str = "") -> str:
    return (
        "WARNING: http://x/page.html#EXT_001: Need 'EXT_001' has unknown outgoing "
        f"link 'REQ_002' in field 'links'{hint} [needs.external_link_outgoing]"
    )


def _mean(target: str) -> str:
    return f" (did you mean {target!r}?)"


@pytest.mark.parametrize("test_app", [_hint_project()], indirect=True)
def test_a_dead_target_one_need_has_as_its_local_id_is_hinted(test_app: Any) -> None:
    """A dead link (an external need's too) or a :need: role naming a bare id that no
    need has, and exactly one need has as its local id in a namespace, says which,
    with the part re-attached where that need has the part. With no candidate, two, a
    target that holds a namespace itself, a part the candidate lacks, or an id that
    names a need (a dead part of it), the message is as before; so is it with two
    candidates of which one has the part (the candidates are counted first). (A role to a missing
    part of an existing need is "linked need part ... not found", never hinted.)"""
    app = test_app
    app.build()
    assert sorted(build_warnings(app)) == sorted(
        [
            _dead("REQ_002", _mean("nc::REQ_002")),
            _dead("REQ_002.p1", _mean("nc::REQ_002.p1")),
            _dead("REQ_003"),
            _dead("REQ_009"),
            _dead("other::REQ_002"),
            _role("REQ_002", _mean("nc::REQ_002")),
            _role("REQ_002.p1", _mean("nc::REQ_002.p1")),
            _role("REQ_003"),
            _role("REQ_009"),
            _dead("REQ_010.p1", _mean("nc::REQ_010.p1"), "SRC_002", 36),
            _dead("REQ_010.p2", "", "SRC_002", 36),
            _dead("REQ_011.p9", "", "SRC_002", 36),
            _role("REQ_010.p1", _mean("nc::REQ_010.p1"), 40),
            _role("REQ_010.p2", "", 40),
            _role("REQ_011.p9", "", 40, part=True),
            _dead("REQ_012.p1", "", "SRC_003", 50),
            _external(_mean("nc::REQ_002")),
        ]
    )
    # nothing changes in what resolves: the links are as written, every one dead
    needs = _needs(app)
    assert sorted(needs["SRC_001"]["links"]) == sorted(
        ["REQ_002", "REQ_002.p1", "REQ_003", "REQ_009", "other::REQ_002"]
    )
    assert needs["nc::REQ_002"]["links_back"] == []


@pytest.mark.parametrize(
    "test_app",
    [_hint_project(HINT_CONF + "needs_namespaced_ids = False\n")],
    indirect=True,
)
def test_no_hint_switched_off(test_app: Any) -> None:
    """With the switch off no need is in a namespace: no hint."""
    app = test_app
    app.build()
    assert sorted(build_warnings(app)) == sorted(
        [
            *(
                _dead(t)
                for t in [
                    "REQ_002",
                    "REQ_002.p1",
                    "REQ_003",
                    "REQ_009",
                    "other::REQ_002",
                ]
            ),
            *(_role(t) for t in ["REQ_002", "REQ_002.p1", "REQ_003", "REQ_009"]),
            *(_dead(t, "", "SRC_002", 36) for t in ["REQ_010.p1", "REQ_010.p2"]),
            _dead("REQ_011.p9", "", "SRC_002", 36),
            *(_role(t, "", 40) for t in ["REQ_010.p1", "REQ_010.p2"]),
            _role("REQ_011.p9", "", 40, part=True),
            _dead("REQ_012.p1", "", "SRC_003", 50),
            _external(),
        ]
    )


def test_the_hint_index_is_built_once_and_only_when_needed() -> None:
    """The index of local ids is built when the first dead target is met, once; never
    for a target holding a namespace itself, nor for an id that names a need."""
    from collections.abc import Iterator, Mapping

    from sphinx_needs._namespaced_ids import LocalIdHints

    class _Need(dict[str, Any]):
        def __init__(self, segments: tuple[str, ...], local: str, *parts: str) -> None:
            super().__init__(parts={part: {} for part in parts})
            self.id_ns_segments, self.id_local = segments, local

    class _Counting(Mapping[str, Any]):
        walks = 0
        _data = {
            "nc::REQ_2": _Need(("nc",), "REQ_2", "p1"),
            "REQ_3": _Need((), "REQ_3"),
        }

        def __getitem__(self, key: str) -> Any:
            return self._data[key]

        def __iter__(self) -> Iterator[str]:
            type(self).walks += 1
            return iter(self._data)

        def __len__(self) -> int:
            return len(self._data)

    hints = LocalIdHints(_Counting())
    assert hints.hint("x::REQ_2") == ""
    assert hints.hint("REQ_3", "p1") == ""
    assert _Counting.walks == 0
    assert hints.hint("REQ_2") == " (did you mean 'nc::REQ_2'?)"
    assert hints.hint("REQ_2", "p1") == " (did you mean 'nc::REQ_2.p1'?)"
    assert hints.hint("REQ_2", "p2") == ""
    assert hints.hint("REQ_4") == ""
    assert _Counting.walks == 1


@pytest.mark.parametrize("test_app", [_hint_project()], indirect=True)
def test_the_links_and_the_roles_share_one_index(test_app: Any) -> None:
    """The dead links (post-processing) and the roles (writing) of a build read one
    index."""
    from sphinx_needs import _namespaced_ids

    built = []
    real = _namespaced_ids.LocalIdHints.hint

    def counting(self: Any, need_id: str, part: str | None = None) -> str:
        if self._index is None:
            built.append(need_id)
        return real(self, need_id, part)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(_namespaced_ids.LocalIdHints, "hint", counting)
        test_app.build()
    assert len(built) == 1


DERIVE_TOML = """\
[needs.fields.n_all]
schema = { type = "integer" }
derive = { kind = "count", over = "links", where = 'c.in_namespace("nc")' }
""" + "".join(
    f"""
[needs.fields.{name}]
schema = {{ type = "integer" }}
derive = {{ kind = "count", over = "links", where = 'c.in_namespace("{text}")' }}
"""
    for name, text in [("n_empty", ""), ("n_bad", "a b"), ("n_trail", "nc::")]
)

DERIVE_INDEX = """\
Index
=====

.. req:: Linked one
   :id: nc::A_1

.. req:: Linked two
   :id: nc::m2::B_1

.. req:: Linked three
   :id: x::C_1

.. req:: Host
   :id: HOST_1
   :links: nc::A_1, nc::m2::B_1, x::C_1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    UNCHECKED + 'needs_from_toml = "ubproject.toml"\n',
                ),
                (Path("ubproject.toml"), DERIVE_TOML),
                (Path("index.rst"), DERIVE_INDEX),
            ],
        }
    ],
    indirect=True,
)
def test_a_derived_rule_naming_no_namespace_is_reported(test_app: Any) -> None:
    """A derived field's ``where`` naming no namespace is reported as an invalid rule
    (``needs.derive_invalid``), never a count of nothing; a valid one counts."""
    app = test_app
    app.build()
    warnings = build_warnings(app)
    for name in ("n_empty", "n_bad", "n_trail"):
        (warning,) = [w for w in warnings if f"field {name!r}" in w]
        assert warning.endswith("[needs.derive_invalid]"), warning
        assert "c.in_namespace" in warning, warning
    assert len(warnings) == 3, warnings
    assert _needs(app)["HOST_1"]["n_all"] == 2


@pytest.mark.parametrize("test_app", [_filter_project(True)], indirect=True)
def test_comparing_c_id_itself_is_an_invalid_filter(test_app: Any) -> None:
    """``c.id`` holds the facets of the id: compared with a value it is an invalid
    filter, reported by the engine over needs and over parts, never "no need"."""
    from sphinx_needs.filter_common import filter_needs_parts, filter_needs_view

    app = test_app
    app.build()
    view = _needs(app)
    config = NeedsSphinxConfig(app.config)
    stream = app._warning
    for filter_string in ('c.id == "nc::REQ_001"', 'c.id in ["nc::REQ_001"]'):
        for parts in (False, True):
            start = len(stream.getvalue())
            if parts:
                found = filter_needs_parts(
                    view.to_list_with_parts(), config, filter_string
                )
            else:
                found = filter_needs_view(view, config, filter_string)
            assert list(found) == []
            reported = build_warnings(stream.getvalue()[start:], srcdir=app.srcdir)
            assert len(reported) == 1, reported
            assert reported[0].endswith("[needs.filter]"), reported
            assert ID_IS_NO_ID in reported[0], reported


@pytest.mark.parametrize("parallel", [0, 2], ids=["serial", "parallel"])
def test_the_hint_index_is_one_builds_and_never_pickled(
    parallel: int, make_app: Any, tmp_path: Path
) -> None:
    """One application building twice (a server rebuilding on change): the hint index
    is kept on the application, never in the pickled environment, and each build has
    its own (a second candidate added before build 2 ends the hint there)."""
    if parallel and not parallel_available:
        pytest.skip("this platform reads in one process")
    from sphinx_needs._namespaced_ids import LocalIdHints

    srcdir = tmp_path / "src"
    srcdir.mkdir()
    (srcdir / "conf.py").write_text(UNCHECKED, "utf-8")
    pages = [f"page{i}" for i in range(6)]
    for page in pages:
        (srcdir / f"{page}.rst").write_text(f"{page}\n{'=' * len(page)}\n", "utf-8")
    (srcdir / "index.rst").write_text(
        "Index\n=====\n\n.. req:: Target\n   :id: nc::REQ_002\n\n"
        ".. req:: Linking\n   :id: SRC_001\n   :links: REQ_002\n\n"
        ".. toctree::\n\n   " + "\n   ".join(pages) + "\n",
        "utf-8",
    )
    app = make_app(
        "html",
        srcdir=srcdir,
        freshenv=True,
        status=io.StringIO(),
        warning=io.StringIO(),
        parallel=parallel,
    )
    pickled = Path(app.doctreedir) / "environment.pickle"
    hinted = "(did you mean 'nc::REQ_002'?)"

    app.build()
    assert any(hinted in w for w in build_warnings(app))
    # a second candidate: build 2 offers no hint
    (srcdir / "page0.rst").write_text(
        "page0\n=====\n\n.. req:: A namesake\n   :id: sup::REQ_002\n", "utf-8"
    )
    start = len(app._warning.getvalue())
    app.build()
    second = build_warnings(app._warning.getvalue()[start:], srcdir=app.srcdir)
    assert [w for w in second if "REQ_002" in w and "unknown outgoing" in w] == [
        "<srcdir>/index.rst:7: WARNING: Need 'SRC_001' has unknown outgoing link "
        "'REQ_002' in field 'links' [needs.link_outgoing]"
    ]
    data = pickled.read_bytes()
    assert b"LocalIdHints" not in data
    assert b"LocalIdHints" in pickle.dumps(LocalIdHints({}))  # the control
    env = pickle.loads(data)
    assert not hasattr(env, "_needs_local_id_hints")


DEFAULT_INDEX = """\
Index
=====

.. req:: One segment
   :id: SUPPLIER::REQ_1

.. req:: Not split cleanly
   :id: SUPPLIER::::REQ_4

.. req:: Refused by the default pattern, read whole
   :id: nc::REQ_00001

.. req:: Linking
   :id: SRC_00001
   :links: REQ_1
"""


@pytest.mark.parametrize(
    "test_app",
    [
        {
            **_unclean_project('extensions = ["sphinx_needs"]\n', DEFAULT_INDEX),
            "buildername": "html",
        }
    ],
    indirect=True,
)
def test_off_by_default(test_app: Any) -> None:
    """A project that sets nothing reads every id as plain (until 10.0, whose default
    is on): no namespace is stored or filtered on, an id that does not split cleanly is
    not reported, a pattern sees the whole id, and no hint is offered."""
    from sphinx_needs.filter_common import filter_needs_view

    app = test_app
    app.build()
    # read before the view: reading it after the build post-processes the needs again
    assert build_warnings(app) == [
        _refused("nc::REQ_00001", 10, None, DEFAULT),
        _dead("REQ_1", "", "SRC_00001", 13),
    ]
    config = NeedsSphinxConfig(app.config)
    assert config.namespaced_ids is False
    needs = _needs(app)
    assert sorted(needs) == ["SRC_00001", "SUPPLIER::::REQ_4", "SUPPLIER::REQ_1"]
    for key, need in needs.items():
        assert (need.id_ns, need.id_ns_segments, need.id_local) == ("", (), key)
    assert list(filter_needs_view(needs, config, 'c.in_namespace("SUPPLIER")')) == []
