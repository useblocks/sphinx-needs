"""In-file C++ namespace macros (``analyse/cpp_macros.py``): the rules F1-F10 on the
text alone, then F7 on the tree, and the names they give a marker's entity end to end.

Another implementation of the same naming holds the same cases.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import Any

import pytest
from tree_sitter import Node as TreeSitterNode

from sphinx_codelinks.analyse import cpp_macros, utils
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.cpp_macros import CLOSING, OPENING, prepare
from sphinx_codelinks.analyse.entity import CppNames, describe_entity, is_entity
from sphinx_codelinks.analyse.references import need_id_ref_records
from sphinx_codelinks.config import SourceAnalyseConfig
from sphinx_codelinks.source_discover.config import CommentType


def _file(opening: str, closing: str, body: str) -> str:
    """An opening and a closing macro, and a file using them around ``body``."""
    return (
        f"#define LIB_NAMESPACE_BEGIN {opening}\n#define LIB_NAMESPACE_END {closing}\n"
        f"LIB_NAMESPACE_BEGIN\n{body}\nLIB_NAMESPACE_END\n"
    )


def _opened(source: str) -> list[list[str]]:
    """The named namespaces of each pair ``prepare`` accepts in ``source``."""
    return [
        list(pair.namespaces) for pair in prepare(source.encode("utf-8")).scopes.pairs
    ]


@pytest.mark.parametrize(
    ("opening", "closing", "expected"),
    [
        pytest.param("namespace lib {", "}", ["lib"], id="one"),
        pytest.param("namespace a::b {", "}", ["a", "b"], id="nested_name"),
        pytest.param("namespace a { namespace b {", "}}", ["a", "b"], id="two_openers"),
        pytest.param(
            "namespace lib { inline namespace v1 {", "}}", ["lib"], id="inline_elided"
        ),
        pytest.param(
            "namespace lib { inline namespace LIB_ABI_TAG(v1, 2) {",
            "} }",
            ["lib"],
            id="inline_named_by_a_macro_call",
        ),
        pytest.param(
            "\\\n    namespace lib /* the library */ \\\n    { // opened\n",
            "}",
            ["lib"],
            id="continuation_and_comments",
        ),
        pytest.param("inline namespace v1 {", "}", [], id="only_inline"),
    ],
)
def test_an_opening_body_names_its_namespaces(
    opening: str, closing: str, expected: list[str]
) -> None:
    """F2: what an opening body may be, and the named namespaces it opens (an inline
    one's name is left out; a continuation and comments are read through)."""
    assert _opened(_file(opening, closing, "void f() {}")) == [expected]


@pytest.mark.parametrize(
    ("opening", "closing"),
    [
        pytest.param("namespace lib { int x;", "}", id="extra_tokens"),
        pytest.param("namespace LIB {", "}", id="all_capitals"),
        pytest.param("namespace {", "}", id="anonymous"),
        pytest.param('extern "C" {', "}", id="extern_c"),
        pytest.param("namespace [[deprecated]] lib {", "}", id="attribute"),
        pytest.param("namespace lib {", "};", id="closing_with_more"),
        pytest.param("", "}", id="empty"),
    ],
)
def test_a_body_that_is_not_an_opening_is_not_read(opening: str, closing: str) -> None:
    """F1, F2: a body that is not an opening (or a closing that is not only ``}``)
    leaves the file as it is."""
    source = _file(opening, closing, "void f() {}").encode("utf-8")
    prepared = prepare(source)
    assert not prepared.scopes.pairs
    assert prepared.parse_text == source


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "#define LIB_NAMESPACE_BEGIN(name) namespace name {\n"
            "#define LIB_NAMESPACE_END }\n"
            "LIB_NAMESPACE_BEGIN\nvoid f() {}\nLIB_NAMESPACE_END\n",
            id="function_like",
        ),
        pytest.param(
            "#define lib other\n#define LIB_NAMESPACE_BEGIN namespace lib {\n"
            "#define LIB_NAMESPACE_END }\n"
            "LIB_NAMESPACE_BEGIN\nvoid f() {}\nLIB_NAMESPACE_END\n",
            id="namespace_name_is_a_macro",
        ),
    ],
)
def test_a_macro_the_rules_refuse_is_not_read(source: str) -> None:
    """F1: a function-like macro is not read (``PYBIND11_NAMESPACE_BEGIN(name)``), nor
    is an opening that names a namespace the file ``#define``\\ s itself."""
    assert not prepare(source.encode("utf-8")).scopes.pairs


