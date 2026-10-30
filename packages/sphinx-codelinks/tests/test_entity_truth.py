"""Which code entity each marker is attached to, against compiler ground truth.

A case of ``tests/data/extraction/*.yaml`` may carry a ``truth`` list: for each marker
id, the entity a compiler (or, for a rule case, the attachment rule) says the marker
belongs to -- its kind, its name within the file, its first line and, for a rule case,
the mechanism. The case is extracted exactly as ``test_extraction_fixtures.py`` does,
and every marker's ``scope`` is compared with its entry. ``entities.yaml`` documents
the entries and where the truth comes from.

``KNOWN_WRONG_TODAY`` lists the markers the analysis attaches wrongly today. Each one
is asserted to STILL be wrong, so the list cannot go stale: a fix that rights one fails
here until the fix also delists it.

The fence of ``semantic``: in every case of every shared fixture, each ``scope``'s
components, rendered by the rule of its ``language``, spell its ``qualified_name``
exactly. And kinds describe, names identify: the name chain of one entity does not
depend on how it is written.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, get_args

import pytest
import yaml

from sphinx_codelinks.analyse.entity import EntityKind, name_chain, render_semantic

from .test_extraction_fixtures import FIXTURE_DIR, _extract, _load_cases

KNOWN_WRONG_TODAY: frozenset[str] = frozenset()
"""Marker ids whose ``scope`` differs from their truth today."""


def _truth_cases() -> list[Any]:
    cases = []
    for path in sorted(FIXTURE_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, case in data.items():
            if "truth" in case:
                cases.append(pytest.param(case, id=f"{path.stem}-{name}"))
    return cases


def _marker_id(item: dict[str, Any]) -> str:
    if item["type"] == "need-id-refs":
        return str(item["need_ids"][0])
    return str(item["need"]["id"])


def _scope(item: dict[str, Any]) -> dict[str, Any] | None:
    if item["type"] == "multiline-need":
        return item["source"]["scope"]
    return item["scope"]


# The ``scope`` key each truth key is compared with.
_TRUTH_KEYS = {
    "node_kind": "kind",
    "entity_kind": "entity_kind",
    "qualified_name": "qualified_name",
    "start": "start",
    "mechanism": "mechanism",
}


def _difference(scope: dict[str, Any] | None, entry: dict[str, Any]) -> str | None:
    """How ``scope`` differs from the truth ``entry``, or ``None`` if it matches.

    An entry with no ``entity_kind`` expects no entity, unless it names the
    ``node_kind`` bound: an entity the syntax cannot name.
    """
    if entry["entity_kind"] is None and "node_kind" not in entry:
        return None if scope is None else f"expected no entity, got {scope}"
    if scope is None:
        return "expected an entity, got none"
    expected = {
        scope_key: entry[key] for key, scope_key in _TRUTH_KEYS.items() if key in entry
    }
    got = {key: scope[key] for key in expected}
    return None if got == expected else f"expected {expected}, got {got}"


@pytest.mark.parametrize("case", _truth_cases())
def test_entity_truth(case: dict[str, Any], tmp_path: Path) -> None:
    """Every marker of the case is attached to the entity its truth names."""
    content, _ = _extract(case, tmp_path, case["source"])
    scopes = {_marker_id(item): _scope(item) for item in content}
    truth = {entry["id"]: entry for entry in case["truth"]}
    assert sorted(scopes) == sorted(truth), "every marker has exactly one truth entry"

    wrong = {}
    right_but_listed = []
    for marker_id, entry in truth.items():
        difference = _difference(scopes[marker_id], entry)
        if marker_id in KNOWN_WRONG_TODAY:
            if difference is None:
                right_but_listed.append(marker_id)
        elif difference is not None:
            wrong[marker_id] = difference
    assert not wrong, "attached to the wrong entity:\n" + "\n".join(
        f"  {marker_id}: {difference}" for marker_id, difference in wrong.items()
    )
    assert not right_but_listed, (
        f"now attached right, remove from KNOWN_WRONG_TODAY: {right_but_listed}"
    )


def test_known_wrong_today_names_real_markers() -> None:
    """Every listed id is a marker some case has a truth entry for."""
    ids = {
        entry["id"] for param in _truth_cases() for entry in param.values[0]["truth"]
    }
    assert KNOWN_WRONG_TODAY <= ids, sorted(KNOWN_WRONG_TODAY - ids)


# The kinds a component may have: the entity kinds, and ``scope`` for a C++ qualifier
# the syntax cannot classify.
_COMPONENT_KINDS = frozenset(get_args(EntityKind)) | {"scope"}


# The ``scope.language`` of each fixture ``lang``: the language the file is analysed
# as, by its name, ``c`` for a ``.c`` file and ``cpp`` for a ``.h`` one.
_LANGUAGES = {
    "cpp": "cpp",
    "c": "c",
    "cpp_header": "cpp",
    "python": "python",
    "csharp": "cs",
    "rust": "rust",
    "yaml": "yaml",
    "go": "go",
    "jsonc": "jsonc",
    "bash": "bash",
    "typescript": "ts",
    "tsx": "ts",
    "js": "ts",
}


def _fence_difference(scope: dict[str, Any], lang: str) -> str | None:
    """How ``scope``'s ``semantic`` fails the fence, or ``None`` if it holds."""
    if scope["language"] != _LANGUAGES[lang]:
        return f"language {scope['language']!r}, not {_LANGUAGES[lang]!r}"
    semantic = scope["semantic"]
    if scope["qualified_name"] is None:
        return None if semantic is None else f"no name, but components {semantic}"
    if not semantic:
        return f"{scope['qualified_name']!r} has no components"
    for element in semantic:
        extra = set(element) - {"kind", "name"}
        if element["kind"] not in _COMPONENT_KINDS:
            return f"component of unknown kind: {element}"
        if extra and (extra != {"trait"} or element["kind"] != "impl"):
            return f"component with extra keys: {element}"
    if semantic[-1]["kind"] != scope["entity_kind"]:
        return f"last component {semantic[-1]} is not the {scope['entity_kind']}"
    rendered = render_semantic(semantic, scope["language"])
    if rendered != scope["qualified_name"]:
        return f"{semantic} renders {rendered!r}, not {scope['qualified_name']!r}"
    return None


