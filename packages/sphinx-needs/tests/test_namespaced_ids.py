"""Namespaced ids: what the conformance corpus cannot state.

``tests/test_namespace_conformance.py`` holds the rules both tools share. Here: the
``NeedItem`` slots and their survival across a pickled environment, generated ids,
``needextract``'s id argument, every configuration route to a reserved name, the marker of
a ``needs_file`` history and of the per-id files, and needsequence's participant names.
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsConfigException
from sphinx_needs.need_item import NeedItem, NeedItemSourceUnknown, NeedsContent
from sphinx_needs_testkit import assert_no_warnings, build_warnings

CONF = """\
extensions = ["sphinx_needs"]
needs_build_json = True
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
]
show_warning_types = True
"""


def project(index: str, *, conf: str = CONF, **params: Any) -> dict[str, Any]:
    """The ``test_app`` parameters of a one-page project."""
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Index\n=====\n\n" + index),
        ],
        **params,
    }


def on(**overrides: Any) -> dict[str, Any]:
    return {"needs_namespaced_ids": True, **overrides}


def split_of(app: SphinxTestApp) -> dict[str, tuple[tuple[str, ...], str]]:
    return {
        need_id: (need.ns, need.local_id)
        for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
    }


# --- NeedItem -------------------------------------------------------------------------


def _need_item(need_id: str, **kwargs: Any) -> NeedItem:
    core: Any = {
        "id": need_id,
        "type": "req",
        "type_name": "Requirement",
        "type_prefix": "R_",
        "type_color": "",
        "type_style": "node",
        "title": "t",
        "status": None,
        "tags": [],
        "constraints": [],
        "collapse": False,
        "hide": False,
        "style": None,
        "layout": None,
        "external_css": "external_link",
        "arch": {},
        "has_dead_links": False,
        "has_forbidden_dead_links": False,
        "sections": (),
        "signature": None,
    }
    return NeedItem(
        core=core,
        extras={},
        links={},
        source=NeedItemSourceUnknown(),
        content=NeedsContent(doctype=".rst", content=""),
        **kwargs,
    )


def test_a_need_item_without_a_split_is_its_own_local_id() -> None:
    need = _need_item("nc::REQ_001")
    assert (need.ns, need.local_id) == ((), "nc::REQ_001")


def test_a_need_item_keeps_its_split_through_a_copy_and_a_pickle() -> None:
    need = _need_item("nc::tc::REQ_001", ns=("nc", "tc"), local_id="REQ_001")
    for again in (need.copy(), pickle.loads(pickle.dumps(need))):
        assert (again.ns, again.local_id) == (("nc", "tc"), "REQ_001")


@pytest.mark.parametrize(
    ("ns", "local_id"),
    [(("nc",), "REQ_002"), (("nd",), "REQ_001"), ((), "REQ_001"), (("nc",), None)],
)
def test_a_need_item_refuses_a_split_that_does_not_join_to_its_id(
    ns: tuple[str, ...], local_id: str | None
) -> None:
    with pytest.raises(ValueError, match="do not join to its id"):
        _need_item("nc::REQ_001", ns=ns, local_id=local_id)


@pytest.mark.parametrize(
    "test_app",
    [project(".. req:: A\n   :id: nc::REQ_001\n", confoverrides=on())],
    indirect=True,
)
def test_the_split_survives_an_incremental_build(test_app: SphinxTestApp) -> None:
    app = test_app
    app.build()
    assert split_of(app) == {"nc::REQ_001": (("nc",), "REQ_001")}
    # a second build reads nothing again: the needs come from the pickled environment
    app2 = SphinxTestApp(
        "html", srcdir=app.srcdir, confoverrides=on(), status=None, warning=None
    )
    try:
        app2.build()
        assert "0 added, 0 changed, 0 removed" in app2._status.getvalue()
        assert split_of(app2) == {"nc::REQ_001": (("nc",), "REQ_001")}
    finally:
        app2.cleanup()


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            ".. req:: A\n   :id: nc::REQ_001\n", confoverrides={"needs_id_regex": ""}
        )
    ],
    indirect=True,
)
def test_turning_the_switch_on_reads_every_document_again(
    test_app: SphinxTestApp,
) -> None:
    """The switch is an ``env`` value: the stored split follows it on the next build."""
    app = test_app
    app.build()
    assert split_of(app) == {"nc::REQ_001": ((), "nc::REQ_001")}
    app2 = SphinxTestApp(
        "html",
        srcdir=app.srcdir,
        confoverrides=on(needs_id_regex=""),
        status=None,
        warning=None,
    )
    try:
        app2.build()
        assert split_of(app2) == {"nc::REQ_001": (("nc",), "REQ_001")}
    finally:
        app2.cleanup()


# --- generated ids ------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            ".. req:: Generated\n\n.. spec:: Generated in a namespace\n",
            conf=CONF.replace(
                'style="node"),\n]',
                'style="node"),\n    dict(directive="spec", title="Spec", prefix="nc::S_"),\n]',
            ),
            confoverrides=on(),
        )
    ],
    indirect=True,
)
def test_a_generated_id_is_split_as_written(test_app: SphinxTestApp) -> None:
    """No namespace is added to a generated id; a type prefix holding ``::`` is split
    like any other id, and the regex is applied to the local id."""
    app = test_app
    app.build()
    assert_no_warnings(app)
    splits = sorted(split_of(app).values())
    assert [ns for ns, _ in splits] == [(), ("nc",)]
    assert all(local.startswith(("R_", "S_")) for _, local in splits)


# --- needextract --------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            ".. req:: Extracted\n   :id: nc::REQ_001\n\n"
            ".. needextract:: nc::REQ_001\n\n"
            ".. needextract:: nc::REQ_404\n",
            confoverrides=on(),
        )
    ],
    indirect=True,
)
def test_needextract_takes_a_namespaced_argument_as_an_id(
    test_app: SphinxTestApp,
) -> None:
    """With the switch on, an argument whose local id matches ``needs_id_regex`` is an
    id: an existing one is extracted, a missing one is reported, not taken as a filter."""
    app = test_app
    app.build()
    assert build_warnings(app) == [
        "<srcdir>/index.rst:9: WARNING: Requested need 'nc::REQ_404' not found. "
        "[needs.needextract]"
    ]
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert html.count("Extracted") >= 2


# --- reserved names -----------------------------------------------------------------

ROUTES = {
    "needs_fields": "needs_fields = {NAME: {'schema': {'type': 'string'}}}",
    "needs_extra_options": "needs_extra_options = [NAME]",
    "needs_links": "needs_links = {NAME: {}}",
    "needs_extra_links": "needs_extra_links = [{'option': NAME}]",
    "a type's fields": "needs_types[0]['fields'] = {NAME: {'schema': {'type': 'string'}}}",
    "a type's links": "needs_types[0]['links'] = {NAME: {}}",
}


def _write(srcdir: Path, conf: str) -> None:
    srcdir.mkdir(parents=True)
    (srcdir / "conf.py").write_text(conf, encoding="utf-8")
    (srcdir / "index.rst").write_text("Index\n=====\n", encoding="utf-8")


@pytest.mark.parametrize("name", ["ns", "local_id"])
@pytest.mark.parametrize("route", list(ROUTES))
def test_a_reserved_name_is_refused_on_every_route(
    make_app: Any, tmp_path: Path, route: str, name: str
) -> None:
    srcdir = tmp_path / "src"
    _write(
        srcdir,
        CONF
        + "needs_namespaced_ids = True\n"
        + ROUTES[route].replace("NAME", repr(name)),
    )
    with pytest.raises(NeedsConfigException) as exc_info:
        make_app("needs", srcdir=srcdir)
    assert str(exc_info.value) == (
        f"Field {name!r} is reserved while needs_namespaced_ids is on: it is the "
        "need's namespace or local id. Please use another name in your config."
    )


@pytest.mark.parametrize("name", ["ns", "local_id"])
@pytest.mark.parametrize("route", list(ROUTES))
def test_a_reserved_name_is_an_ordinary_name_with_the_switch_off(
    make_app: Any, tmp_path: Path, route: str, name: str
) -> None:
    srcdir = tmp_path / "src"
    _write(srcdir, CONF + ROUTES[route].replace("NAME", repr(name)))
    app = make_app("needs", srcdir=srcdir)
    app.build()
    schema = SphinxNeedsData(app.env).get_schema()
    assert name in {*schema.iter_extra_field_names(), *schema.iter_link_field_names()}


# --- the marker ----------------------------------------------------------------------

PREVIOUS = json.dumps(
    {
        "current_version": "1.0",
        "project": "p",
        "versions": {
            "1.0": {"needs": {"OLD_001": {"id": "OLD_001", "title": "old"}}},
        },
    }
)


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "files": [
                (
                    Path("conf.py"),
                    CONF + 'version = "2.0"\nneeds_file = "previous.json"\n',
                ),
                (Path("previous.json"), PREVIOUS),
                (
                    Path("index.rst"),
                    "Index\n=====\n\n.. req:: A\n   :id: nc::REQ_001\n",
                ),
            ],
            "confoverrides": on(),
        }
    ],
    indirect=True,
)
def test_a_needs_file_history_keeps_its_earlier_versions_unmarked(
    test_app: SphinxTestApp,
) -> None:
    app = test_app
    app.build()
    data = json.loads(Path(app.outdir, "needs.json").read_text(encoding="utf-8"))
    assert data["versions"]["1.0"] == {
        "needs": {"OLD_001": {"id": "OLD_001", "title": "old"}}
    }
    assert data["versions"]["2.0"]["namespaced_ids"] is True


@pytest.mark.parametrize(
    "test_app",
    [
        project(
            ".. req:: A\n   :id: nc::REQ_001\n",
            confoverrides=on(needs_build_json_per_id=True),
        )
    ],
    indirect=True,
)
def test_the_per_id_files_are_marked(test_app: SphinxTestApp) -> None:
    app = test_app
    app.build()
    data = json.loads(
        Path(app.outdir, "needs_id", "nc::REQ_001.json").read_text(encoding="utf-8")
    )
    assert data["versions"][data["current_version"]]["namespaced_ids"] is True


# --- needsequence ---------------------------------------------------------------------

SEQUENCE_CONF = """\
extensions = ["sphinx_needs", "sphinxcontrib.plantuml"]
plantuml_output_format = "svg"
needs_id_regex = ""
needs_types = [
    dict(directive="req", title="Requirement", prefix="R_", color="#BFD8D2", style="node"),
]
"""

SEQUENCE = """\
.. req:: Sender
   :id: nc::A-1
   :links: nc::M_1

