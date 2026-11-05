"""The C++ names clang prints, where they differ from what one syntax node shows.

``test_entity.py`` names one node at a time. These cases pin the C++ rules that make a
name the one the compiler prints for the entity, and the rules a whole file decides
(:class:`~sphinx_codelinks.analyse.entity.CppNames`): which names keep their full chain
because leaving a container out would make two definitions share one. Another
implementation of the same naming holds the same cases.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tree_sitter import Node as TreeSitterNode

from sphinx_codelinks.analyse import utils
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.entity import (
    CppNames,
    EntityKind,
    cpp_signature,
    describe_entity,
    is_entity,
)
from sphinx_codelinks.config import SourceAnalyseConfig
from sphinx_codelinks.source_discover.config import CommentType


def _parsed(source: str, path: str = "src/a.cpp") -> tuple[TreeSitterNode, CppNames]:
    """``source`` parsed as the analysis parses a file at ``path``."""
    parser, _ = utils.init_tree_sitter(CommentType.cpp, Path(path))
    tree, names = utils.parse_source(
        source.encode("utf-8"), parser, CommentType.cpp, Path(path)
    )
    assert names is not None
    return tree.root_node, names


def _nodes_of(root: TreeSitterNode, kind: str) -> list[TreeSitterNode]:
    found: list[TreeSitterNode] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == kind:
            found.append(node)
        stack.extend(reversed(node.children))
    return found


def _functions(source: str, path: str = "src/a.cpp") -> set[str]:
    """Every function of ``source`` (definition or declaration) as the file names it,
    with its normalised parameters: what tells two of them apart."""
    root, names = _parsed(source, path)
    found = set()
    stack = [root]
    while stack:
        node = stack.pop()
        stack.extend(node.children)
        if not is_entity(node, CommentType.cpp) or node.type not in (
            "function_definition",
            "declaration",
            "field_declaration",
        ):
            continue
        name = describe_entity(node, CommentType.cpp, source=names.source)
        assert name is not None
        named = names.qualify(name)
        found.add(f"{named.qualified_name}{cpp_signature(node, names.source)}")
    return found


@pytest.mark.parametrize(
    ("source", "kind", "index", "expected_kind", "expected", "parts"),
    [
        # An inline namespace adds nothing to the names of what it holds (named,
        # nested, anonymous, and an ``inline`` part of a C++20 nested name), while the
        # inline namespace itself keeps its own name: clang prints
        # ``nlohmann::basic_json``, not ``nlohmann::json_abi_v3_12_0::basic_json``.
        pytest.param(
            "namespace lib { inline namespace v1 { void f() {} } }",
            "function_definition",
            0,
            "function",
            "lib::f",
            ["namespace lib", "function f"],
            id="inline_in_named",
        ),
        pytest.param(
            "namespace a { inline namespace v1 { inline namespace v2 { void f() {} } } }",
            "function_definition",
            0,
            "function",
            "a::f",
            ["namespace a", "function f"],
            id="nested_inline",
        ),
        pytest.param(
            "namespace a { inline namespace { void f() {} } }",
            "function_definition",
            0,
            "function",
            "a::f",
            ["namespace a", "function f"],
            id="anonymous_inline",
        ),
        pytest.param(
            "inline namespace v1 { struct W { void m(); }; }",
            "field_declaration",
            0,
            "method",
            "W::m",
            ["struct W", "method m"],
            id="class_in_inline",
        ),
        pytest.param(
            "namespace lib { inline namespace v1 { void f() {} } }",
            "namespace_definition",
            1,
            "namespace",
            "lib::v1",
            ["namespace lib", "namespace v1"],
            id="inline_entity_keeps_its_own_name",
        ),
        pytest.param(
            "namespace a { inline namespace { void f() {} } }",
            "namespace_definition",
            1,
            "namespace",
            "a::(anonymous namespace)",
            ["namespace a", "namespace (anonymous namespace)"],
            id="anonymous_inline_entity",
        ),
        pytest.param(
            "namespace a { namespace v1 { void f() {} } }",
            "function_definition",
            0,
            "function",
            "a::v1::f",
            ["namespace a", "namespace v1", "function f"],
            id="non_inline_kept",
        ),
        pytest.param(
            "namespace a::inline v1 { void f() {} }",
            "function_definition",
            0,
            "function",
            "a::f",
            ["namespace a", "function f"],
            id="nested_name_inline_part",
        ),
        pytest.param(
            "namespace a::inline v1 { void f() {} }",
            "namespace_definition",
            0,
            "namespace",
            "a::v1",
            ["namespace a", "namespace v1"],
            id="nested_name_inline_part_entity",
        ),
        pytest.param(
            "namespace a::inline v1::b { void f() {} }",
            "namespace_definition",
            0,
            "namespace",
            "a::b",
            ["namespace a", "namespace b"],
            id="nested_name_inline_qualifier",
        ),
    ],
)
def test_cpp_names_as_clang_prints_them(
    source: str,
    kind: str,
    index: int,
    expected_kind: EntityKind,
    expected: str,
    parts: list[str],
) -> None:
    """Each case's name, of the node alone, is the one clang prints for the entity."""
    parser, _ = utils.init_tree_sitter(CommentType.cpp, Path("a.cpp"))
    tree = parser.parse(source.encode("utf-8"))
    assert not tree.root_node.has_error, str(tree.root_node)
    node = _nodes_of(tree.root_node, kind)[index]
    named = describe_entity(node, CommentType.cpp)
    assert named is not None
    assert (named.kind, named.qualified_name) == (expected_kind, expected)
    assert named.semantic is not None
    assert [f"{part['kind']} {part['name']}" for part in named.semantic] == parts


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nvoid h(int) {}\n}\n"
            "inline namespace v2 {\nvoid h(int) {}\n}\n}\n",
            {"lib::v1::h(int)", "lib::v2::h(int)"},
            id="two_inline_siblings",
        ),
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nvoid f() {}\n}\nvoid f(long) {}\n}\n"
            "namespace lib::inline v3 {\nvoid z() {}\n}\nnamespace lib {\nvoid z() {}\n}\n",
            {"lib::f()", "lib::f(long)", "lib::v3::z()", "lib::z()"},
            id="inline_beside_its_parent",
        ),
        pytest.param(
            "namespace lib {\n#if ABI_V2\ninline namespace v2 {\nvoid g() {}\n}\n#else\n"
            "inline namespace v1 {\nvoid g() {}\n}\n#endif\n}\n",
            {"lib::v1::g()", "lib::v2::g()"},
            id="abi_version_arms",
        ),
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nvoid h(int);\nvoid h(int) {}\n}\n"
            "inline namespace v2 {\nvoid h(int) {}\n}\n}\n",
            {"lib::v1::h(int)", "lib::v2::h(int)"},
            id="a_declaration_follows_its_group",
        ),
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nvoid f() {}\n}\n}\n",
            {"lib::f()"},
            id="one_inline_namespace",
        ),
    ],
)
def test_names_that_would_collide_keep_their_full_chain(
    source: str, expected: set[str]
) -> None:
    """Leaving an inline namespace out of a name never makes two definitions of a file
    share one: where it would, every entity of that name and parameters keeps its full
    chain, as before it was left out (two inline siblings, an inline namespace beside
    its parent, the ``#if``/``#else`` arms of an ABI version, a declaration with its
    group); where it would not, the name is clang's."""
    assert _functions(source) == expected