@pytest.mark.parametrize(
    ("definitions", "read"),
    [
        pytest.param(
            "#if A\n#define LIB_NAMESPACE_BEGIN namespace lib {\n#else\n"
            "#define LIB_NAMESPACE_BEGIN namespace other {\n#endif\n",
            False,
            id="disagreeing",
        ),
        pytest.param(
            "#ifndef LIB_NAMESPACE_BEGIN\n#define LIB_NAMESPACE_BEGIN namespace lib {\n"
            "#endif\n#ifndef LIB_NAMESPACE_BEGIN\n"
            "#define LIB_NAMESPACE_BEGIN namespace lib {\n#endif\n",
            True,
            id="ifndef_idiom_twice",
        ),
    ],
)
def test_every_definition_must_agree(definitions: str, read: bool) -> None:
    """F3: two definitions that disagree leave the name unused (and so, with its closing
    unpaired, the file unchanged); the ``#ifndef X`` / ``#define X`` idiom, repeated
    alike, is read."""
    source = (
        f"{definitions}#define LIB_NAMESPACE_END }}\n"
        "LIB_NAMESPACE_BEGIN\nvoid f() {}\nLIB_NAMESPACE_END\n"
    )
    assert bool(prepare(source.encode("utf-8")).scopes.pairs) == read


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "LIB_NAMESPACE_BEGIN\nvoid f() {}\nLIB_NAMESPACE_END\n"
            "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n",
            id="used_before_defined",
        ),
        pytest.param(
            "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
            "#undef LIB_NAMESPACE_BEGIN\n"
            "LIB_NAMESPACE_BEGIN\nvoid f() {}\nLIB_NAMESPACE_END\n",
            id="used_after_undef",
        ),
    ],
)
def test_an_invocation_where_the_macro_is_not_defined_is_not_read(source: str) -> None:
    """F4: an invocation before the name's first definition, or after an ``#undef`` of
    it, leaves the name unused."""
    assert not prepare(source.encode("utf-8")).scopes.pairs


