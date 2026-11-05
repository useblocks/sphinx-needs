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
        # A function a ``friend`` declaration declares or defines is named in its
        # innermost enclosing namespace, not in the class (a qualified friend by its
        # qualifier); every other member keeps its class.
        pytest.param(
            "namespace ns { struct A { friend void f(A) {} }; }",
            "function_definition",
            0,
            "function",
            "ns::f",
            ["namespace ns", "function f"],
            id="friend_definition",
        ),
        pytest.param(
            "namespace ns { struct A { friend bool operator==(const A&, const A&)"
            " { return true; } }; }",
            "function_definition",
            0,
            "operator",
            "ns::operator==",
            ["namespace ns", "operator operator=="],
            id="friend_operator",
        ),
        pytest.param(
            "namespace ns { struct A { template <typename T> friend void g(T) {} }; }",
            "function_definition",
            0,
            "function",
            "ns::g",
            ["namespace ns", "function g"],
            id="friend_template",
        ),
        pytest.param(
            "namespace ns { struct A { friend void h(A); }; }",
            "declaration",
            0,
            "function",
            "ns::h",
            ["namespace ns", "function h"],
            id="friend_declaration",
        ),
        pytest.param(
            "namespace ns { struct O { struct I { friend void f(I) {} }; }; }",
            "function_definition",
            0,
            "function",
            "ns::f",
            ["namespace ns", "function f"],
            id="friend_in_nested_class",
        ),
        pytest.param(
            "struct A { friend void f(A) {} };",
            "function_definition",
            0,
            "function",
            "f",
            ["function f"],
            id="friend_of_a_global_class",
        ),
        pytest.param(
            "namespace ns { struct Other { void h(); }; "
            "struct A { friend void Other::h(); }; }",
            "declaration",
            0,
            "method",
            "ns::Other::h",
            ["namespace ns", "class Other", "method h"],
            id="qualified_friend",
        ),
        pytest.param(
            "namespace ns { struct A { void m() {} friend void f(A) {} }; }",
            "function_definition",
            0,
            "method",
            "ns::A::m",
            ["namespace ns", "struct A", "method m"],
            id="member_beside_a_friend",
        ),
        # A specialisation's class name keeps its arguments, squeezed and without
        # comments (``P<T,4>``), in the class and in an out-of-line qualifier; an
        # out-of-line qualifier's arguments are dropped only when they are exactly the
        # template's own parameter names (the primary's member, ``Box::get``).
        pytest.param(
            "template <typename T, int N> struct P {};\ntemplate <typename T> struct P<T, 4> { void fill(); };",
            "field_declaration",
            0,
            "method",
            "P<T,4>::fill",
            ["struct P<T,4>", "method fill"],
            id="partial_specialisation_member",
        ),
        pytest.param(
            "template <typename T, int N> struct P {};\ntemplate <typename T> struct P<T, 4> { P(); };",
            "declaration",
            0,
            "constructor",
            "P<T,4>::P",
            ["struct P<T,4>", "constructor P"],
            id="partial_specialisation_constructor",
        ),
        pytest.param(
            "template <typename T, int N> struct P {};\ntemplate <typename T> struct P<T, 4> {};",
            "struct_specifier",
            1,
            "struct",
            "P<T,4>",
            ["struct P<T,4>"],
            id="partial_specialisation_itself",
        ),
        pytest.param(
            "template <typename T, int N> struct P {};\ntemplate <typename T> struct P<T, /* four */ 4> { void fill(); };",
            "field_declaration",
            0,
            "method",
            "P<T,4>::fill",
            ["struct P<T,4>", "method fill"],
            id="comment_in_arguments",
        ),
        pytest.param(
            "template <typename T, int N> struct P {};\ntemplate <typename T> struct P<T, // four\n  4> { void fill(); };",
            "field_declaration",
            0,
            "method",
            "P<T,4>::fill",
            ["struct P<T,4>", "method fill"],
            id="line_comment_in_arguments",
        ),
        pytest.param(
            "template <> struct Box<bool> { bool get(); };",
            "field_declaration",
            0,
            "method",
            "Box<bool>::get",
            ["struct Box<bool>", "method get"],
            id="explicit_specialisation_member",
        ),
        pytest.param(
            "template <> struct Box<bool /* flag */> { bool get(); };",
            "field_declaration",
            0,
            "method",
            "Box<bool>::get",
            ["struct Box<bool>", "method get"],
            id="explicit_specialisation_comment",
        ),
        pytest.param(
            "template <typename T> void P<T, 4>::fill() {}",
            "function_definition",
            0,
            "method",
            "P<T,4>::fill",
            ["class P<T,4>", "method fill"],
            id="partial_specialisation_member_out_of_line",
        ),
        pytest.param(
            "template <typename T> P<T, 4>::P() {}",
            "function_definition",
            0,
            "constructor",
            "P<T,4>::P",
            ["class P<T,4>", "constructor P"],
            id="partial_specialisation_constructor_out_of_line",
        ),
        pytest.param(
            "template <typename T> void Box<T>::get() {}",
            "function_definition",
            0,
            "method",
            "Box::get",
            ["class Box", "method get"],
            id="primary_member_out_of_line",
        ),
        pytest.param(
            "template <typename T, int N> void P<T, N>::fill() {}",
            "function_definition",
            0,
            "method",
            "P::fill",
            ["class P", "method fill"],
            id="primary_member_two_parameters",
        ),
        pytest.param(
            "template <typename... Ts> void V<Ts...>::f() {}",
            "function_definition",
            0,
            "method",
            "V::f",
            ["class V", "method f"],
            id="primary_member_of_a_pack",
        ),
        pytest.param(
            "template <typename T> template <typename U> void A<T>::f(U) {}",
            "function_definition",
            0,
            "method",
            "A::f",
            ["class A", "method f"],
            id="member_template_of_a_class_template",
        ),
        pytest.param(
            "template <> void Box<int>::get() {}",
            "function_definition",
            0,
            "method",
            "Box<int>::get",
            ["class Box<int>", "method get"],
            id="explicit_specialisation_member_out_of_line",
        ),
        pytest.param(
            "void Box<int>::get() {}",
            "function_definition",
            0,
            "method",
            "Box<int>::get",
            ["class Box<int>", "method get"],
            id="explicit_specialisation_member_no_header",
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
            "namespace ns {\nclass List { public: class iterator {\n"
            "  friend bool operator==(const iterator& a, const iterator& b)"
            " { return true; } }; };\n"
            "class Map { public: class iterator {\n"
            "  friend bool operator==(const iterator& a, const iterator& b)"
            " { return false; } }; };\n}\n",
            {
                "ns::List::iterator::operator==(const iterator&, const iterator&)",
                "ns::Map::iterator::operator==(const iterator&, const iterator&)",
            },
            id="hidden_friends_of_two_classes",
        ),
        pytest.param(
            "namespace lib {\nstruct Vec  { struct iterator { friend bool operator==("
            "const iterator&, const iterator&) { return true; } }; };\n"
            "struct List { struct iterator { friend bool operator==("
            "const iterator&, const iterator&) { return true; } }; };\n}\n",
            {
                "lib::List::iterator::operator==(const iterator&, const iterator&)",
                "lib::Vec::iterator::operator==(const iterator&, const iterator&)",
            },
            id="hidden_friends_of_two_structs",
        ),
        pytest.param(
            "namespace ns {\ntemplate <typename T> struct A {\n  using Self = A;\n"
            "  friend void swap(Self& a, Self& b) {}\n};\n"
            "template <typename T> struct B {\n  using Self = B;\n"
            "  friend void swap(Self& a, Self& b) {}\n};\n}\n",
            {"ns::A::swap(Self&, Self&)", "ns::B::swap(Self&, Self&)"},
            id="self_aliases",
        ),
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
        pytest.param(
            "namespace ns {\nstruct S {\n  friend void reset(S& s);\n};\n"
            "void reset(S& s) {}\n}\n",
            {"ns::reset(S&)"},
            id="friend_declaration_and_definition",
        ),
        pytest.param(
            "namespace ns {\nstruct A {\n  friend bool operator==(const A&, const A&);\n"
            "};\nbool operator==(const A&, const A&) { return true; }\n}\n",
            {"ns::operator==(const A&, const A&)"},
            id="friend_declared_in_its_class",
        ),
    ],
)
def test_names_that_would_collide_keep_their_full_chain(
    source: str, expected: set[str]
) -> None:
    """Leaving an inline namespace or a friend's classes out of a name never makes two
    definitions of a file share one: where it would, every entity of that name and
    parameters keeps its full chain, as before they were left out (hidden friends of
    two classes, ``Self`` aliases, two inline siblings, an inline namespace beside its
    parent, the ``#if``/``#else`` arms of an ABI version, a declaration with its
    group); where it would not, the name is clang's (a friend declared in its class and
    defined in its namespace is one function)."""
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