.. req:: The message
   :id: nc::M_1
   :links: nc::B_1

.. req:: Receiver
   :id: nc::B_1

.. needsequence::
   :start: nc::A-1
"""


@pytest.mark.parametrize(
    "test_app",
    [project(SEQUENCE, conf=SEQUENCE_CONF, plantuml=True)],
    indirect=True,
)
def test_needsequence_names_its_participants_as_needflow_does(
    test_app: SphinxTestApp,
) -> None:
    """A need id is not a PlantUML name: the aliases go through needflow's entity map,
    so an id with ``::`` or ``-`` renders."""
    app = test_app
    sources: list[str] = []
    from sphinxcontrib.plantuml import plantuml

    def collect(app_: Any, doctree: Any, docname: str) -> None:
        sources.extend(node["uml"] for node in doctree.findall(plantuml))

    app.connect("doctree-resolved", collect, priority=900)
    app.build()
    assert_no_warnings(app)
    (uml,) = sources
    assert 'participant "Sender" as nc__A_1\n' in uml
    assert "nc__A_1 -> nc__B_1: The message\n" in uml
    html = Path(app.outdir, "index.html").read_text(encoding="utf-8")
    assert "Syntax Error" not in html
    assert len(list(Path(app.outdir, "_images").glob("*.svg"))) == 1
