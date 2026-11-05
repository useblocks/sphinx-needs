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

from sphinx_codelinks.analyse import entity, utils
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


def _functions(
    source: str, path: str = "src/a.cpp", *, which: bool = False
) -> set[str]:
    """Every function of ``source`` (definition or declaration) as the file names it,
    with its normalised parameters: what tells two of them apart; after ``def `` or
    ``decl `` when ``which``."""
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
        named = names.qualify(name, node.start_point.row + 1)
        spelled = f"{named.qualified_name}{cpp_signature(node, names.source)}"
        if which:
            kind = "def" if node.type == "function_definition" else "decl"
            spelled = f"{kind} {spelled}"
        found.add(spelled)
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
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nstruct Widget { void draw() {} };\n}\n"
            "struct Widget { void resize() {} };\n}\n",
            {"lib::Widget::resize()", "lib::v1::Widget::draw()"},
            id="a_kept_class_keeps_its_members",
        ),
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nnamespace detail { void a() {} }\n}\n"
            "inline namespace v2 {\nnamespace detail { void b() {} }\n}\n}\n",
            {"lib::v1::detail::a()", "lib::v2::detail::b()"},
            id="a_kept_namespace_keeps_its_members",
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
    defined in its namespace is one function). Everything a class or namespace that
    keeps its full chain holds keeps it too."""
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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nvoid f(int);\n}\n}\n"
            "void lib::v1::f(int) {}\n",
            {"decl lib::f(int)", "def lib::f(int)"},
            id="one_definition",
        ),
        pytest.param(
            "namespace lib::inline v3 {\nvoid z(int);\n}\nvoid lib::v3::z(int) {}\n",
            {"decl lib::z(int)", "def lib::z(int)"},
            id="a_nested_inline_part",
        ),
        pytest.param(
            "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
            "LIB_NAMESPACE_BEGIN\ninline namespace v1 {\nvoid f(int);\n}\n"
            "LIB_NAMESPACE_END\nvoid lib::v1::f(int) {}\n",
            {"decl lib::f(int)", "def lib::f(int)"},
            id="in_a_namespace_the_file_s_macro_opens",
        ),
        pytest.param(
            "namespace lib {\n#if LIB_V2\ninline namespace v2 { void g(); }\n#else\n"
            "inline namespace v1 { void g() {} }\n#endif\n}\n"
            "#if LIB_V2\nvoid lib::v2::g() {}\n#endif\n",
            {"decl lib::v2::g()", "def lib::v1::g()", "def lib::v2::g()"},
            id="abi_version_arms_out_of_line",
        ),
        pytest.param(
            "namespace lib {\ninline namespace v1 { void g(); }\n"
            "inline namespace v2 { void g(); }\n}\n"
            "void lib::v1::g() {}\nvoid lib::v2::g() {}\n",
            {
                "decl lib::v1::g()",
                "decl lib::v2::g()",
                "def lib::v1::g()",
                "def lib::v2::g()",
            },
            id="two_inline_siblings_out_of_line",
        ),
        pytest.param(
            "namespace lib {\nvoid g() {}\ninline namespace v1 { void g(); }\n}\n"
            "void lib::v1::g() {}\n",
            {"decl lib::v1::g()", "def lib::g()", "def lib::v1::g()"},
            id="inline_beside_its_parent_out_of_line",
        ),
        pytest.param(
            "namespace lib {\ninline namespace v1 {\nstruct Widget { void draw(); };\n}\n"
            "struct Widget { void resize() {} };\n}\nvoid lib::v1::Widget::draw() {}\n",
            {
                "decl lib::v1::Widget::draw()",
                "def lib::Widget::resize()",
                "def lib::v1::Widget::draw()",
            },
            id="a_member_of_a_kept_class_out_of_line",
        ),
        pytest.param(
            "namespace lib { inline namespace v2 { struct X; } }\n"
            "struct lib::v2::X {\n  void m();\n};\nvoid lib::v2::X::m() {}\n",
            {"decl lib::X::m()", "def lib::X::m()"},
            id="a_class_head",
        ),
        pytest.param(
            "namespace lib { inline namespace v1 { struct X {\n  void m() {} }; }\n"
            "inline namespace v2 { struct X; } }\nstruct lib::v2::X {\n  void m();\n};\n"
            "void lib::v2::X::m() {}\n",
            {"decl lib::v2::X::m()", "def lib::v1::X::m()", "def lib::v2::X::m()"},
            id="a_class_head_beside_a_colliding_sibling",
        ),
        pytest.param(
            "namespace lib { inline namespace v1 { struct Widget { struct Impl;\n"
            "  void draw(); }; } }\n"
            "struct lib::v1::Widget::Impl {\n  void run();\n};\n"
            "void lib::v1::Widget::Impl::run() {}\nvoid lib::v1::Widget::draw() {}\n",
            {
                "decl lib::Widget::Impl::run()",
                "decl lib::Widget::draw()",
                "def lib::Widget::Impl::run()",
                "def lib::Widget::draw()",
            },
            id="a_pimpl_class_head",
        ),
        pytest.param(
            "namespace lib { inline namespace v1 { struct W {\n"
            "  operator int() const; }; } }\n"
            "lib::v1::W::operator int() const { return 0; }\n",
            {
                "decl lib::W::operator int() const",
                "def lib::W::operator int() const",
            },
            id="a_conversion_operator",
        ),
        pytest.param(
            "namespace lib { inline namespace v1 {\n"
            "template <class T, int N> struct P { void fill(); };\n"
            "template <class T> struct P<T, 4> {\n  void fill(); }; } }\n"
            "template <class U> void lib::v1::P<U, 4>::fill() {}\n",
            {
                "decl lib::P::fill()",
                "decl lib::P<T,4>::fill()",
                "def lib::P<T,4>::fill()",
            },
            id="a_partial_specialisation_with_other_names",
        ),
        pytest.param(
            "namespace lib { inline namespace v1 {\n"
            "template <class T, int N> struct P { void fill(); };\n"
            "template <class T> struct P<T, 4> {\n  void fill(); }; } }\n"
            "template <class T> void lib::v1::P<T, 4>::fill() {}\n",
            {
                "decl lib::P::fill()",
                "decl lib::P<T,4>::fill()",
                "def lib::P<T,4>::fill()",
            },
            id="a_partial_specialisation_with_the_same_names",
        ),
    ],
)
def test_a_qualifier_through_an_inline_namespace_leaves_it_out(
    source: str, expected: set[str]
) -> None:
    """A qualifier written through an inline namespace of the file leaves it out, as
    clang names the function (``void lib::v1::f(int) {}`` is ``lib::f``, named as its
    declaration is), and the function is one that leaves a container out: where that
    would give two definitions one name and parameters, it keeps the qualifier as
    written, so a declaration never names another definition (the ``#if``/``#else``
    arms of an ABI version with the definition out of line, two inline siblings, an
    inline namespace beside its parent), and a member of a class that keeps its full
    chain keeps it out of line too. Every written qualifier does so: a class head (its
    members follow it; the pimpl's ``Impl`` too), a conversion operator's, and the
    path a partial specialisation is looked up by."""
    assert _functions(source, which=True) == expected


@pytest.mark.parametrize(
    ("source", "inline"),
    [
        pytest.param("inline namespace v1 {}", True, id="inline"),
        pytest.param("namespace a::inline b {}", True, id="inline_part"),
        pytest.param("namespace a::inline b::c {}", True, id="inline_middle_part"),
        pytest.param("namespace lib {}", False, id="plain"),
        pytest.param("namespace pipeline {}", False, id="pipeline"),
        pytest.param("namespace inliner {}", False, id="inliner"),
        pytest.param("namespace baseline::inliner {}", False, id="nested_letters"),
    ],
)
def test_inline_is_a_token(source: str, inline: bool) -> None:
    """A namespace is inline, or has an inline part, by an ``inline`` token, as the
    parser reads it: a name that merely holds the letters (``inliner``) is neither, so
    nothing under it is named a second time."""
    parser, _ = utils.init_tree_sitter(CommentType.cpp, Path("a.cpp"))
    namespace = parser.parse(source.encode("utf-8")).root_node.named_children[0]
    assert namespace.type == "namespace_definition"
    assert entity._cpp_inline_namespace_or_part(namespace) == inline


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "template <typename... Ts> struct S;\n"
            "template <typename T, typename... Ts> struct S<T, Ts...> { void f() {} };\n"
            "template <typename T, typename U> struct S<T, U> { void f(); };\n"
            "template <typename A, typename B> void S<A, B>::f() {}\n",
            {"decl S<T,U>::f()", "def S<T,Ts...>::f()", "def S<T,U>::f()"},
            id="a_pack_is_not_a_plain_parameter",
        ),
        pytest.param(
            "template <typename... Ts> struct S;\n"
            "template <typename... Ts> struct S<int, Ts...> { void f() {} };\n"
            "template <typename T> struct S<int, T> { void f(); };\n"
            "template <typename A> void S<int, A>::f() {}\n",
            {"decl S<int,T>::f()", "def S<int,Ts...>::f()", "def S<int,T>::f()"},
            id="a_pack_after_a_fixed_argument",
        ),
        pytest.param(
            "template <class T, int N> struct P {};\n"
            "template <class T> struct P<T, 4>;\n"
            "template <class U> struct P<U, 4> { void fill(); };\n"
            "template <class V> void P<V, 4>::fill() {}\n",
            {"decl P<U,4>::fill()", "def P<U,4>::fill()"},
            id="a_forward_declaration_with_other_names",
        ),
        pytest.param(
            "template <typename T, int N> struct P {};\n"
            "template <typename T> struct P<T, 4>;\n"
            "template <typename U> struct P<U, 4> { void fill(); };\n"
            "template <typename U> void P<U, 4>::fill() {}\n",
            {"decl P<U,4>::fill()", "def P<U,4>::fill()"},
            id="a_forward_declaration_then_the_definition",
        ),
        pytest.param(
            "namespace ns1 {\ntemplate <class T, int N> struct P {};\n"
            "template <class T> struct P<T, 4> { void fill(); };\n}\n"
            "namespace ns2 {\ntemplate <class T, int N> struct P {};\n"
            "template <class U> struct P<U, 4> { void fill(); };\n}\n"
            "template <class V> void ns1::P<V, 4>::fill() {}\n"
            "template <class V> void ns2::P<V, 4>::fill() {}\n",
            {
                "decl ns1::P<T,4>::fill()",
                "decl ns2::P<U,4>::fill()",
                "def ns1::P<T,4>::fill()",
                "def ns2::P<U,4>::fill()",
            },
            id="two_namespaces",
        ),
        pytest.param(
            "struct A {\n  template <class T> struct In {};\n"
            "  template <class U> struct In<U*> { void m(); };\n};\n"
            "struct B {\n  template <class T> struct In {};\n"
            "  template <class W> struct In<W*> { void m(); };\n};\n"
            "template <class X> void A::In<X*>::m() {}\n"
            "template <class X> void B::In<X*>::m() {}\n",
            {
                "decl A::In<U*>::m()",
                "decl B::In<W*>::m()",
                "def A::In<U*>::m()",
                "def B::In<W*>::m()",
            },
            id="two_classes_members",
        ),
        pytest.param(
            "template <class T> struct Outer"
            " { template <class U> struct Inner { void n(); }; };\n"
            "template <> template <class U> void Outer<int>::Inner<U>::n() {}\n",
            {"decl Outer::Inner::n()", "def Outer<int>::Inner::n()"},
            id="an_explicit_specialisation_s_empty_header",
        ),
        pytest.param(
            "template <class T, int N> struct P {};\n#if A\n"
            "template <class T> struct P<T, 4> { void fill(); };\n#else\n"
            "template <class U> struct P<U, 4> { void fill(); };\n#endif\n"
            "template <class V> void P<V, 4>::fill() {}\n",
            {"decl P<T,4>::fill()", "decl P<U,4>::fill()", "def P<V,4>::fill()"},
            id="two_spellings_in_two_arms_spell_nothing",
        ),
    ],
)
def test_a_qualifier_takes_one_partial_specialisation_s_spelling(
    source: str, expected: set[str]
) -> None:
    """An out-of-line qualifier is spelled as a partial specialisation of the file only
    when exactly one with a body is the same but for its parameter names, in the same
    scope: a pack is not a plain parameter (``S<A,B>`` is ``S<T,U>``'s, never
    ``S<T,Ts...>``'s), a forward declaration never sets the spelling, and two
    namespaces' or two classes' specialisations of the same name never share one; where
    the matching ones with a body spell it two ways (the arms of an ``#if``), none does
    and the qualifier keeps its own arguments. An explicit specialisation's empty
    ``template <>`` is its own, so the header after it reaches the next qualifier."""
    assert _functions(source, which=True) == expected


def test_a_deeply_nested_parameter_type_is_named() -> None:
    """A parameter type nested 400 deep (``A<A<…<int>…>>``) in two functions that
    would share a name and parameters: their signatures are worked out without
    exhausting Python's recursion limit, and the two keep their inline namespaces."""
    nested = "A<" * 400 + "int" + " >" * 400
    source = (
        f"template <class T> struct A {{}};\nnamespace lib {{\n"
        f"inline namespace v1 {{ void h({nested} x) {{}} }}\n"
        f"inline namespace v2 {{ void h({nested} x) {{}} }}\n}}\n"
    )
    root, names = _parsed(source)
    named = []
    for node in _nodes_of(root, "function_definition"):
        name = describe_entity(node, CommentType.cpp, source=names.source)
        assert name is not None
        named.append(names.qualify(name, node.start_point.row + 1).qualified_name)
    assert named == ["lib::v1::h", "lib::v2::h"]
