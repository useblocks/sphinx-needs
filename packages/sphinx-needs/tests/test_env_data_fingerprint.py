"""The shape of the data sphinx-needs stores in the environment moves with
``ENV_DATA_VERSION``.

Sphinx pickles the environment, and every document's doctree, and loads them into the
next build as long as the extension's ``env_version`` has not changed. Data of an older
shape is then handed to code that no longer understands it: a slotted dataclass pickles
its fields by position, so a field added, removed or renamed takes the old values into
the wrong slots, and a key missing from a stored dict ends in a ``KeyError`` far from the
cause. ``ENV_DATA_VERSION`` has to be bumped whenever that shape changes, and this test
notices when it was not.

What is stored is measured, not listed. A representative project
(``doc_test/doc_env_data_fingerprint``: the need directives, parts, ``needimport``,
``needs_external_needs``, ``list2need``, ``needservice``, the API, a derived field,
variants, a ``needextend``, every view and role, a schema) is built, and every class of
``sphinx_needs`` that its pickled environment or doctrees name is collected, with the
type each ``env._need*`` attribute is declared as by its accessor on
:class:`~sphinx_needs.data.SphinxNeedsData`. A ``TypedDict`` pickles as a plain dict, so
it is found through the annotations: the classes those collected name in their stored
fields (a node's ``attributes``, a slotted class's constructor) are added, until nothing
new is named.

Each class's stored shape is fingerprinted: a dataclass's ``fields()``, in order, a
``TypedDict``'s keys and ``__total__``, a slotted class's ``__slots__``, an enum's members
and values, a docutils node's ``attributes`` annotation; with each field's annotation as
written in the source, which reads the same on every supported Python. The fingerprint
is pinned in ``fixtures/env_data_fingerprint.json``, beside the version it was pinned at,
and the test fails

- when the fingerprint changes and ``ENV_DATA_VERSION`` did not, and
- when ``ENV_DATA_VERSION`` changes and the pin was not updated, so that the two move
  together.

It cannot see a change of what stored values *mean* (the dependency order of version 10,
the new ``derive`` rules of versions 11 and 12, the located hidden needs of version 17):
the shape is the same, and that bump is still the author's to make.
"""

from __future__ import annotations

import ast
import dataclasses
import enum
import functools
import importlib
import inspect
import io
import json
import pickle
import shutil
import textwrap
from collections.abc import Callable, Iterable
from pathlib import Path
from types import ModuleType
from typing import Any, is_typeddict

import pytest
from docutils import nodes
from sphinx.testing.util import SphinxTestApp

from sphinx_needs import data
from sphinx_needs_testkit import assert_no_warnings

PROJECT = Path(__file__).parent / "doc_test" / "doc_env_data_fingerprint"
PIN = Path(__file__).parent / "fixtures" / "env_data_fingerprint.json"
REPIN = "uv run poe test-needs tests/test_env_data_fingerprint.py --snapshot-update"
PACKAGE = "sphinx_needs"


# --- what is stored ------------------------------------------------------------------


class _GlobalsRecorder(pickle.Unpickler):
    """Unpickles, recording every global the pickle names: each class it stores."""

    def __init__(self, stream: io.BytesIO, found: set[tuple[str, str]]) -> None:
        super().__init__(stream)
        self._found = found

    def find_class(self, module: str, name: str) -> Any:
        self._found.add((module, name))
        return super().find_class(module, name)


def _pickled_globals(doctreedir: Path) -> set[tuple[str, str]]:
    """The ``(module, name)`` of every global the environment and the doctrees name."""
    found: set[tuple[str, str]] = set()
    paths = [doctreedir / "environment.pickle", *sorted(doctreedir.rglob("*.doctree"))]
    for path in paths:
        _GlobalsRecorder(io.BytesIO(path.read_bytes()), found).load()
    return found


def _accessor_annotations() -> dict[str, str]:
    """The type each ``env._need*`` attribute is declared as: the return annotation of
    the :class:`~sphinx_needs.data.SphinxNeedsData` method that reads it."""
    tree = ast.parse(Path(data.__file__).read_text(encoding="utf-8"))
    (cls,) = (
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SphinxNeedsData"
    )
    declared: dict[str, str] = {}
    for method in cls.body:
        if not isinstance(method, ast.FunctionDef) or method.returns is None:
            continue
        returns = ast.unparse(method.returns)
        if returns == "None":
            continue
        for node in ast.walk(method):
            # ``self.env.<name>``, or ``getattr(self.env, "<name>", ...)``
            if isinstance(node, ast.Attribute) and _is_self_env(node.value):
                name = node.attr
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) > 1
                and _is_self_env(node.args[0])
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
            ):
                name = node.args[1].value
            else:
                continue
            if name.startswith("_need"):
                declared.setdefault(name, returns)
    return declared