@pytest.mark.parametrize(
    ("opening", "closing", "between", "pairs"),
    [
        pytest.param(
            "LIB_NAMESPACE_BEGIN // opens lib",
            "LIB_NAMESPACE_END /* closes */",
            "",
            1,
            id="comment_beside",
        ),
        pytest.param(
            "    LIB_NAMESPACE_BEGIN", "\tLIB_NAMESPACE_END", "", 1, id="indented"
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN",
            "LIB_NAMESPACE_END",
            "/*\nLIB_NAMESPACE_BEGIN\n*/",
            1,
            id="in_a_block_comment",
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN",
            "LIB_NAMESPACE_END",
            'const char* s = R"x(\nLIB_NAMESPACE_BEGIN\n)x";',
            1,
            id="in_a_raw_string",
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN",
            "LIB_NAMESPACE_END",
            "// a comment \\\nLIB_NAMESPACE_BEGIN",
            1,
            id="in_a_spliced_line_comment",
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN",
            "LIB_NAMESPACE_END",
            "#if 0\n#define X \\\nLIB_NAMESPACE_BEGIN\n#endif",
            1,
            id="in_a_directive",
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN",
            "LIB_NAMESPACE_END",
            "char q = '\"'; int n = 1'000'000;",
            1,
            id="char_and_digit_separators",
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN void f();", "LIB_NAMESPACE_END", "", 0, id="not_alone"
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN;", "LIB_NAMESPACE_END", "", 0, id="with_a_semicolon"
        ),
    ],
)
def test_an_invocation_stands_alone_in_code(
    opening: str, closing: str, between: str, pairs: int
) -> None:
    """F5: an invocation is a logical line that is the name alone (a comment beside it
    is fine), in code. Inside a comment, a raw string or a directive, or with anything
    else on its line, it is no invocation: here a stray one would leave its pair
    unclosed (F6) and the file unchanged, so the pair read proves it was not taken."""
    source = (
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        f"{opening}\n{between}\nvoid f() {{}}\n{closing}\n"
    )
    prepared = prepare(source.encode("utf-8"))
    assert len(prepared.scopes.pairs) == pairs, prepared.parse_text
    # whatever is not an invocation is untouched
    for kept in (
        'R"x(\nLIB_NAMESPACE_BEGIN',
        "/*\nLIB_NAMESPACE_BEGIN",
        "\\\nLIB_NAMESPACE_BEGIN",
    ):
        if kept in source:
            assert kept.encode("utf-8") in prepared.parse_text, prepared.parse_text


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param("LIB_NAMESPACE_BEGIN\nvoid f() {}\n", id="left_open"),
        pytest.param("void f() {}\nLIB_NAMESPACE_END\n", id="nothing_open"),
        pytest.param(
            "LIB_NAMESPACE_BEGIN\nvoid f() {}\nLIB_NAMESPACE_END2\n",
            id="other_brace_count",
        ),
    ],
)
def test_unbalanced_pairs_leave_the_file_unchanged(extra: str) -> None:
    """F6: an opening left open, a closing with nothing open, or a closing of another
    brace count leaves the whole file unchanged, other pairs included."""
    source = (
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        "#define LIB_NAMESPACE_END2 }}\n"
        f"LIB_NAMESPACE_BEGIN\nvoid g() {{}}\nLIB_NAMESPACE_END\n{extra}"
    ).encode()
    prepared = prepare(source)
    assert not prepared.scopes.pairs
    assert prepared.parse_text == source


def test_the_copy_differs_only_in_the_invocations() -> None:
    """F10: the parsed copy has the source's length, an opening is ``extern"C++"{`` and
    a closing ``}``, each padded with spaces to the invocation's length, and every other
    byte is the source's."""
    source = _file(
        "namespace lib { inline namespace v1 {",
        "} }",
        "namespace detail {\nint f(const char* s) { return s[0] == 'x'; }\n}",
    ).encode("utf-8")
    prepared = prepare(source)
    [pair] = prepared.scopes.pairs
    copy = prepared.parse_text
    assert len(copy) == len(source)
    assert copy[slice(*pair.opening)] == OPENING.ljust(19)
    assert copy[slice(*pair.closing)] == CLOSING.ljust(17)
    for index, (written, parsed) in enumerate(zip(source, copy, strict=True)):
        if not (
            pair.opening[0] <= index < pair.opening[1]
            or pair.closing[0] <= index < pair.closing[1]
        ):
            assert written == parsed, f"byte {index}"


def test_a_short_opening_is_left_as_written() -> None:
    """An opening shorter than ``extern"C++"{`` (12 bytes) is not rewritten, nor is its
    closing, and opens no namespace; a longer pair beside it still is. (Blanking a short
    one instead would move a marker above it onto the first declaration inside:
    ``test_a_marker_before_an_opening_is_not_moved``.)"""
    source = (
        "#define NS_OPEN namespace inner {\n#define NS_SHUT }\n"
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        "LIB_NAMESPACE_BEGIN\nNS_OPEN\nvoid f() {}\nNS_SHUT\nLIB_NAMESPACE_END\n"
    )
    prepared = prepare(source.encode("utf-8"))
    assert _opened(source) == [["lib"]]
    assert b"\nNS_OPEN\n" in prepared.parse_text
    assert b"\nNS_SHUT\n" in prepared.parse_text
    assert b"\nLIB_NAMESPACE_BEGIN\n" not in prepared.parse_text
    # one byte longer than the rewrite is read
    assert _opened(
        "#define NS_OPEN_LONG namespace inner {\n#define NS_SHUT }\n"
        "NS_OPEN_LONG\nvoid f() {}\nNS_SHUT\n"
    ) == [["inner"]]
    assert len("NS_OPEN_LONG") == len(OPENING)