def test_a_c_file_gets_no_file_level_names() -> None:
    """A ``.c`` file is C: it is parsed as written, and no name is decided by the
    whole file."""
    parser, _ = utils.init_tree_sitter(CommentType.cpp, Path("a.c"))
    _, names = utils.parse_source(
        b"int f(void) { return 0; }\n", parser, CommentType.cpp, Path("src/a.c")
    )
    assert names is None


def _marker_names(
    tmp_path: Path, source: str, filename: str = "a.cpp"
) -> dict[str, str | None]:
    """The qualified name of the entity each ``@need-ids:`` marker of ``source`` is
    attached to, by its first id, as the analysis of a file ``filename`` gives it."""
    path = tmp_path / filename
    path.write_bytes(source.encode("utf-8"))
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[path],
            src_dir=tmp_path,
            comment_type=CommentType.cpp,
            get_need_id_refs=True,
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return {
        ref.need_ids[0]: ref.scope["qualified_name"] if ref.scope else None
        for ref in analyse.need_id_refs
    }


def test_markers_are_named_as_the_file_names_them(tmp_path: Path) -> None:
    """A marker's entity is named as the whole file names it: an inline namespace is
    left out, except where two definitions would then share a name."""
    source = (
        "namespace lib {\ninline namespace v1 {\n// @need-ids: REQ_A\nvoid f() {}\n"
        "// @need-ids: REQ_B\nvoid h(int) {}\n}\ninline namespace v2 {\n"
        "// @need-ids: REQ_C\nvoid h(int) {}\n}\n}\n"
    )
    assert _marker_names(tmp_path, source) == {
        "REQ_A": "lib::f",
        "REQ_B": "lib::v1::h",
        "REQ_C": "lib::v2::h",
    }
