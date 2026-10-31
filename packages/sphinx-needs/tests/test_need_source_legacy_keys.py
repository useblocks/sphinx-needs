"""The legacy location keys of every need, as sphinx-needs gave them before its source
classes became one.

A need's location keys (``docname``, ``lineno``, ``lineno_content``, ``is_import``,
``is_external``, ``external_url``) are its source's ``dict_repr``, and its items carry
them. These snapshots were generated on ``8bd37988a``, where five ``NeedItemSource*``
classes computed them, and committed before the classes changed: they hold the values
any rewrite of the sources has to keep, byte for byte, for

- every need of the source hops project, which exercises each producer of this
  repository (``doc_test/doc_need_source_hops``), and
- every way an extension gives a need its location through the API: each call shape of
  ``add_need``, ``ingest_need_record``, ``add_external_need``, ``create_need`` and
  ``generate_need``, and each of the five names constructed with its 9.1.0 keywords
  (``doc_test/doc_need_source_shapes``).

The hops of these needs are pinned by ``test_need_source.py``; here only what a filter, a
table or ``needs.json`` reads.

One change since, deliberate: the four needs written in an include's slice
(``REQ_STARTAFTERX``, ``REQ_STARTLINEX``, ``REQ_HIT_A``, ``REQ_X_TWIN``) record the line
they are written on in their files as ``lineno``, where the five classes gave the line in
the slice (#2428).

The last test is the upgrade path: an environment the five classes pickled is not read
back into the new class, whatever their names now resolve to.
"""

from __future__ import annotations

import ast
import copyreg
import io
import pickle
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp
from syrupy.assertion import SnapshotAssertion

from sphinx_needs import data, need_item
from sphinx_needs._need_source import first_line
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.need_item import NeedItem
from sphinx_needs_testkit import assert_no_warnings

HOPS_PROJECT = Path(__file__).parent / "doc_test" / "doc_need_source_hops"
SHAPES_PROJECT = Path(__file__).parent / "doc_test" / "doc_need_source_shapes"


def _keys(need: NeedItem) -> dict[str, Any]:
    """What these snapshots hold of a need: its source's ``dict_repr``, and its items."""
    return {"dict_repr": dict(need.source.dict_repr), "items": dict(need.items())}


def _all_keys(app: SphinxTestApp) -> dict[str, dict[str, Any]]:
    return {
        need_id: _keys(need)
        for need_id, need in sorted(SphinxNeedsData(app.env).get_needs_view().items())
    }


def _hops_project(tmp_path: Path) -> Path:
    """A copy of the source hops project; its source directory."""
    shutil.copytree(HOPS_PROJECT, tmp_path / "project")
    return tmp_path / "project" / "docs"


def test_every_need_of_each_producer_keeps_its_legacy_keys(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, snapshot: SnapshotAssertion
):
    """The need directive (pages, includes, MyST, autodoc), ``list2need``,
    ``needservice``, ``needimport``, ``needs_external_needs`` and ``add_need``."""
    app = make_app("html", srcdir=_hops_project(tmp_path), freshenv=True)
    try:
        app.build()
        assert_no_warnings(app)
        assert _all_keys(app) == snapshot
    finally:
        app.cleanup()


def test_every_call_shape_of_the_api_keeps_its_legacy_keys(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, snapshot: SnapshotAssertion
):
    """Each way an extension written against 9.1.0 gives a need its location."""
    shutil.copytree(SHAPES_PROJECT, tmp_path / "project")
    app = make_app("html", srcdir=tmp_path / "project", freshenv=True)
    try:
        app.build()
        assert_no_warnings(app)
        created = _all_keys(app)
        assert sorted(created) == sorted([*SHAPE_IDS_ADDED, *SHAPE_IDS_EXTERNAL]), (
            "every shape created its need"
        )
        assert created == snapshot(name="created")
        generated = {
            need_id: _keys(need)
            for need_id, need in sorted(app.source_shapes_generated.items())
        }
        assert sorted(generated) == sorted(SHAPE_IDS_GENERATED)
        assert generated == snapshot(name="generated")
    finally:
        app.cleanup()


