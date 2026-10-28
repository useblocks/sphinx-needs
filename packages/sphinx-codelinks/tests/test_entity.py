"""The naming of a definition node, ``describe_entity``, and the doc-comment test.

The shared extraction fixtures pin the names of the entities a marker is attached to;
these cases call the naming directly, for node kinds and spellings no marker in them
reaches (an operator, an indexer, a file-scoped namespace, a generic receiver).
"""

from pathlib import Path

import pytest
from tree_sitter import Node as TreeSitterNode

from sphinx_codelinks.analyse.entity import (
    EntityName,
    describe_entity,
    is_doc_comment,
)
from sphinx_codelinks.analyse.utils import init_tree_sitter
from sphinx_codelinks.source_discover.config import CommentType


def _nodes(source: str, comment_type: CommentType, suffix: str) -> list[TreeSitterNode]:
    parser, _ = init_tree_sitter(comment_type, Path(f"case.{suffix}"))
    tree = parser.parse(source.encode("utf-8"))
    found: list[TreeSitterNode] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        found.append(node)
        stack.extend(reversed(node.children))
    return found


def _describe(
    source: str, comment_type: CommentType, suffix: str, kind: str, index: int
) -> EntityName | None:
    nodes = [n for n in _nodes(source, comment_type, suffix) if n.type == kind]
    return describe_entity(nodes[index], comment_type)


@pytest.mark.parametrize(
    ("comment_type", "suffix", "source", "kind", "index", "expected"),
    [
        pytest.param(
            CommentType.cpp,
            "cpp",
            "namespace ns { struct W { W(); ~W(); bool operator==(const W&) const; }; }",
            "field_declaration",
            0,
            EntityName("operator", "ns::W::operator=="),
            id="cpp-member-operator",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "struct W { W(); ~W(); };",
            "declaration",
            1,
            EntityName("destructor", "W::~W"),
            id="cpp-in-class-destructor",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "template <typename T> struct Box { template <typename U> void put(U u); };",
            "declaration",
            0,
            EntityName("method", "Box::put"),
            id="cpp-member-template-is-a-method",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "namespace { int hidden() { return 1; } }",
            "function_definition",
            0,
            EntityName("function", "(anonymous namespace)::hidden"),
            id="cpp-anonymous-namespace",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "enum class Color { Red };",
            "enum_specifier",
            0,
            EntityName("enum", "Color"),
            id="cpp-enum",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "namespace A.B;\nclass C { public static C operator +(C a, C b) => a; }",
            "operator_declaration",
            0,
            EntityName("operator", "A.B.C.operator +"),
            id="csharp-file-scoped-namespace-and-operator",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "class C { public int this[int i] => i; ~C() {} }",
            "indexer_declaration",
            0,
            EntityName("indexer", "C.this[]"),
            id="csharp-indexer",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "class C { ~C() {} }",
            "destructor_declaration",
            0,
            EntityName("destructor", "C.~C"),
            id="csharp-destructor",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "class C { void M() { int local() => 1; } }",
            "local_function_statement",
            0,
            EntityName("function", "C.M.local"),
            id="csharp-local-function",
        ),
        pytest.param(
            CommentType.go,
            "go",
            "package p\nfunc (w *Widget[T]) Area() int { return 0 }\n",
            "method_declaration",
            0,
            EntityName("method", "Widget.Area"),
            id="go-generic-pointer-receiver",
        ),
        pytest.param(
            CommentType.go,
            "go",
            "package p\ntype (\n\tA int\n\tB struct{}\n)\n",
            "type_declaration",
            0,
            EntityName("type", None),
            id="go-grouped-type-declaration-has-no-name",
        ),
        pytest.param(
            CommentType.go,
            "go",
            "package p\ntype I interface { M() int }\n",
            "method_elem",
            0,
            EntityName("method", "I.M"),
            id="go-interface-method",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "mod m { pub struct G; impl crate::Shape for G { fn area(&self) {} } }",
            "function_item",
            0,
            EntityName("method", "<m::G as Shape>::area"),
            id="rust-trait-impl-in-module",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "impl Widget { fn new() -> Self { fn helper() {} Widget } }",
            "function_item",
            1,
            EntityName("function", "Widget::new::helper"),
            id="rust-function-in-inherent-method",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "impl<T> Shape for Vec<T> {}",
            "impl_item",
            0,
            EntityName("impl", "<Vec<T> as Shape>"),
            id="rust-generic-trait-impl-block",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "trait Shape { fn area(&self) -> f64; }",
            "function_signature_item",
            0,
            EntityName("method", "Shape::area"),
            id="rust-required-trait-method",
        ),
        pytest.param(
            CommentType.python,
            "py",
            "class A:\n    def m(self):\n        def inner():\n            pass\n",
            "function_definition",
            1,
            EntityName("function", "A.m.<locals>.inner"),
            id="python-locals",
        ),
        pytest.param(
            CommentType.ts,
            "ts",
            "namespace Gfx { export class W { draw(): void {} } }",
            "method_definition",
            0,
            EntityName("method", "Gfx.W.draw"),
            id="typescript-namespace-class-method",
        ),
        pytest.param(
            CommentType.ts,
            "ts",
            "declare var version: string;",
            "variable_declaration",
            0,
            None,
            id="typescript-ambient-value-is-unnamed",
        ),
        pytest.param(
            CommentType.yaml,
            "yaml",
            "a:\n  - b\n",
            "block_sequence_item",
            0,
            EntityName("item", None),
            id="yaml-item",
        ),
    ],
)
def test_describe_entity(
    comment_type: CommentType,
    suffix: str,
    source: str,
    kind: str,
    index: int,
    expected: EntityName | None,
) -> None:
    """``describe_entity`` names the node: its kind, and its name within the file."""
    assert _describe(source, comment_type, suffix, kind, index) == expected