def test_which_files_are_read() -> None:
    """F8, F9: a ``.c`` file is C (never read), every other C or C++ file is; and a
    buffer with no ``namespace`` or no ``#define`` line is not lexed at all."""
    assert not cpp_macros.applies(PurePath("src/driver.c"))
    for path in ("a.cpp", "a.hpp", "a.h", "a.cc", "a.C", "include/json.hpp"):
        assert cpp_macros.applies(PurePath(path)), path
    assert not cpp_macros._worth_lexing(b"#define X 1\nvoid f() {}\n")
    assert not cpp_macros._worth_lexing(b"namespace lib { void f() {} }\n")
    assert cpp_macros._worth_lexing(b"#  define X namespace lib {\n")


def test_names_inside_a_pair_are_qualified() -> None:
    """The names a pair gives: an entity whose name ends between an opening and its
    closing is prefixed with the pair's namespaces, outermost first (a nested pair's
    after its outer one's); one outside is not."""
    source = (
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        "#define DETAIL_NAMESPACE_BEGIN namespace detail {\n"
        "#define DETAIL_NAMESPACE_END }\n"
        "void before() {}\nLIB_NAMESPACE_BEGIN\nvoid f() {}\nDETAIL_NAMESPACE_BEGIN\n"
        "void g() {}\nDETAIL_NAMESPACE_END\nLIB_NAMESPACE_END\nvoid after() {}\n"
    )
    scopes = prepare(source.encode("utf-8")).scopes

    def qualified(name: str) -> str:
        name_end = source.find(f"void {name}") + len(f"void {name}")
        return "::".join([*scopes.namespaces_at(name_end), name])

    assert qualified("before") == "before"
    assert qualified("f") == "lib::f"
    assert qualified("g") == "lib::detail::g"
    assert qualified("after") == "after"


def _parse(source: str) -> tuple[TreeSitterNode, cpp_macros.MacroScopes]:
    parser, _ = utils.init_tree_sitter(CommentType.cpp, Path("a.cpp"))
    tree, scopes = cpp_macros.parse(parser, source.encode("utf-8"))
    return tree.root_node, scopes


@pytest.mark.parametrize(
    ("around", "used"),
    [
        pytest.param("{}", 1, id="at_file_level"),
        pytest.param("namespace outer {{\n{}\n}}", 0, id="in_a_namespace"),
        pytest.param('extern "C++" {{\n{}\n}}', 0, id="in_an_extern_block"),
        pytest.param("struct S {{\n{}\n}};", 0, id="in_a_class"),
        pytest.param(
            "OUTER_NAMESPACE_BEGIN\n{}\nOUTER_NAMESPACE_END", 2, id="in_another_pair"
        ),
    ],
)
def test_a_pair_inside_a_real_scope_names_nothing(around: str, used: int) -> None:
    """F7: a pair whose opening lies inside a real scope (a namespace, a class, a
    function, an ``extern`` block of the file's own) is not used for names; one nested
    in another pair is."""
    pair = "LIB_NAMESPACE_BEGIN\nvoid f();\nLIB_NAMESPACE_END"
    source = (
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        "#define OUTER_NAMESPACE_BEGIN namespace outer {\n"
        "#define OUTER_NAMESPACE_END }\n" + around.format(pair) + "\n"
    )
    _, scopes = _parse(source)
    assert len(scopes.pairs) == used, source


