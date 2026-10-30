"""The naming of a definition node, ``describe_entity``, its components and how
they render, and the doc-comment test.

The shared extraction fixtures pin the names of the entities a marker is attached to;
these cases call the naming directly, for node kinds and spellings no marker in them
reaches (an operator, an indexer, a file-scoped namespace, a generic receiver).
"""

from pathlib import Path

import pytest
from tree_sitter import Node as TreeSitterNode

from sphinx_codelinks.analyse.entity import (
    EntityName,
    SemanticElement,
    describe_entity,
    is_doc_comment,
    name_chain,
    render_semantic,
    scope_language,
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


def _s(*components: tuple[str, ...]) -> tuple[SemanticElement, ...]:
    """``semantic`` from ``(kind, name)`` pairs; a third item is a Rust impl's trait."""
    elements: list[SemanticElement] = []
    for kind, name, *trait in components:
        element: SemanticElement = {"kind": kind, "name": name}
        if trait:
            element["trait"] = trait[0]
        elements.append(element)
    return tuple(elements)


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
            EntityName(
                "operator",
                "ns::W::operator==",
                _s(("namespace", "ns"), ("struct", "W"), ("operator", "operator==")),
            ),
            id="cpp-member-operator",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "struct W { W(); ~W(); };",
            "declaration",
            1,
            EntityName(
                "destructor", "W::~W", _s(("struct", "W"), ("destructor", "~W"))
            ),
            id="cpp-in-class-destructor",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "template <typename T> struct Box { template <typename U> void put(U u); };",
            "declaration",
            0,
            EntityName("method", "Box::put", _s(("struct", "Box"), ("method", "put"))),
            id="cpp-member-template-is-a-method",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "namespace { int hidden() { return 1; } }",
            "function_definition",
            0,
            EntityName(
                "function",
                "(anonymous namespace)::hidden",
                _s(("namespace", "(anonymous namespace)"), ("function", "hidden")),
            ),
            id="cpp-anonymous-namespace",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "enum class Color { Red };",
            "enum_specifier",
            0,
            EntityName("enum", "Color", _s(("enum", "Color"))),
            id="cpp-enum",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "namespace A.B;\nclass C { public static C operator +(C a, C b) => a; }",
            "operator_declaration",
            0,
            EntityName(
                "operator",
                "A.B.C.operator +",
                _s(
                    ("namespace", "A"),
                    ("namespace", "B"),
                    ("class", "C"),
                    ("operator", "operator +"),
                ),
            ),
            id="csharp-file-scoped-namespace-and-operator",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "class C { public int this[int i] => i; ~C() {} }",
            "indexer_declaration",
            0,
            EntityName(
                "indexer", "C.this[]", _s(("class", "C"), ("indexer", "this[]"))
            ),
            id="csharp-indexer",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "class C { ~C() {} }",
            "destructor_declaration",
            0,
            EntityName("destructor", "C.~C", _s(("class", "C"), ("destructor", "~C"))),
            id="csharp-destructor",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "class C { void M() { int local() => 1; } }",
            "local_function_statement",
            0,
            EntityName(
                "function",
                "C.M.local",
                _s(("class", "C"), ("method", "M"), ("function", "local")),
            ),
            id="csharp-local-function",
        ),
        pytest.param(
            CommentType.go,
            "go",
            "package p\nfunc (w *Widget[T]) Area() int { return 0 }\n",
            "method_declaration",
            0,
            EntityName(
                "method", "Widget.Area", _s(("type", "Widget"), ("method", "Area"))
            ),
            id="go-generic-pointer-receiver",
        ),
        pytest.param(
            CommentType.go,
            "go",
            "package p\ntype (\n\tA int\n\tB struct{}\n)\n",
            "type_declaration",
            0,
            EntityName("type", None, None),
            id="go-grouped-type-declaration-has-no-name",
        ),
        pytest.param(
            CommentType.go,
            "go",
            "package p\ntype I interface { M() int }\n",
            "method_elem",
            0,
            EntityName("method", "I.M", _s(("interface", "I"), ("method", "M"))),
            id="go-interface-method",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "mod m { pub struct G; impl crate::Shape for G { fn area(&self) {} } }",
            "function_item",
            0,
            EntityName(
                "method",
                "<m::G as Shape>::area",
                _s(("module", "m"), ("impl", "G", "Shape"), ("method", "area")),
            ),
            id="rust-trait-impl-in-module",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "impl Widget { fn new() -> Self { fn helper() {} Widget } }",
            "function_item",
            1,
            EntityName(
                "function",
                "Widget::new::helper",
                _s(("impl", "Widget"), ("method", "new"), ("function", "helper")),
            ),
            id="rust-function-in-inherent-method",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "mod a { mod b { trait Tr {} impl Tr for u32 {} impl G { fn new() {} } } }",
            "function_item",
            0,
            EntityName(
                "method",
                "a::b::G::new",
                _s(("module", "a"), ("module", "b"), ("impl", "G"), ("method", "new")),
            ),
            id="rust-impl-in-nested-modules",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "mod a { mod b { trait Tr {} impl Tr for u32 {} impl G { fn new() {} } } }",
            "impl_item",
            0,
            EntityName(
                "impl",
                "<u32 as a::b::Tr>",
                _s(("module", "a"), ("module", "b"), ("impl", "u32", "a::b::Tr")),
            ),
            id="rust-primitive-self-type-in-a-module-is-not-folded",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "mod k { impl crate::Q { fn q() {} } }",
            "function_item",
            0,
            EntityName(
                "method",
                "Q::q",
                _s(("module", "k"), ("impl", "crate::Q"), ("method", "q")),
            ),
            id="rust-crate-rooted-self-type-keeps-its-root",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "impl<T> Shape for Vec<T> {}",
            "impl_item",
            0,
            EntityName("impl", "<Vec<T> as Shape>", _s(("impl", "Vec<T>", "Shape"))),
            id="rust-generic-trait-impl-block",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "trait Shape { fn area(&self) -> f64; }",
            "function_signature_item",
            0,
            EntityName(
                "method", "Shape::area", _s(("trait", "Shape"), ("method", "area"))
            ),
            id="rust-required-trait-method",
        ),
        pytest.param(
            CommentType.python,
            "py",
            "class A:\n    def m(self):\n        def inner():\n            pass\n",
            "function_definition",
            1,
            EntityName(
                "function",
                "A.m.<locals>.inner",
                _s(("class", "A"), ("method", "m"), ("function", "inner")),
            ),
            id="python-locals",
        ),
        pytest.param(
            CommentType.ts,
            "ts",
            "namespace Gfx { export class W { draw(): void {} } }",
            "method_definition",
            0,
            EntityName(
                "method",
                "Gfx.W.draw",
                _s(("namespace", "Gfx"), ("class", "W"), ("method", "draw")),
            ),
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
        # The components of a name (``semantic``), as the data-model reply tabulates
        # them: a qualifier the syntax cannot classify is a ``scope``, the one right
        # before a member its ``class``.
        pytest.param(
            CommentType.cpp,
            "cpp",
            "void ns::W::f() {}",
            "function_definition",
            0,
            EntityName(
                "method",
                "ns::W::f",
                _s(("scope", "ns"), ("class", "W"), ("method", "f")),
            ),
            id="semantic-cpp-out-of-line-member",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "struct ns::W { void f(); };",
            "field_declaration",
            0,
            EntityName(
                "method",
                "ns::W::f",
                _s(("scope", "ns"), ("struct", "W"), ("method", "f")),
            ),
            id="semantic-cpp-qualified-class-name",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "namespace a::b { void f(); }",
            "declaration",
            0,
            EntityName(
                "function",
                "a::b::f",
                _s(("namespace", "a"), ("namespace", "b"), ("function", "f")),
            ),
            id="semantic-cpp-nested-namespace-definition",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "template <typename T> struct Box { T get(); };\n"
            "template <typename T> T Box<T>::get() { return T(); }",
            "function_definition",
            0,
            EntityName("method", "Box::get", _s(("class", "Box"), ("method", "get"))),
            id="semantic-cpp-class-template-member",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "template <> struct Box<bool> {};",
            "struct_specifier",
            0,
            EntityName("struct", "Box<bool>", _s(("struct", "Box<bool>"))),
            id="semantic-cpp-explicit-specialisation",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "void Box<std::string>::get() {}",
            "function_definition",
            0,
            EntityName(
                "method",
                "Box<std::string>::get",
                _s(("class", "Box<std::string>"), ("method", "get")),
            ),
            id="semantic-cpp-no-split-inside-template-arguments",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "W::operator std::string() const { return {}; }",
            "function_definition",
            0,
            EntityName(
                "operator",
                "W::operator std::string",
                _s(("class", "W"), ("operator", "operator std::string")),
            ),
            id="semantic-cpp-conversion-operator-qualifier-is-its-class",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "bool W::operator==(const W&) const { return true; }",
            "function_definition",
            0,
            EntityName(
                "operator",
                "W::operator==",
                _s(("scope", "W"), ("operator", "operator==")),
            ),
            id="semantic-cpp-operator-qualifier-is-a-scope",
        ),
        pytest.param(
            CommentType.cpp,
            "cpp",
            "TEST(LoginTest, RateLimited) { }",
            "function_definition",
            0,
            None,
            id="semantic-cpp-macro-defined-function-is-unnamed",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "impl Shape for Widget { fn area(&self) -> f64 { 0.0 } }",
            "function_item",
            0,
            EntityName(
                "method",
                "<Widget as Shape>::area",
                _s(("impl", "Widget", "Shape"), ("method", "area")),
            ),
            id="semantic-rust-trait-impl",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "impl dyn Shape { fn area(&self) -> f64 { 0.0 } }",
            "function_item",
            0,
            EntityName(
                "method",
                "<dyn Shape>::area",
                _s(("impl", "dyn Shape"), ("method", "area")),
            ),
            id="semantic-rust-impl-of-a-type-that-is-no-path",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "impl Box<dyn Fn(i32) -> u32> { fn call(&self) {} }",
            "function_item",
            0,
            EntityName(
                "method",
                "Box<dyn Fn(i32) -> u32>::call",
                _s(("impl", "Box<dyn Fn(i32) -> u32>"), ("method", "call")),
            ),
            id="semantic-rust-impl-of-a-generic-path",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "mod geo { trait Shape { fn area(&self) -> f64; } }",
            "function_signature_item",
            0,
            EntityName(
                "method",
                "geo::Shape::area",
                _s(("module", "geo"), ("trait", "Shape"), ("method", "area")),
            ),
            id="semantic-rust-trait-in-module",
        ),
        pytest.param(
            CommentType.rust,
            "rs",
            "fn outer() { fn inner() {} }",
            "function_item",
            1,
            EntityName(
                "function",
                "outer::inner",
                _s(("function", "outer"), ("function", "inner")),
            ),
            id="semantic-rust-function-in-function",
        ),
        pytest.param(
            CommentType.python,
            "py",
            "def outer():\n    def inner():\n        pass\n",
            "function_definition",
            1,
            EntityName(
                "function",
                "outer.<locals>.inner",
                _s(("function", "outer"), ("function", "inner")),
            ),
            id="semantic-python-nested-functions",
        ),
        pytest.param(
            CommentType.python,
            "py",
            "def f():\n    class C:\n        def m(self):\n            pass\n",
            "function_definition",
            1,
            EntityName(
                "method",
                "f.<locals>.C.m",
                _s(("function", "f"), ("class", "C"), ("method", "m")),
            ),
            id="semantic-python-class-in-function",
        ),
        pytest.param(
            CommentType.cs,
            "cs",
            "namespace Acme.Gfx { class Widget { void Draw() {} } }",
            "method_declaration",
            0,
            EntityName(
                "method",
                "Acme.Gfx.Widget.Draw",
                _s(
                    ("namespace", "Acme"),
                    ("namespace", "Gfx"),
                    ("class", "Widget"),
                    ("method", "Draw"),
                ),
            ),
            id="semantic-csharp-dotted-namespace",
        ),
        pytest.param(
            CommentType.ts,
            "ts",
            "namespace A.B { function f() {} }",
            "function_declaration",
            0,
            EntityName(
                "function",
                "A.B.f",
                _s(("namespace", "A"), ("namespace", "B"), ("function", "f")),
            ),
            id="semantic-typescript-dotted-namespace",
        ),
        pytest.param(
            CommentType.ts,
            "js",
            "module.exports.f = function () {};",
            "assignment_expression",
            0,
            EntityName(
                "function", "module.exports.f", _s(("function", "module.exports.f"))
            ),
            id="semantic-javascript-assignment-is-one-component",
        ),
        pytest.param(
            CommentType.yaml,
            "yaml",
            "a:\n  - b\n",
            "block_sequence_item",
            0,
            EntityName("item", None, None),
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
    """``describe_entity`` names the node: its kind, its name within the file, and
    that name's components, which render to it."""
    assert _describe(source, comment_type, suffix, kind, index) == expected
    if expected is not None:
        language = scope_language(comment_type, Path(f"case.{suffix}"))
        assert render_semantic(expected.semantic, language) == expected.qualified_name


@pytest.mark.parametrize(
    ("language", "semantic", "expected"),
    [
        pytest.param("cpp", None, None, id="no-components"),
        pytest.param(
            "cpp",
            _s(("scope", "ns"), ("class", "W"), ("method", "f")),
            "ns::W::f",
            id="cpp",
        ),
        pytest.param(
            "c",
            _s(("struct", "point"), ("function", "f")),
            "point::f",
            id="c-renders-as-cpp",
        ),
        pytest.param(
            "rust",
            _s(("impl", "a::Widget<T>"), ("method", "new")),
            "a::Widget<T>::new",
            id="rust-path-self-type",
        ),
        pytest.param(
            "rust",
            _s(("impl", "&'a str"), ("method", "len")),
            "<&'a str>::len",
            id="rust-reference-self-type",
        ),
        pytest.param(
            "rust",
            _s(("impl", "[u8]")),
            "<[u8]>",
            id="rust-slice-self-type",
        ),
        pytest.param(
            "rust",
            _s(("impl", "fn(i32) -> i32")),
            "<fn(i32) -> i32>",
            id="rust-function-self-type",
        ),
        pytest.param(
            "rust",
            _s(("impl", "dyn Shape", "Debug"), ("method", "fmt")),
            "<dyn Shape as Debug>::fmt",
            id="rust-trait-impl",
        ),
        pytest.param(
            "rust",
            _s(("module", "a"), ("trait", "impl")),
            "a::impl",
            id="rust-only-an-impl-component-is-bracketed",
        ),
        pytest.param(
            "rust",
            _s(("module", "a"), ("module", "b"), ("impl", "G"), ("method", "new")),
            "a::b::G::new",
            id="rust-modules-fold-into-a-bare-self-type",
        ),
        pytest.param(
            "rust",
            _s(("module", "m"), ("impl", "Vec<T>", "m::Tr")),
            "<m::Vec<T> as m::Tr>",
            id="rust-modules-fold-into-a-generic-self-type",
        ),
        pytest.param(
            "rust",
            _s(("module", "m"), ("impl", "x::P"), ("method", "new")),
            "x::P::new",
            id="rust-a-path-self-type-is-not-folded",
        ),
        pytest.param(
            "rust",
            _s(("module", "m"), ("impl", "u32", "m::Tr")),
            "<u32 as m::Tr>",
            id="rust-a-primitive-self-type-is-not-folded",
        ),
        pytest.param(
            "rust",
            _s(("module", "m"), ("impl", "dyn Shape"), ("method", "f")),
            "<dyn Shape>::f",
            id="rust-a-non-path-self-type-is-not-folded",
        ),
        pytest.param(
            "rust",
            _s(("module", "k"), ("impl", "crate::Q"), ("method", "q")),
            "Q::q",
            id="rust-a-crate-rooted-self-type-drops-its-root",
        ),
        pytest.param(
            "python",
            _s(("class", "A"), ("method", "m"), ("class", "B"), ("function", "g")),
            "A.m.<locals>.B.g",
            id="python-locals-after-a-method",
        ),
        pytest.param(
            "python",
            _s(("function", "f")),
            "f",
            id="python-no-locals-after-the-last",
        ),
        pytest.param(
            "go",
            _s(("type", "Widget"), ("method", "Draw")),
            "Widget.Draw",
            id="go",
        ),
        pytest.param(
            "ts",
            _s(("namespace", "A"), ("function", "module.exports.f")),
            "A.module.exports.f",
            id="typescript",
        ),
    ],
)
def test_render_semantic(
    language: str,
    semantic: tuple[SemanticElement, ...] | None,
    expected: str | None,
) -> None:
    """Each language's rule for spelling components as a qualified name."""
    assert render_semantic(semantic, language) == expected


@pytest.mark.parametrize(
    ("comment_type", "filename", "expected"),
    [
        (CommentType.cpp, "a.c", "c"),
        (CommentType.cpp, "a.C", "cpp"),
        (CommentType.cpp, "a.h", "cpp"),
        (CommentType.cpp, "a.cpp", "cpp"),
        (CommentType.cpp, "a.hpp", "cpp"),
        (CommentType.cpp, "a.ci", "cpp"),
        (CommentType.python, "a.py", "python"),
        (CommentType.cs, "a.cs", "cs"),
        (CommentType.ts, "a.js", "ts"),
        (CommentType.ts, "a.tsx", "ts"),
        (CommentType.rust, "a.rs", "rust"),
        (CommentType.go, "a.go", "go"),
        (CommentType.yaml, "a.yml", "yaml"),
        (CommentType.jsonc, "a.json", "jsonc"),
        (CommentType.bash, "a.sh", "bash"),
    ],
)
def test_scope_language(
    comment_type: CommentType, filename: str, expected: str
) -> None:
    """The language a file is analysed as, by its name: ``c`` for a ``.c`` file
    (lowercase: compilers read ``.C`` as C++), ``cpp`` for every other C and C++ file,
    a header included, else the comment type."""
    assert scope_language(comment_type, Path(filename)) == expected


def test_name_chain() -> None:
    """A name chain drops the kinds and keeps every other key, sorted, and in Python
    the ``<locals>`` boundary the rendering writes."""
    assert name_chain(None, "cpp") is None
    assert name_chain(_s(("namespace", "ns"), ("method", "f")), "cpp") == (
        (("name", "ns"),),
        (("name", "f"),),
    )
    assert name_chain(_s(("impl", "W", "Shape"), ("method", "area")), "rust") == (
        (("name", "W"), ("trait", "Shape")),
        (("name", "area"),),
    )
    assert name_chain(_s(("namespace", "ns"), ("method", "f")), "cpp") == name_chain(
        _s(("scope", "ns"), ("function", "f")), "cpp"
    )
    nested_class = _s(("class", "A"), ("class", "f"), ("method", "g"))
    in_a_method = _s(("class", "A"), ("method", "f"), ("function", "g"))
    assert name_chain(in_a_method, "python") == (
        (("name", "A"),),
        (("name", "f"),),
        (("name", "<locals>"),),
        (("name", "g"),),
    )
    assert name_chain(nested_class, "python") != name_chain(in_a_method, "python")
    # only Python writes the boundary
    assert name_chain(in_a_method, "rust") == name_chain(nested_class, "rust")


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