SHAPE_IDS_ADDED = (
    "SHAPE_ADD_POSITIONAL",
    "SHAPE_ADD_KEYWORDS",
    "SHAPE_ADD_NO_LOCATION",
    "SHAPE_ADD_DOCNAME_ONLY",
    "SHAPE_ADD_LINENO_ONLY",
    "SHAPE_ADD_IS_IMPORT",
    "SHAPE_ADD_URL_NOT_EXTERNAL",
    "SHAPE_ADD_SRC_UNKNOWN",
    "SHAPE_ADD_SRC_UNKNOWN_FULL",
    "SHAPE_ADD_SRC_UNKNOWN_HOPS",
    "SHAPE_ADD_SRC_UNKNOWN_EMPTY",
    "SHAPE_ADD_SRC_DIRECTIVE",
    "SHAPE_ADD_SRC_DIRECTIVE_HOPS",
    "SHAPE_ADD_SRC_DIRECTIVE_UNLINED",
    "SHAPE_ADD_SRC_SERVICE",
    "SHAPE_ADD_SRC_SERVICE_HOPS",
    "SHAPE_ADD_SRC_IMPORT",
    "SHAPE_ADD_SRC_IMPORT_HOPS",
    "SHAPE_ADD_SRC_PROTOCOL",
    "SHAPE_ADD_SRC_AND_KEYWORDS",
    "SHAPE_REC_UNKNOWN",
    "SHAPE_REC_DIRECTIVE",
    "SHAPE_REC_SERVICE",
    "SHAPE_REC_IMPORT",
    "SHAPE_REC_IMPORT_HOPS",
    "SHAPE_CREATE_UNKNOWN",
)
"""The needs ``source-shapes`` places on its page."""

SHAPE_IDS_EXTERNAL = (
    "SHAPE_ADD_IS_EXTERNAL",
    "SHAPE_ADD_IS_EXTERNAL_NO_URL",
    "SHAPE_ADD_IS_EXTERNAL_PLACED",
    "SHAPE_ADD_SRC_EXTERNAL",
    "SHAPE_ADD_SRC_EXTERNAL_HOPS",
    "SHAPE_EXT_URL",
    "SHAPE_EXT_NO_URL",
    "SHAPE_EXT_IS_IMPORT",
    "SHAPE_EXT_LINENO_CONTENT",
    "SHAPE_EXT_SRC_EXTERNAL",
    "SHAPE_EXT_SRC_UNKNOWN",
    "SHAPE_CREATE_EXTERNAL",
)
"""The external needs it creates."""

SHAPE_IDS_GENERATED = (
    "SHAPE_GEN_LOCATION",
    "SHAPE_GEN_NO_LOCATION",
    "SHAPE_GEN_IS_EXTERNAL",
    "SHAPE_GEN_IS_IMPORT",
    "SHAPE_GEN_SRC_SERVICE",
)
"""The need items ``generate_need`` returns to it."""


# --- the upgrade path ----------------------------------------------------------------

LAST_VERSION_OF_THE_FIVE_CLASSES = 17
"""The last ``ENV_DATA_VERSION`` whose environment stores the five ``NeedItemSource*``
classes: what an environment written before they became one says it is."""

FIVE_CLASSES_FIELDS = {
    "NeedItemSourceUnknown": (
        "docname",
        "lineno",
        "lineno_content",
        "external_url",
        "is_import",
        "is_external",
        "hops",
        "dict_repr",
    ),
    "NeedItemSourceDirective": (
        "hops",
        "lineno_content",
        "parser_lineno",
        "_lineno",
        "dict_repr",
    ),
    "NeedItemSourceService": ("hops", "_lineno", "dict_repr"),
    "NeedItemSourceExternal": ("hops", "dict_repr"),
    "NeedItemSourceImport": ("hops", "_lineno", "path", "dict_repr"),
}
"""The fields each of the five classes pickles, in its order: a slotted, frozen
dataclass pickles the list of its fields' values (``ENV_DATA_VERSION`` 14 to 17)."""


def test_the_last_version_of_the_five_classes_is_the_one_before_the_one_class():
    """The version the upgrade fence writes is the one before the version whose
    paragraph introduces ``NeedItemSource``: when another bump lands first and that
    paragraph is renumbered, this fails until the constant follows it (one step stale,
    the fence would stay green with the bump reverted)."""
    body = ast.parse(Path(data.__file__).read_text(encoding="utf-8")).body
    index = next(
        i
        for i, node in enumerate(body)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ENV_DATA_VERSION"
    )
    docstring = body[index + 1]
    assert isinstance(docstring, ast.Expr)
    assert isinstance(docstring.value, ast.Constant)
    (version,) = re.findall(
        r"^Version (\d+) stores every need's source as one class",
        docstring.value.value,
        re.M,
    )
    assert int(version) - 1 == LAST_VERSION_OF_THE_FIVE_CLASSES


def _as_the_five_classes_stored_it(source: Any) -> tuple[str, list[Any]]:
    """The class and the pickled state of ``source`` as the five classes stored it.

    Read from what every version of the sources gives alike -- the legacy keys, the
    hops and the parser line -- for the producers of the source hops project: the need
    directive and ``list2need`` (a parser line), ``needservice`` (a generated first hop),
    ``needimport`` (imported), ``needs_external_needs`` (an external first hop) and
    ``add_need`` (the rest).
    """
    keys = source.dict_repr
    hops = source.hops
    first = hops[0].kind if hops else None
    values: dict[str, Any] = {"hops": hops, "dict_repr": keys}
    if first == "external":
        name = "NeedItemSourceExternal"
    elif keys["is_import"]:
        name = "NeedItemSourceImport"
        assert hops[0].physical is not None
        # the argument as written, which is the file's path in this project
        values |= {"_lineno": keys["lineno"], "path": hops[0].physical.path}
    elif first == "generated":
        name = "NeedItemSourceService"
        values |= {"_lineno": keys["lineno"]}
    elif getattr(source, "parser_lineno", None) is not None:
        name = "NeedItemSourceDirective"
        values |= {
            "lineno_content": keys["lineno_content"],
            "parser_lineno": source.parser_lineno,
            # stored only where the first hop has no line to give it
            "_lineno": keys["lineno"] if first_line(hops) is None else None,
        }
    else:
        name = "NeedItemSourceUnknown"
        values |= {key: keys[key] for key in FIVE_CLASSES_FIELDS[name] if key in keys}
    return name, [values[field] for field in FIVE_CLASSES_FIELDS[name]]