@pytest.mark.parametrize(
    ("body", "read"),
    [
        pytest.param(
            "LIB_NAMESPACE_BEGIN\nvoid f(); LIB_NAMESPACE_END\nvoid g();\n"
            "LIB_NAMESPACE_BEGIN void h();\nLIB_NAMESPACE_END\n",
            False,
            id="closing_after_code",
        ),
        pytest.param(
            "LIB_NAMESPACE_BEGIN void h();\nLIB_NAMESPACE_BEGIN\nvoid f();\n"
            "LIB_NAMESPACE_END\n",
            False,
            id="opening_before_code",
        ),
        pytest.param(
            "#ifdef LIB_NAMESPACE_BEGIN\n#endif\nLIB_NAMESPACE_BEGIN\nvoid f();\n"
            "LIB_NAMESPACE_END\n",
            True,
            id="in_a_directive",
        ),
    ],
)
def test_a_macro_used_other_than_alone_is_not_read(body: str, read: bool) -> None:
    """F5, F6: a macro used other than alone on its line anywhere in the code
    (``void f(); LIB_NAMESPACE_END``, ``LIB_NAMESPACE_BEGIN void h();``) is not read:
    pairing only its alone lines would open a namespace around code outside it. A use
    in a directive (``#ifndef``) is not code, and is fine."""
    source = (
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        + body
    ).encode("utf-8")
    prepared = prepare(source)
    assert bool(prepared.scopes.pairs) == read, source
    if not read:
        assert prepared.parse_text == source


def test_a_pair_inside_a_short_one_is_left_as_written() -> None:
    """A long pair inside a short one (which is left as written) is left as written
    too, so the short opening's line never reads as a declaration swallowing the long
    one's block."""
    source = (
        b"#define NS_A namespace a {\n#define NS_A_END }\n"
        b"#define LONG_NAMESPACE_B namespace b {\n#define LONG_NAMESPACE_B_END }\n"
        b"NS_A\nLONG_NAMESPACE_B\nint f() { return 0; }\nLONG_NAMESPACE_B_END\n"
        b"NS_A_END\n"
    )
    prepared = prepare(source)
    assert not prepared.scopes.pairs
    assert prepared.parse_text == source


# ---------------------------------------------------------------------------
# End to end: the names a marker's entity gets, and where a marker is attached
# ---------------------------------------------------------------------------

# A header in ``json.hpp``'s shape: its namespace opened by a macro it defines itself
# (guarded by ``#ifndef``, continued over lines, with an inline namespace named by a
# macro call), and closed by another.
SAMPLE = """\
#ifndef LIB_NAMESPACE_BEGIN
#define LIB_NAMESPACE_BEGIN \\
    namespace lib \\
    { \\
    inline namespace LIB_ABI_TAG(v3, 12) \\
    {
#endif
#ifndef LIB_NAMESPACE_END
#define LIB_NAMESPACE_END }}
#endif

LIB_NAMESPACE_BEGIN
namespace detail {
// @need-ids: REQ_F
int f(int x) { return x; }
class W {
  public:
    // @need-ids: REQ_M
    void m() {}
};
}  // namespace detail
// @need-ids: REQ_G
void g() {}
LIB_NAMESPACE_END
"""


def _analyse(tmp_path: Path, source: str, filename: str) -> SourceAnalyse:
    """``source`` analysed for need-id references, as a file ``filename``."""
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
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
    return analyse


def _analysed(tmp_path: Path, source: str, filename: str) -> list[dict[str, Any]]:
    """The need-id references of ``source``, analysed as a file ``filename``."""
    return [ref.to_dict() for ref in _analyse(tmp_path, source, filename).need_id_refs]