def _is_self_env(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "env"
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _env_attributes(doctreedir: Path) -> list[str]:
    """The names of the attributes sphinx-needs stores on the pickled environment."""
    with (doctreedir / "environment.pickle").open("rb") as stream:
        env = pickle.load(stream)
    return sorted(name for name in vars(env) if name.startswith("_need"))


def _class_annotations(cls: type) -> dict[str, str]:
    """The annotations of a class body as written, those under ``if TYPE_CHECKING:``
    included (a node's ``attributes``)."""
    source = textwrap.dedent(inspect.getsource(cls))
    (body,) = ast.parse(source).body
    assert isinstance(body, ast.ClassDef)
    annotations: dict[str, str] = {}
    pending: list[ast.stmt] = list(body.body)
    while pending:
        node = pending.pop(0)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            annotations[node.target.id] = ast.unparse(node.annotation)
        elif isinstance(node, ast.If):
            pending.extend([*node.body, *node.orelse])
    return annotations


def _annotation(value: Any, where: str) -> str:
    """An annotation as written in the source, normalised: the same on every Python."""
    text = value.__forward_arg__ if hasattr(value, "__forward_arg__") else value
    assert isinstance(text, str), (
        f"the annotation of {where} is {value!r}, not its source text: its module needs "
        "'from __future__ import annotations'"
    )
    return ast.unparse(ast.parse(text, mode="eval"))


def _functional_typeddict(cls: type) -> dict[str, str]:
    """The keys of a ``TypedDict`` made by a call, ``X = TypedDict("X", {...})``, with
    their annotations as written: the call holds objects, not the source text."""
    module = importlib.import_module(cls.__module__)
    for node in _module_tree(module.__name__).body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "TypedDict"
            and isinstance(node.value.args[0], ast.Constant)
            and node.value.args[0].value == cls.__name__
            and isinstance(node.value.args[1], ast.Dict)
        ):
            return {
                key.value: ast.unparse(value)
                for key, value in zip(
                    node.value.args[1].keys, node.value.args[1].values, strict=True
                )
                if isinstance(key, ast.Constant)
            }
    return {}


def _slots(cls: type) -> list[str]:
    """Every slot of a class, its bases' first."""
    return [
        slot
        for base in reversed(cls.__mro__)
        for slot in (
            [base.__dict__["__slots__"]]
            if isinstance(base.__dict__.get("__slots__"), str)
            else base.__dict__.get("__slots__", ())
        )
    ]


def _shape(cls: type) -> dict[str, Any]:
    """What a class stores, by its kind."""
    if is_typeddict(cls):
        functional = _functional_typeddict(cls)
        return {
            "kind": "TypedDict",
            "total": cls.__total__,
            "keys": [
                [
                    key,
                    _annotation(functional.get(key, value), f"{_qualified(cls)}.{key}"),
                ]
                for key, value in cls.__annotations__.items()
            ],
        }
    if dataclasses.is_dataclass(cls):
        return {
            "kind": "dataclass",
            "slots": "__slots__" in vars(cls),
            "fields": [
                [field.name, _annotation(field.type, f"{_qualified(cls)}.{field.name}")]
                for field in dataclasses.fields(cls)
            ],
        }
    if issubclass(cls, enum.Enum):
        return {
            "kind": "enum",
            "members": [[member.name, repr(member.value)] for member in cls],
        }
    if issubclass(cls, nodes.Node):
        attributes = _class_annotations(cls).get("attributes")
        return {
            "kind": "node",
            "attributes": None
            if attributes is None
            else _annotation(attributes, f"{_qualified(cls)}.attributes"),
        }
    if "__slots__" in vars(cls):
        return {"kind": "slots", "slots": _slots(cls)}
    raise AssertionError(
        f"{_qualified(cls)} is stored in the environment, but this test does not know "
        "what its stored shape is: teach _shape() its kind"
    )