def _stand_in(name: str) -> type:
    """A class that pickles as ``sphinx_needs.need_item.<name>`` did: by its name, then
    its list of field values."""

    def reduce(self: Any, protocol: int) -> tuple[Any, ...]:
        return (copyreg.__newobj__, (type(self),), list(self.state))

    return type(
        name,
        (),
        {
            "__module__": need_item.__name__,
            "__qualname__": name,
            "__slots__": ("state",),
            "__reduce_ex__": reduce,
        },
    )


class _Stored:
    """What a pickled source holds, read without its class."""

    __slots__ = ("state",)

    def __setstate__(self, state: list[Any]) -> None:
        self.state = state


class _StoredReader(pickle.Unpickler):
    """Reads the five classes as :class:`_Stored`, under their names."""

    def find_class(self, module: str, name: str) -> Any:
        if module == need_item.__name__ and name in FIVE_CLASSES_FIELDS:
            return type(name, (_Stored,), {"__slots__": ()})
        return super().find_class(module, name)


def _read_stored(data: bytes) -> tuple[str, list[Any]]:
    """The class name and the state a pickled source stores."""
    stored = _StoredReader(io.BytesIO(data)).load()
    return type(stored).__name__, stored.state


def test_an_environment_the_five_classes_stored_is_not_read_into_the_new_class(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """An environment written before the sources became one class gives the needs a
    fresh build gives.

    The project is built, and its pickled environment rewritten as the five classes and
    their last ``ENV_DATA_VERSION`` wrote it: each need's source pickled under its old class's
    name with its old fields, in their order. Rebuilt over it, the needs equal the fresh
    build's: the environment is read again (its version is not this one's, and the old
    names are no classes to unpickle), never loaded with the old fields in the new
    class's slots. Where the old names are still the classes (the base this was written
    on), the stand-in's pickle is checked to read back as theirs: the same class name
    and the same state.
    """
    srcdir = _hops_project(tmp_path)
    app = make_app("html", srcdir=srcdir, freshenv=True)
    try:
        app.build()
        assert_no_warnings(app)
        fresh = _all_keys(app)
        fresh_hops = {
            need_id: need.source.hops
            for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
        }
        pickled = Path(app.doctreedir) / "environment.pickle"
    finally:
        app.cleanup()

    with pickled.open("rb") as stream:
        env = pickle.load(stream)
    # where the five names are still classes (the base), what each source pickles as
    classes = {name: vars(need_item).get(name) for name in FIVE_CLASSES_FIELDS}
    stored = {}
    for need_id, need in env._needs_all_needs.items():
        name, state = _as_the_five_classes_stored_it(need.source)
        if isinstance(cls := classes[name], type) and cls.__name__ == name:
            assert type(need.source) is cls, need_id
            stored[need_id] = (name, state, pickle.dumps(need.source, 5))
        else:
            stored[need_id] = (name, state, None)
    assert len(stored) == len(fresh)
    stand_ins = {name: _stand_in(name) for name in FIVE_CLASSES_FIELDS}
    with monkeypatch.context() as patch:
        for name, stand_in in stand_ins.items():
            # in the module's namespace itself: an attribute lookup of a deprecated
            # name would warn, and restore the factory it returns there
            patch.setitem(vars(need_item), name, stand_in)
        for need_id, (name, state, as_pickled) in stored.items():
            old = object.__new__(stand_ins[name])
            old.state = state
            if as_pickled is not None:
                assert _read_stored(pickle.dumps(old, 5)) == _read_stored(as_pickled), (
                    need_id
                )
            env._needs_all_needs[need_id]._source = old
        env.__dict__.pop("_needs_view", None)
        env.version["sphinx_needs"] = LAST_VERSION_OF_THE_FIVE_CLASSES
        with pickled.open("wb") as stream:
            pickle.dump(env, stream, pickle.HIGHEST_PROTOCOL)

    app = make_app("html", srcdir=srcdir, freshenv=False)
    try:
        app.build()
        assert_no_warnings(app)
        assert _all_keys(app) == fresh
        assert {
            need_id: need.source.hops
            for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
        } == fresh_hops
    finally:
        app.cleanup()