def test_describe_entity_refuses_a_node_that_is_no_entity() -> None:
    """A node no table names (a C++ ``return`` statement) is described as nothing."""
    assert (
        _describe(
            "int f() { return 1; }", CommentType.cpp, "cpp", "return_statement", 0
        )
        is None
    )


@pytest.mark.parametrize(
    ("comment_type", "comment", "expected"),
    [
        (CommentType.cpp, "/// doc", True),
        (CommentType.cpp, "//! doc", True),
        (CommentType.cpp, "///< member", True),
        (CommentType.cpp, "/** doc */", True),
        (CommentType.cpp, "/*! doc */", True),
        (CommentType.cpp, "//// banner", False),
        (CommentType.cpp, "/**/", False),
        (CommentType.cpp, "/*** banner */", False),
        (CommentType.cpp, "// plain", False),
        (CommentType.cs, "/// doc", True),
        (CommentType.cs, "//! not in C#", False),
        (CommentType.rust, "/// doc", True),
        (CommentType.rust, "//! inner doc", True),
        (CommentType.ts, "/** JSDoc */", True),
        (CommentType.ts, "/// <reference path='x' />", False),
        (CommentType.go, "// Package doc", False),
    ],
)
def test_is_doc_comment(
    comment_type: CommentType, comment: str, expected: bool
) -> None:
    """The documentation-comment openings of each language, and their look-alikes."""
    suffix = {
        CommentType.cpp: "cpp",
        CommentType.cs: "cs",
        CommentType.rust: "rs",
        CommentType.ts: "ts",
        CommentType.go: "go",
    }[comment_type]
    source = (
        f"package p\n{comment}\n" if comment_type == CommentType.go else f"{comment}\n"
    )
    nodes = [
        n
        for n in _nodes(source, comment_type, suffix)
        if n.type in ("comment", "line_comment", "block_comment")
    ]
    assert is_doc_comment(nodes[0], comment_type) is expected