@pytest.mark.parametrize("case", _load_cases())
def test_semantic_spells_the_qualified_name(
    case: dict[str, Any], tmp_path: Path
) -> None:
    """Every ``scope`` of the case: its components, outermost first and the entity
    last, rendered by the rule of its ``language``, are its ``qualified_name``; it has
    none exactly when it has no name."""
    content, _ = _extract(case, tmp_path, case["source"])
    failures = {
        index: difference
        for index, item in enumerate(content)
        if (scope := _scope(item)) is not None
        and (difference := _fence_difference(scope, case["lang"])) is not None
    }
    assert not failures, "\n".join(
        f"  record {index}: {difference}" for index, difference in failures.items()
    )


def _semantic_of(case_name: str, tmp_path: Path) -> dict[str, list[dict[str, Any]]]:
    """The ``semantic`` of each marker of ``entities.yaml``'s case ``case_name``."""
    cases = yaml.safe_load((FIXTURE_DIR / "entities.yaml").read_text(encoding="utf-8"))
    case = cases[case_name]
    root = tmp_path / case_name
    root.mkdir()
    content, _ = _extract(case, root, case["source"])
    semantic = {}
    for item in content:
        scope = _scope(item)
        assert scope is not None
        semantic[_marker_id(item)] = scope["semantic"]
    return semantic


def _kinds(semantic: list[dict[str, Any]]) -> list[str]:
    return [element["kind"] for element in semantic]