def _attached(references: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    """The qualified name of the entity each reference is attached to, by its first id
    (the analysis lists references in capture order, which is not stable)."""
    return sorted(
        (
            reference["need_ids"][0],
            reference["scope"]["qualified_name"] if reference["scope"] else None,
        )
        for reference in references
    )


def _parts(references: list[dict[str, Any]], need_id: str) -> list[str]:
    """The parts of the name of the entity the reference to ``need_id`` is attached
    to."""
    [scope] = [
        reference["scope"]
        for reference in references
        if reference["need_ids"][0] == need_id
    ]
    return [f"{part['kind']} {part['name']}" for part in scope["semantic"]]


def _as_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every C++ file read as written: no namespace macro is read."""
    monkeypatch.setattr(
        cpp_macros,
        "prepare",
        lambda source: cpp_macros.Prepared(source, cpp_macros.MacroScopes()),
    )


def test_markers_are_named_in_the_macro_namespace(tmp_path: Path) -> None:
    """The sample parses (no error past the macros), its markers' entities are named in
    the macro's namespace (the inline one left out), and the parts lead with it."""
    parser, _ = utils.init_tree_sitter(CommentType.cpp, Path("lib.hpp"))
    tree, names = utils.parse_source(
        SAMPLE.encode("utf-8"), parser, CommentType.cpp, Path("include/lib.hpp")
    )
    assert names is not None
    assert names.macros.pairs
    assert not tree.root_node.has_error, str(tree.root_node)

    references = _analysed(tmp_path, SAMPLE, "include/lib.hpp")
    assert _attached(references) == [
        ("REQ_F", "lib::detail::f"),
        ("REQ_G", "lib::g"),
        ("REQ_M", "lib::detail::W::m"),
    ]
    assert _parts(references, "REQ_F") == [
        "namespace lib",
        "namespace detail",
        "function f",
    ]


def test_every_read_is_from_the_file_as_written(tmp_path: Path) -> None:
    """A marker on a namespace that holds a pair (which F7 leaves unnamed, its rewrite
    kept) carries the namespace's text as written, macro and all, as its tagged scope
    and its excerpt; and every comment of a rewritten file has its bytes as written."""
    source = (
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        "// @need-ids: REQ_O\nnamespace outer {\nLIB_NAMESPACE_BEGIN\n"
        "// a comment inside\nvoid h() {}\nLIB_NAMESPACE_END\n}\n"
    )
    assert prepare(source.encode("utf-8")).parse_text != source.encode("utf-8")
    analyse = _analyse(tmp_path, source, "a.cpp")
    [reference] = [ref.to_dict() for ref in analyse.need_id_refs]
    written = source[source.index("namespace outer") : -1]
    assert reference["tagged_scope"] == written
    assert reference["scope"]["qualified_name"] == "outer"
    [record] = need_id_ref_records(
        analyse.need_id_refs, project="p", root=tmp_path, root_kind="src_dir"
    )
    assert record.scope == "namespace outer {"
    for comment in analyse.src_comments:
        node = comment.node
        assert node.text == source.encode("utf-8")[node.start_byte : node.end_byte]
    assert _defined(source) == ["outer::h"]


def _name_of(node: TreeSitterNode, names: CppNames) -> str | None:
    """The name the whole file (``names``) gives the entity ``node``."""
    name = describe_entity(node, CommentType.cpp, source=names.source)
    assert name is not None
    return names.qualify(name, node.start_point.row + 1).qualified_name


def _defined(source: str, path: str = "a.hpp") -> list[str | None]:
    """The names of the function definitions of ``source``, in file order, as the
    analysis of a file at ``path`` names them."""
    parser, _ = utils.init_tree_sitter(CommentType.cpp, Path(path))
    tree, names = utils.parse_source(
        source.encode("utf-8"), parser, CommentType.cpp, Path(path)
    )
    assert names is not None
    found = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        stack.extend(reversed(node.children))
        if node.type == "function_definition" and is_entity(node, CommentType.cpp):
            found.append(_name_of(node, names))
    return found


def test_a_c_file_is_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """F8: a ``.c`` file's macros are not read, so its markers are attached and named
    as before."""
    after = sorted(_attached(_analysed(tmp_path, SAMPLE, "src/lib.c")))
    _as_written(monkeypatch)
    before = sorted(_attached(_analysed(tmp_path / "before", SAMPLE, "src/lib.cpp")))
    assert after == before
    assert not any(name and name.startswith("lib::") for _, name in after)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
            "WARNINGS_PUSH\nLIB_NAMESPACE_BEGIN\nint f() { return 0; }\n"
            "int g() { return 1; }\nLIB_NAMESPACE_END\n",
            ["f", "g"],
            id="macro_statement_before_the_opening",
        ),
        pytest.param(
            "#define NS_A namespace a {\n#define NS_A_END }\n"
            "#define LONG_NAMESPACE_B namespace b {\n#define LONG_NAMESPACE_B_END }\n"
            "NS_A\nLONG_NAMESPACE_B\nint f() { return 0; }\nint g() { return 1; }\n"
            "LONG_NAMESPACE_B_END\nNS_A_END\n",
            ["f", "g"],
            id="inside_a_short_pair",
        ),
        pytest.param(
            "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
            "WARNINGS_PUSH;\nLIB_NAMESPACE_BEGIN\nint f() { return 0; }\n"
            "int g() { return 1; }\nLIB_NAMESPACE_END\n",
            ["lib::f", "lib::g"],
            id="control_read",
        ),
    ],
)
def test_an_opening_the_tree_does_not_read_is_left_as_written(
    source: str, expected: list[str]
) -> None:
    """An opening the tree does not read as its block is left as written: a macro
    statement on the line before it (``WARNINGS_PUSH``) would make
    ``WARNINGS_PUSH extern"C++"{`` one declaration and lose ``f``. Both ``f`` and ``g``
    stay definitions, named without the macro's namespace. The same for a long pair
    inside a short one (left as written)."""
    assert _defined(source) == expected, source