def _named(cls: type) -> list[str]:
    """The annotations of what a class stores, which name the classes it may hold."""
    shape = _shape(cls)
    if shape["kind"] == "TypedDict":
        return [annotation for _, annotation in shape["keys"]]
    if shape["kind"] == "dataclass":
        return [annotation for _, annotation in shape["fields"]]
    if shape["kind"] == "node":
        return [] if shape["attributes"] is None else [shape["attributes"]]
    if shape["kind"] == "slots":
        # a slotted class declares what its slots hold by its constructor
        init = vars(cls).get("__init__")
        return [
            _annotation(value, f"{_qualified(cls)}.__init__({name})")
            for name, value in getattr(init, "__annotations__", {}).items()
            if name != "return"
        ]
    return []


@functools.cache
def _module_tree(module_name: str) -> ast.Module:
    return ast.parse(inspect.getsource(importlib.import_module(module_name)))


def _module_statements(module_name: str) -> list[ast.stmt]:
    """A module's top-level statements, those under an ``if`` (``TYPE_CHECKING``) or a
    ``try`` included."""
    statements: list[ast.stmt] = []
    pending: list[ast.stmt] = list(_module_tree(module_name).body)
    while pending:
        node = pending.pop(0)
        statements.append(node)
        if isinstance(node, ast.If):
            pending.extend([*node.body, *node.orelse])
        elif isinstance(node, ast.Try):
            pending.extend(
                [
                    *node.body,
                    *(stmt for handler in node.handlers for stmt in handler.body),
                    *node.orelse,
                    *node.finalbody,
                ]
            )
    return statements


def _classes_named(
    annotation: str, module: ModuleType, seen: set[tuple[str, str]] | None = None
) -> set[type]:
    """The classes of this package an annotation in ``module`` names."""
    seen = set() if seen is None else seen
    found: set[type] = set()
    for node in ast.walk(ast.parse(annotation, mode="eval")):
        if isinstance(node, ast.Name):
            found |= _classes_of_name(node.id, module, seen)
    return found


def _classes_of_name(
    name: str, module: ModuleType, seen: set[tuple[str, str]]
) -> set[type]:
    """The classes of this package a name in ``module`` stands for: a class itself, or
    those of the type alias it names, or of the name an import (under
    ``TYPE_CHECKING`` too) brings in."""
    if (module.__name__, name) in seen:
        return set()
    seen.add((module.__name__, name))
    value = vars(module).get(name)
    if inspect.isclass(value):
        if value.__module__.split(".")[0] != PACKAGE or getattr(
            value, "_is_protocol", False
        ):
            # not this package's; or a protocol, which stores nothing: what
            # implements it is measured
            return set()
        return {value}
    for node in _module_statements(module.__name__):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    source = importlib.import_module(
                        "." * node.level + (node.module or ""), module.__package__
                    )
                    return _classes_of_name(alias.name, source, seen)
        elif (aliased := _alias_value(node, name)) is not None:
            return _classes_named(ast.unparse(aliased), module, seen)
    return set()


def _alias_value(node: ast.stmt, name: str) -> ast.expr | None:
    """What a type alias assigns to ``name``: ``X = A | B``, or
    ``X: TypeAlias = A | B``."""
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == name for target in node.targets
    ):
        return node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == name
    ):
        return node.value
    return None