def test_a_marker_in_a_colliding_hidden_friend_keeps_its_class(tmp_path: Path) -> None:
    """A marker in one of two classes' hidden friends of one name and parameters is
    named with its class, so it never credits the other class's function; a hidden
    friend of one class alone, and a friend declared in its class and defined in its
    namespace, are named in the namespace. (A marker before a ``friend`` declaration
    is attached to its class: the attachment does not look into one.)"""
    source = (
        "namespace ns {\nclass List { public: class iterator {\n"
        "friend bool operator==(const iterator& a, const iterator& b) { return true; }"
        " }; };\n"
        "class Map { public: class iterator {\n"
        "friend bool operator==(const iterator& a, const iterator& b) {\n"
        "// @need-ids: REQ_M\n    return false;\n  } }; };\n"
        "struct T {\n  friend void touch(T& t) {\n    // @need-ids: REQ_T\n  }\n};\n"
        "struct S {\n  // @need-ids: REQ_S\n  friend void reset(S& s);\n};\n"
        "// @need-ids: REQ_E\nvoid reset(S& s) {}\n}\n"
    )
    assert _marker_names(tmp_path, source) == {
        "REQ_M": "ns::Map::iterator::operator==",
        "REQ_T": "ns::touch",
        "REQ_S": "ns::S",
        "REQ_E": "ns::reset",
    }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "template <typename... Ts> struct List { int size() const; };\n"
            "template <typename... Ts> int List<Ts...>::size() const { return 0; }\n"
            "template <typename Head, typename... Tail> struct List<Head, Tail...> {\n"
            "  int size() const;\n};\n"
            "template <typename Head, typename... Tail>"
            " int List<Head, Tail...>::size() const { return 1; }\n",
            {"List::size() const", "List<Head,Tail...>::size() const"},
            id="typelist",
        ),
        pytest.param(
            "template <class T, class U, class V = int> struct Q { void m(); };\n"
            "template <class T, class U, class V> void Q<T, U, V>::m() {}\n"
            "template <class T, class U> struct Q<T, U> { void m(); };\n"
            "template <class T, class U> void Q<T, U>::m() {}\n",
            {"Q::m()", "Q<T,U>::m()"},
            id="primary_with_a_default",
        ),
        pytest.param(
            "template <typename T, typename U = void> struct Q { void m(); };\n"
            "template <typename T, typename U> void Q<T, U>::m() {}\n"
            "template <typename T> struct Q<T*, void> { void m(); };\n"
            "template <typename T> void Q<T*, void>::m() {}\n"
            "template <typename T> void Q<T *, void>::m();\n",
            {"Q::m()", "Q<T*,void>::m()"},
            id="pointer_partial_and_a_redeclaration",
        ),
        pytest.param(
            "namespace std { template <class A, class B> struct pair {}; }\n"
            "template <typename T, int N> struct P { void fill(); };\n"
            "template <typename T> struct P<T, 4> {\n  void fill();\n"
            "  template <typename U> void put(U);\n  void inl() {}\n};\n"
            "template <typename T> void P<T, 4>::fill() {}\n"
            "template <typename T> template <typename U> void P<T, 4>::put(U) {}\n"
            "template <typename T, int N> void P<T, N>::fill() {}\n"
            "template <typename A, typename B> struct P<std::pair<A, B>, 2>"
            " { void fill(); };\n"
            "template <typename A, typename B> void P<std::pair<A,B>, 2>::fill() {}\n",
            {
                "P::fill()",
                "P<T,4>::fill()",
                "P<T,4>::inl()",
                "P<T,4>::put(U)",
                "P<std::pair<A,B>,2>::fill()",
            },
            id="partial_members",
        ),
        pytest.param(
            "template <typename T> struct Box { void get(); };\n"
            "template <typename X> void Box<X>::get() {}\n"
            "template <> void Box<int>::get() {}\n"
            "template <typename T> struct W { struct In { void m(); }; };\n"
            "template <typename T> void W<T>::In::m() {}\n"
            "template <typename T, typename U> struct Pair2 { void m(); };\n"
            "template <typename U, typename T> void Pair2<U, T>::m() {}\n"
            "template <typename T> struct Outer"
            " { template <typename U> struct Inner { void m(); }; };\n"
            "template <typename T> template <typename U>"
            " void Outer<T>::Inner<U>::m() {}\n",
            {
                "Box::get()",
                "Box<int>::get()",
                "Outer::Inner::m()",
                "Pair2::m()",
                "W::In::m()",
            },
            id="primary_members",
        ),
        pytest.param(
            "template <typename T, int N> struct P {};\n"
            "template <typename T> struct P<T, 4> {\n  void fill();\n};\n"
            "template <typename T> void P<T, 4>::fill() {}\n",
            {"P<T,4>::fill()"},
            id="partial_specialisation_member",
        ),
        pytest.param(
            "template <typename T> struct Box {\n  void get();\n};\n"
            "template <typename T> void Box<T>::get() {}\n",
            {"Box::get()"},
            id="primary_member",
        ),
        pytest.param(
            "template <typename T> struct Box {};\n"
            "template <> struct Box<int> {\n  void get();\n};\n"
            "void Box<int>::get() {}\n",
            {"Box<int>::get()"},
            id="explicit_specialisation_member",
        ),
        pytest.param(
            "template <typename T, int N> struct P {};\n"
            "template <typename T> struct P<T, 4> {\n  void fill();\n};\n"
            "template <typename U> void P<U, 4>::fill() {}\n",
            {"P<T,4>::fill()"},
            id="renamed_partial_specialisation_member",
        ),
        pytest.param(
            "template <typename T> struct Outer {};\n"
            "template <> struct Outer<int> {\n"
            "  template <typename U> struct Inner {\n    void n();\n  };\n};\n"
            "template <typename U> void Outer<int>::Inner<U>::n() {}\n",
            {"Outer<int>::Inner::n()"},
            id="member_template_of_an_explicit_specialisation",
        ),
    ],
)
def test_a_specialisation_member_is_named_alike_in_and_out_of_its_class(
    source: str, expected: set[str]
) -> None:
    """A member of a partial specialisation is named with its arguments in the class
    and out of line (``P<T,4>::fill``), a primary template's member without them both
    times (``Box::get``), an explicit specialisation's with them both times; out of
    line, a qualifier the same as a partial specialisation of the file but for its
    parameter names is spelled as that specialisation (renamed parameters, a typelist's
    head and tail, a primary with a defaulted parameter); and an explicit
    specialisation's qualifier (``Outer<int>``) takes no template header. So a
    declaration and its definition share a name."""
    assert _functions(source) == expected


def test_a_marker_on_a_partial_specialisation_member(tmp_path: Path) -> None:
    """A marker in a partial specialisation's class, and one on its out-of-line
    definition written with other parameter names, name one member, apart from the
    primary template's."""
    source = (
        "template <typename T, int N> struct P {\n  // @need-ids: REQ_P\n"
        "  void fill();\n};\n"
        "template <typename T> struct P<T, 4> {\n  // @need-ids: REQ_D\n"
        "  void fill();\n};\n"
        "// @need-ids: REQ_U\ntemplate <typename U> void P<U, 4>::fill() {}\n"
        "template <typename... Ts> struct L { int size() const; };\n"
        "template <typename Head, typename... Tail> struct L<Head, Tail...> {\n"
        "  // @need-ids: REQ_S\n  int size() const;\n};\n"
        "template <typename H, typename... T> int L<H, T...>::size() const"
        " { return 1; }\n"
    )
    assert _marker_names(tmp_path, source) == {
        "REQ_P": "P::fill",
        "REQ_D": "P<T,4>::fill",
        "REQ_U": "P<T,4>::fill",
        "REQ_S": "L<Head,Tail...>::size",
    }