def test_an_unnamed_entity_in_a_pair_is_qualified(tmp_path: Path) -> None:
    """A marker on an entity with no name (an anonymous namespace) between a pair is
    named in the pair's namespace too, as the functions in it are."""
    source = (
        "#define LIB_NAMESPACE_BEGIN namespace lib {\n#define LIB_NAMESPACE_END }\n"
        "LIB_NAMESPACE_BEGIN\n// @need-ids: REQ_A\nnamespace {\nvoid f() {}\n}\n"
        "LIB_NAMESPACE_END\n// @need-ids: REQ_B\nnamespace {\nvoid g() {}\n}\n"
    )
    references = _analysed(tmp_path, source, "a.cpp")
    assert _attached(references) == [
        ("REQ_A", "lib::(anonymous namespace)"),
        ("REQ_B", "(anonymous namespace)"),
    ]
    assert _parts(references, "REQ_A") == [
        "namespace lib",
        "namespace (anonymous namespace)",
    ]
    assert _defined(source) == [
        "lib::(anonymous namespace)::f",
        "(anonymous namespace)::g",
    ]


@pytest.mark.parametrize("opening", ["LIB_NAMESPACE_BEGIN", "NS_OPEN"])
@pytest.mark.parametrize(
    ("first", "name"),
    [
        ("void f() {}", "f"),
        ("namespace detail { void f() {} }", "detail"),
        ("class A { void m(); };", "A"),
        ("template <typename T> void g(T) {}", "g"),
        ("struct S {};", "S"),
    ],
)
def test_a_marker_before_an_opening_is_not_moved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    first: str,
    name: str,
    opening: str,
) -> None:
    """A marker right before an opening invocation is never moved onto the first
    declaration inside the pair, nor to the file: with the opening rewritten to
    ``extern"C++"{`` it is attached to no entity (as before an ``extern "C++" {``
    block; before, tree-sitter could read the macro as a function's return type and
    attach it to that function), and an opening shorter than the rewrite is not read at
    all, so its markers are attached exactly as before. Blanking a short opening
    instead puts a blank line under the comment, and the comment would lead the
    namespace, class, template or struct after it."""
    source = (
        f"#define {opening} namespace lib {{\n#define NS_SHUT }}\nint x;\n"
        f"// @need-ids: REQ_1\n{opening}\n{first}\nNS_SHUT\n"
    )
    [after] = _analysed(tmp_path / "after", source, "a.cpp")
    with monkeypatch.context() as patched:
        _as_written(patched)
        [before] = _analysed(tmp_path / "before", source, "a.cpp")

    def on_first(reference: dict[str, Any]) -> bool:
        attached = reference["scope"]["qualified_name"] if reference["scope"] else None
        return attached is not None and (
            attached == name or attached.endswith(f"::{name}")
        )

    if not on_first(before):
        assert not on_first(after), (source, after)
    for record in (after, before):
        record.pop("filepath")
    if len(opening) < len(OPENING):
        assert after == before, source
    else:
        assert after["scope"] is None, source