def _qualified(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _close(classes: Iterable[type]) -> dict[str, type]:
    """The classes, with every class their stored fields name, transitively."""
    found: dict[str, type] = {}
    pending = list(classes)
    while pending:
        cls = pending.pop()
        if _qualified(cls) in found:
            continue
        found[_qualified(cls)] = cls
        module = importlib.import_module(cls.__module__)
        for annotation in _named(cls):
            pending.extend(_classes_named(annotation, module))
    return found


def _stored(doctreedir: Path) -> tuple[dict[str, str], dict[str, type]]:
    """The declared type of each stored ``env._need*`` attribute, and every class of
    this package the environment and the doctrees store or may store."""
    declared = _accessor_annotations()
    stored_attributes = _env_attributes(doctreedir)
    undeclared = [name for name in stored_attributes if name not in declared]
    assert not undeclared, (
        f"env.{', env.'.join(undeclared)} is stored in the environment, but no "
        "SphinxNeedsData method reading it declares its type: store it through an "
        "accessor with a return annotation, so that its shape is fingerprinted"
    )
    env = {name: declared[name] for name in stored_attributes}

    classes: list[type] = []
    for module_name, name in sorted(_pickled_globals(doctreedir)):
        if module_name.split(".")[0] != PACKAGE:
            continue
        value: Any = importlib.import_module(module_name)
        for part in name.split("."):
            value = getattr(value, part)
        assert inspect.isclass(value), (
            f"{module_name}.{name} is pickled into the environment and is no class: "
            "teach this test what its stored shape is"
        )
        classes.append(value)
    for annotation in env.values():
        classes.extend(_classes_named(annotation, data))
    return env, _close(classes)


def _fingerprint(env: dict[str, str], classes: dict[str, type]) -> dict[str, Any]:
    return {
        "env": env,
        "classes": {name: _shape(cls) for name, cls in sorted(classes.items())},
    }


# --- the comparison ------------------------------------------------------------------


def _differences(pinned: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """What changed between two fingerprints, one line each."""
    lines = []
    for section in ("env", "classes"):
        old, new = pinned.get(section, {}), current[section]
        for name in sorted(set(old) | set(new)):
            if name not in new:
                lines.append(f"  {name} is no longer stored")
            elif name not in old:
                lines.append(f"  {name} is newly stored: {_describe(new[name])}")
            elif old[name] != new[name]:
                lines.append(f"  {name}: {_changed(old[name], new[name])}")
    return lines


def _describe(shape: Any) -> str:
    if not isinstance(shape, dict):
        return repr(shape)
    return ", ".join(
        f"{key} {_items(value) if isinstance(value, list) else repr(value)}"
        for key, value in shape.items()
    )


def _items(items: list[Any]) -> str:
    return (
        "("
        + ", ".join(
            ": ".join(map(str, item)) if isinstance(item, list) else str(item)
            for item in items
        )
        + ")"
    )


def _changed(old: Any, new: Any) -> str:
    """How one class's (or attribute's) stored shape changed."""
    if not (isinstance(old, dict) and isinstance(new, dict)):
        return f"{old!r} is now {new!r}"
    parts = []
    for key in [*old, *(key for key in new if key not in old)]:
        before, after = old.get(key), new.get(key)
        if before == after:
            continue
        if isinstance(before, list) and isinstance(after, list):
            removed = [item for item in before if item not in after]
            added = [item for item in after if item not in before]
            change = " ".join(
                [
                    *([f"-{_items(removed)}"] if removed else []),
                    *([f"+{_items(added)}"] if added else []),
                ]
            )
            parts.append(f"{key} {change or 'reordered'}")
        else:
            parts.append(f"{key} {before!r} is now {after!r}")
    return "; ".join(parts)


def _write_pin(fingerprint: dict[str, Any]) -> None:
    pin = {"ENV_DATA_VERSION": data.ENV_DATA_VERSION, **fingerprint}
    PIN.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")


def test_the_stored_shape_moves_with_env_data_version(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    request: pytest.FixtureRequest,
):
    """A change of the stored shape without a bump of ``ENV_DATA_VERSION`` is red, and
    so is a bump the pin does not follow.

    Run with ``--snapshot-update`` (the suite's snapshot convention), it re-pins the
    fingerprint once the version has been bumped, and refuses to while it has not.
    """
    shutil.copytree(PROJECT, tmp_path / "project")
    app = make_app("html", srcdir=tmp_path / "project", freshenv=True)
    try:
        app.build()
        assert_no_warnings(app)
        doctreedir = Path(app.doctreedir)
        env, classes = _stored(doctreedir)
    finally:
        app.cleanup()
    current = _fingerprint(env, classes)

    pinned: dict[str, Any] = (
        json.loads(PIN.read_text(encoding="utf-8")) if PIN.exists() else {}
    )
    pinned_version = pinned.pop("ENV_DATA_VERSION", None)
    version = data.ENV_DATA_VERSION
    changes = _differences(pinned, current)
    if changes and pinned_version == version:
        # never re-pinned, not even with --snapshot-update: the bump comes first
        pytest.fail(
            "The shape of the data sphinx-needs stores in the environment changed, "
            f"and ENV_DATA_VERSION did not (it is {version}, as pinned):\n"
            + "\n".join(changes)
            + "\nAn environment an older build pickled would be loaded into the new "
            "shape. Bump ENV_DATA_VERSION in src/sphinx_needs/data.py, add the "
            "'Version N' paragraph that says what changed, and re-pin with\n"
            f"  {REPIN}",
            pytrace=False,
        )
    if pinned_version == version:
        return
    if request.config.getoption("--snapshot-update"):
        _write_pin(current)
        return
    pytest.fail(
        f"ENV_DATA_VERSION is {version}, and the shape of the data sphinx-needs stores "
        f"in the environment is pinned at {pinned_version}"
        + (":\n" + "\n".join(changes) if changes else " (the shape is the same)")
        + f"\nRe-pin it, so that the two move together:\n  {REPIN}",
        pytrace=False,
    )