def test_name_chain_ignores_kinds(tmp_path: Path) -> None:
    """Kinds describe, names identify: one C++ method, defined in its class and out of
    line, has two kind sequences and one name chain."""
    in_class = _semantic_of("rule_name_chain_cpp_method_in_class", tmp_path)
    out_of_line = _semantic_of("rule_name_chain_cpp_method_out_of_line", tmp_path)
    nested, defined = in_class["IMPL_R_CHAIN_1"], out_of_line["IMPL_R_CHAIN_2"]
    assert _kinds(nested) == ["namespace", "class", "method"]
    assert _kinds(defined) == ["scope", "class", "method"]
    assert name_chain(nested, "cpp") == name_chain(defined, "cpp")


def test_name_chain_keeps_the_trait(tmp_path: Path) -> None:
    """A Rust impl's ``trait`` identifies, as a name does: the ``area`` of two trait
    impls of one type have the same names and kinds, and two name chains."""
    semantic = _semantic_of("rule_name_chain_rust_trait_is_identity", tmp_path)
    shape, other = semantic["IMPL_R_CHAIN_3"], semantic["IMPL_R_CHAIN_4"]
    assert [element["name"] for element in shape] == ["Widget", "area"]
    assert [element["name"] for element in other] == ["Widget", "area"]
    assert _kinds(shape) == _kinds(other) == ["impl", "method"]
    assert (shape[0]["trait"], other[0]["trait"]) == ("Shape", "Other")
    assert name_chain(shape, "rust") != name_chain(other, "rust")


def test_name_chain_keeps_the_locals_boundary(tmp_path: Path) -> None:
    """CPython's ``<locals>`` identifies, as a name does: the method ``g`` of a nested
    class ``f`` and a function ``g`` nested in a method ``f`` have the same names and
    two name chains."""
    semantic = _semantic_of("rule_name_chain_python_locals_is_identity", tmp_path)
    method, function = semantic["IMPL_R_CHAIN_5"], semantic["IMPL_R_CHAIN_6"]
    assert [element["name"] for element in method] == ["A", "f", "g"]
    assert [element["name"] for element in function] == ["A", "f", "g"]
    assert _kinds(method) == ["class", "class", "method"]
    assert _kinds(function) == ["class", "method", "function"]
    assert name_chain(method, "python") != name_chain(function, "python")


def test_name_chain_contains_by_module(tmp_path: Path) -> None:
    """An impl written inside an in-file module is inside it by name chain: the module
    is a part of its own, so the chain of every member of the impl starts with the
    module's, as a free function's in it does; a nested module's starts with both."""
    semantic = _semantic_of("rule_name_chain_rust_impl_in_module", tmp_path)
    chains = {marker: name_chain(parts, "rust") for marker, parts in semantic.items()}
    module_m = name_chain([{"kind": "module", "name": "m"}], "rust")
    module_n = name_chain(
        [{"kind": "module", "name": "m"}, {"kind": "module", "name": "n"}], "rust"
    )
    assert module_m is not None and module_n is not None
    for marker in ("IMPL_R_MOD_1", "IMPL_R_MOD_2", "IMPL_R_MOD_3", "IMPL_R_MOD_4"):
        chain = chains[marker]
        assert chain is not None and chain[: len(module_m)] == module_m, marker
    chain = chains["IMPL_R_MOD_4"]
    assert chain is not None and chain[: len(module_n)] == module_n
    assert semantic["IMPL_R_MOD_1"] == [
        {"kind": "module", "name": "m"},
        {"kind": "impl", "name": "G"},
        {"kind": "method", "name": "new"},
    ]
    assert semantic["IMPL_R_MOD_2"] == [
        {"kind": "module", "name": "m"},
        {"kind": "impl", "name": "G", "trait": "m::Shape"},
        {"kind": "method", "name": "area"},
    ]
    # a path keeps its spelling, a path from the crate root its root
    assert _kinds(semantic["IMPL_R_MOD_5"]) == ["module", "impl", "method"]
    assert semantic["IMPL_R_MOD_5"][1]["name"] == "x::P"
    assert semantic["IMPL_R_MOD_6"][1]["name"] == "crate::Q"
