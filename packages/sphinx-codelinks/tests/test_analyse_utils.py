# @Test suite for tree-sitter parsing utilities and language support, TEST_LANG_1, test, [IMPL_LANG_1, IMPL_EXTR_1]
import shutil
import subprocess
from pathlib import Path

import pytest
from tree_sitter import Node as TreeSitterNode
from tree_sitter import Parser, Query

from sphinx_codelinks.analyse import utils
from sphinx_codelinks.source_discover.config import COMMENT_FILETYPE, CommentType


# The fixtures build the parsers the way analysis does, through init_tree_sitter.
@pytest.fixture(scope="session")
def init_cpp_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.cpp)


@pytest.fixture(scope="session")
def init_python_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.python)


@pytest.fixture(scope="session")
def init_csharp_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.cs)


@pytest.fixture(scope="session")
def init_yaml_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.yaml)


@pytest.fixture(scope="session")
def init_rust_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.rust)


@pytest.fixture(scope="session")
def init_typescript_tree_sitter() -> tuple[Parser, Query]:
    # A .tsx file: the TSX grammar, which the JSX fixtures below need
    return utils.init_tree_sitter(CommentType.ts, Path("fixture.tsx"))


@pytest.fixture(scope="session")
def init_go_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.go)


@pytest.fixture(scope="session")
def init_jsonc_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.jsonc)


@pytest.fixture(scope="session")
def init_bash_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.bash)


@pytest.fixture(scope="session")
def init_powershell_tree_sitter() -> tuple[Parser, Query]:
    return utils.init_tree_sitter(CommentType.powershell)


def test_init_tree_sitter_powershell(init_powershell_tree_sitter):
    """Both PowerShell comment forms, ``#`` and ``<# #>``, are comment nodes."""
    parser, query = init_powershell_tree_sitter
    comments = utils.extract_comments(b"# a\n<# b #>\nfunction f { }\n", parser, query)
    assert comments
    assert [comment.text for comment in comments] == [b"# a", b"<# b #>"]


@pytest.mark.parametrize(
    "code",
    [
        # a here-string whose ``#`` line is not its first line
        b'$stub = @"\nfunction Test-It {\n# @Generated, IMPL_GEN, impl\n}\n"@\n',
        # an interpolating here-string
        b'$name = "px"\n$t = @"\nHello $name\n# @Interp, IMPL_INTERP, impl\n"@\n',
    ],
)
def test_a_hash_line_in_a_powershell_here_string_is_no_comment(
    code, init_powershell_tree_sitter
):
    """The grammar reads a ``#`` line inside an expandable here-string as a comment
    node; it is string content, so extraction leaves it out."""
    parser, query = init_powershell_tree_sitter
    comments = utils.extract_comments(code + b"# real\nfunction f { }\n", parser, query)
    assert comments
    assert [comment.text for comment in comments] == [b"# real"]


@pytest.mark.parametrize(
    "code",
    [
        # an ordinary double-quoted string that interpolates before its ``#`` line
        # and on it
        b'$c = "one $x\n# @Fake, ID_FAKE, impl $y\nthree"\n',
        # the interpolation first in the string
        b'$c = "$x\n# @Fake, ID_FAKE, impl $y\nthree"\n',
        # a subexpression is an interpolation too
        b'$c = "one $($x)\n# @Fake, ID_FAKE, impl $($y)\nthree"\n',
        # a string passed to a command, the ``#`` indented
        b'Write-Host "one $x\n    # @Fake $y, ID_FAKE, impl\nthree"\n',
        # the ``#`` on the interpolation's own line
        b'$c = "one $x # @Fake, ID_FAKE, impl $y\nthree"\n',
    ],
)
def test_a_hash_line_in_an_interpolating_powershell_string_is_no_comment(
    code, init_powershell_tree_sitter
):
    """After an interpolation in a double-quoted string, the grammar may read a ``#``
    that follows it past whitespace alone as a comment node inside the string, as it
    does in a here-string: it is string content, never a marker."""
    parser, query = init_powershell_tree_sitter
    comments = utils.extract_comments(code + b"# real\nfunction f { }\n", parser, query)
    assert comments
    assert [comment.text for comment in comments] == [b"# real"]


@pytest.mark.parametrize(
    "code",
    [
        # a subexpression in a here-string is code
        b'$s = @"\n$( # in code\n 1 )\n"@\n',
        # and in an ordinary double-quoted string
        b'$s = "a $( # in code\n 1 ) b"\n',
    ],
)
def test_a_comment_in_a_powershell_subexpression_is_a_comment(
    code, init_powershell_tree_sitter
):
    """A comment inside ``$( … )`` is a comment of the code the string interpolates,
    not string content: it is kept, string or not around it."""
    parser, query = init_powershell_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    assert comments
    assert [comment.text for comment in comments] == [b"# in code"]


def test_every_comment_type_is_wired():
    """A comment type is a ``CommentType`` member plus an entry in each of several
    tables; a member one of them misses fails here, rather than as a ``KeyError`` in
    discovery or as no scope at all."""
    members = set(CommentType)
    assert set(COMMENT_FILETYPE) == {member.value for member in members}
    # YAML and JSONC bind to data structures, not scopes (find_associated_scope)
    assert set(utils.SCOPE_NODE_TYPES) == members - {
        CommentType.yaml,
        CommentType.jsonc,
    }
    assert set(utils.WRAPPER_TYPES) <= set(utils.ENTITY_NODE_TYPES)
    assert set(utils.TRIVIA_TYPES) <= set(utils.ENTITY_NODE_TYPES)
    for comment_type, predicates in utils.SCOPE_PREDICATES.items():
        assert set(predicates) <= utils.SCOPE_NODE_TYPES[comment_type]
    for member in members:
        utils.init_tree_sitter(member)


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                void dummy_func1(){
                }
            """,
            "void dummy_func1()",
        ),
        (
            b"""
                void dummy_func2(){
                }
                // @req-id: need_001
                void dummy_func1(){
                }
            """,
            "void dummy_func1()",
        ),
        (
            b"""
                void dummy_func1(){
                    a = 1;
                    /* @req-id: need_001 */
                }
            """,
            "void dummy_func1()",
        ),
        (
            b"""
                void dummy_func1(){
                    // @req-id: need_001
                    a = 1;
                }
                void dummy_func2(){
                }
            """,
            "void dummy_func1()",
        ),
    ],
)
def test_find_associated_scope_cpp(code, result, init_cpp_tree_sitter):
    parser, query = init_cpp_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.cpp
    )
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


#: What :func:`_attached_to` gives for a marker rule 7 attaches to nothing
ABOVE_CONDITIONAL = utils.Unattached.above_conditional


def _attached_to(
    source: str, parser: Parser, query: Query
) -> tuple[str, str, str] | utils.Unattached | None:
    """What the comment holding ``marker`` in the C++ ``source`` is attached to: the
    entity's node kind, its first line and the mechanism; :data:`ABOVE_CONDITIONAL`
    for nothing by rule 7, ``None`` for nothing by any other rule."""
    comments = utils.extract_comments(source.encode(), parser, query) or []
    marker = next(c for c in comments if b"marker" in (c.text or b""))
    association = utils.associate(marker, CommentType.cpp)
    if association is None or isinstance(association, utils.Unattached):
        return association
    first_line = (association.node.text or b"").decode().splitlines()[0]
    return association.node.type, first_line, association.mechanism


#: The conditionals a marker can stand directly above, each the body of a namespace or a
#: class with the marker as its first line
CONDITIONAL_ARMS = {
    "one-arm": "#if FEATURE_B\nvoid active() {}\n#endif\n",
    "ifdef": "#ifdef FEATURE_B\nvoid active() {}\n#endif\n",
    "ifndef": "#ifndef FEATURE_B\nvoid active() {}\n#endif\n",
    "else-different-functions": (
        "#if FEATURE_B\nvoid active() {}\n#else\nvoid fallback() {}\n#endif\n"
    ),
    "else-same-function": (
        "#if FEATURE_B\nvoid active() { fast(); }\n"
        "#else\nvoid active() { slow(); }\n#endif\n"
    ),
    "elif": (
        "#if FEATURE_A\nvoid a() {}\n#elif FEATURE_B\nvoid b() {}\n"
        "#else\nvoid c() {}\n#endif\n"
    ),
    "declaration-only": "#if FEATURE_B\nvoid declared();\n#endif\n",
}

#: The marker as the last line of an arm, directly above the next directive of the
#: same conditional
ARM_ENDINGS = {
    "above-else": (
        "#if FEATURE_B\nvoid active() {}\n// marker\n#else\nvoid fallback() {}\n#endif\n"
    ),
    "above-elif": (
        "#if FEATURE_A\nvoid a() {}\n// marker\n#elif FEATURE_B\nvoid b() {}\n#endif\n"
    ),
    "above-elifdef": (
        "#ifdef FEATURE_A\nvoid a() {}\n// marker\n#elifdef FEATURE_B\nvoid b() {}\n"
        "#endif\n"
    ),
    "above-endif": "#if FEATURE_B\nvoid active() {}\n// marker\n#endif\n",
    "above-endif-after-else": (
        "#if FEATURE_B\nvoid a() {}\n#else\nvoid b() {}\n// marker\n#endif\n"
    ),
}

CONTAINERS = {
    "namespace": ("namespace lib {\n", "}\n"),
    "class": ("class Widget {\n", "};\n"),
}


@pytest.mark.parametrize("container", list(CONTAINERS))
@pytest.mark.parametrize(
    "body",
    [
        *(
            pytest.param(f"// marker\n{arms}", id=name)
            for name, arms in CONDITIONAL_ARMS.items()
        ),
        *(pytest.param(body, id=name) for name, body in ARM_ENDINGS.items()),
        pytest.param("/// marker\n" + CONDITIONAL_ARMS["one-arm"], id="doc-comment"),
        pytest.param(
            "// marker\n// and its second line\n" + CONDITIONAL_ARMS["one-arm"],
            id="comment-run",
        ),
        pytest.param(
            "/* marker\n */\n" + CONDITIONAL_ARMS["one-arm"], id="block-comment"
        ),
    ],
)
def test_marker_directly_above_a_conditional_is_on_nothing(
    container: str, body: str, init_cpp_tree_sitter: tuple[Parser, Query]
) -> None:
    """A marker directly above a preprocessor conditional's line, in a namespace or a
    class body, is attached to nothing, as clang attaches it: it would otherwise trace
    every unit of the container, whichever arm is compiled. ``#elif``, ``#else`` and
    ``#endif`` count as the opening directives do, and other comments may stand between
    when no blank line does."""
    head, tail = CONTAINERS[container]

    assert _attached_to(head + body + tail, *init_cpp_tree_sitter) is ABOVE_CONDITIONAL


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "struct S {\n// marker\n" + CONDITIONAL_ARMS["one-arm"] + "};\n",
            id="struct",
        ),
        pytest.param(
            "union U {\n// marker\n#if FEATURE_B\nint a;\n#endif\nfloat b;\n};\n",
            id="union",
        ),
        pytest.param(
            "enum E {\n// marker\n#if FEATURE_B\nA,\n#endif\nB,\n};\n", id="enum"
        ),
        pytest.param(
            'namespace lib {\nextern "C" {\n// marker\n'
            + CONDITIONAL_ARMS["declaration-only"]
            + "}\n}\n",
            id="extern-c-block-in-a-namespace",
        ),
    ],
)
def test_marker_directly_above_a_conditional_is_on_nothing_in_any_body(
    source: str, init_cpp_tree_sitter: tuple[Parser, Query]
) -> None:
    """Not only in a namespace or class body: anywhere outside a function's body, a
    struct, union or enum body and an ``extern "C"`` block included, a marker directly
    above a conditional is attached to nothing, where the struct, union or enum, or
    the namespace around the block, held it."""
    assert _attached_to(source, *init_cpp_tree_sitter) is ABOVE_CONDITIONAL


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "// marker\n" + CONDITIONAL_ARMS["one-arm"],
            ABOVE_CONDITIONAL,
            id="file-level-first",
        ),
        pytest.param(
            "void first() {}\n// marker\n" + CONDITIONAL_ARMS["one-arm"],
            ABOVE_CONDITIONAL,
            id="file-level-after-an-item",
        ),
        pytest.param(
            "// marker\n\n" + CONDITIONAL_ARMS["one-arm"], None, id="file-header"
        ),
        pytest.param("void first() {}\n// marker\n", None, id="file-level-at-the-end"),
        pytest.param(
            "void outer() {\n// marker\n#if FEATURE_B\nfast();\n#endif\n}\n",
            ("function_definition", "void outer() {", "enclosing"),
            id="function-body",
        ),
        pytest.param(
            "namespace lib {\nvoid outer() {\n// marker\n#ifdef FEATURE_B\nfast();\n"
            "#endif\n}\n}\n",
            ("function_definition", "void outer() {", "enclosing"),
            id="function-body-in-a-namespace",
        ),
        pytest.param(
            "namespace lib {\nvoid first() {} // marker\n"
            + CONDITIONAL_ARMS["one-arm"]
            + "}\n",
            ("function_definition", "void first() {}", "trailing"),
            id="trailing",
        ),
        pytest.param(
            "namespace lib {\n// marker\n\n" + CONDITIONAL_ARMS["one-arm"] + "}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="blank-line-namespace",
        ),
        pytest.param(
            "class Widget {\n// marker\n\n" + CONDITIONAL_ARMS["one-arm"] + "};\n",
            ("class_specifier", "class Widget {", "enclosing"),
            id="blank-line-class",
        ),
        pytest.param(
            "namespace lib {\n// marker\n// and its second line\n\n"
            + CONDITIONAL_ARMS["one-arm"]
            + "}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="blank-line-after-a-comment-run",
        ),
        pytest.param(
            "namespace lib {\n#if FEATURE_B\nvoid active() {}\n// marker\n\n#endif\n}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="blank-line-above-endif",
        ),
        pytest.param(
            "namespace lib {\n// marker\n#define FAST 1\nvoid active() {}\n}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="above-define",
        ),
        pytest.param(
            'namespace lib {\n// marker\n#include "fast.h"\nvoid active() {}\n}\n',
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="above-include",
        ),
        pytest.param(
            "class Widget {\n// marker\n#pragma pack(1)\nvoid active() {}\n};\n",
            ("class_specifier", "class Widget {", "enclosing"),
            id="above-pragma",
        ),
        pytest.param(
            "namespace lib {\n#if FEATURE_B\n// marker\nvoid active() {}\n#endif\n}\n",
            ("function_definition", "void active() {}", "leading"),
            id="inside-the-arm",
        ),
        pytest.param(
            "void outer() {\nstruct L {\n// marker\n"
            + CONDITIONAL_ARMS["one-arm"]
            + "};\n}\n",
            ("struct_specifier", "struct L {", "enclosing"),
            id="class-local-to-a-function",
        ),
        pytest.param(
            "namespace lib {\nauto l = []() {\n// marker\n#if FEATURE_B\nactive();\n"
            "#endif\n};\nvoid after() {}\n}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="lambda-in-a-namespace",
        ),
        pytest.param(
            "namespace lib {\n// marker\n%:if FEATURE_B\nvoid active() {}\n%:endif\n}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="digraph-if",
        ),
        pytest.param(
            "namespace lib {\n#if FEATURE_B\nvoid active() {}\n// marker\n%:endif\n}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="digraph-endif",
        ),
        pytest.param(
            "namespace lib {\n#define F(x) \\\n  /* marker */ \\\n  # if x\n"
            "void active() {}\n}\n",
            ("namespace_definition", "namespace lib {", "enclosing"),
            id="define-continuation",
        ),
    ],
)
def test_marker_near_a_conditional_keeps_its_attachment(
    source: str,
    expected: tuple[str, str, str] | utils.Unattached | None,
    init_cpp_tree_sitter: tuple[Parser, Query],
) -> None:
    """Around a preprocessor conditional, every other marker keeps the attachment it
    has: at file level it is on nothing anyway, by rule 7 when directly above the
    conditional and by another rule (a file header, nothing after it) otherwise; in a function's body it is the
    function's; a trailing marker is its row's entity's; a blank line between makes it
    a comment on the namespace or class as a whole; any other directive (``#define``,
    ``#include``, ``#pragma``) breaks the attachment to the next entity as any code
    does; and inside the arm, the marker leads the definition, which is the remedy.

    A lambda's body and a class defined in a function are a function's body too. And
    the directive is read as the grammar reads it: a digraph (``%:if``) is no
    conditional to it, nor is a ``# if`` line that continues a ``#define``."""
    assert _attached_to(source, *init_cpp_tree_sitter) == expected


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                def dummy_func1():
                    # @req-id: need_001
                    pass
            """,
            "def dummy_func1()",
        ),
        (
            b"""
                def dummy_func1():
                    # @req-id: need_002
                    def dummy_func2():
                        pass
                    pass
            """,
            "def dummy_func2()",
        ),
        (
            b"""
                def dummy_func1():
                '''@req-id: need_002'''
                    def nested_dummy_func():
                        pass
                    pass
            """,
            "def dummy_func1()",
        ),
        (
            b"""
                def dummy_func1():
                    def nested_dummy_func():
                        '''@req-id: need_002'''
                        pass
                    pass
            """,
            "def nested_dummy_func()",
        ),
        (
            b"""
                def dummy_func1():
                    def nested_dummy_func():
                        # @req-id: need_002
                        pass
                    pass
            """,
            "def nested_dummy_func()",
        ),
        (
            b"""
                def dummy_func1():
                    def nested_dummy_func():
                        pass
                    # @req-id: need_002
                    pass
            """,
            "def dummy_func1()",
        ),
    ],
)
def test_find_associated_scope_python(code, result, init_python_tree_sitter):
    parser, query = init_python_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.python
    )
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert func_def.startswith(result)


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                public class DummyClass1
                {
                }
            """,
            "public class DummyClass1",
        ),
        (
            b"""
                public class DummyClass2
                {
                    // @req-id: need_001
                    public void DummyFunc2()
                    {
                    }
                }
            """,
            "public void DummyFunc2",
        ),
        (
            b"""
                public class DummyClass3
                {
                    // @req-id: need_001
                    public string Property1 { get; set; }
                }
            """,
            "public string Property1",
        ),
    ],
)
def test_find_associated_scope_csharp(code, result, init_csharp_tree_sitter):
    parser, query = init_csharp_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.cs
    )
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert func_def.startswith(result)


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                # @req-id: need_001
                database:
                  host: localhost
                  port: 5432
            """,
            "database:",
        ),
        (
            b"""
                services:
                  web:
                    # @req-id: need_002
                    image: nginx:latest
                    ports:
                      - "80:80"
            """,
            "image: nginx:latest",
        ),
        (
            b"""
                # @req-id: need_003
                version: "3.8"
                services:
                  app:
                    build: .
            """,
            "version:",
        ),
        (
            b"""
                items:
                  # @req-id: need_004
                  - name: item1
                    value: test
                  - name: item2
                    value: test2
            """,
            "- name: item1",
        ),
    ],
)
def test_find_associated_scope_yaml(code, result, init_yaml_tree_sitter):
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.yaml
    )
    assert node
    assert node.text
    yaml_structure = node.text.decode("utf-8")
    assert result in yaml_structure


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                fn dummy_func1() {
                }
            """,
            "fn dummy_func1()",
        ),
        (
            b"""
                fn dummy_func2() {
                }
                // @req-id: need_001
                fn dummy_func1() {
                }
            """,
            "fn dummy_func1()",
        ),
        (
            b"""
                fn dummy_func1() {
                    let a = 1;
                    /* @req-id: need_001 */
                }
            """,
            "fn dummy_func1()",
        ),
        (
            b"""
                fn dummy_func1() {
                    // @req-id: need_001
                    let a = 1;
                }
                fn dummy_func2() {
                }
            """,
            "fn dummy_func1()",
        ),
        (
            b"""
                /// @req-id: need_001
                fn dummy_func1() {
                }
            """,
            "fn dummy_func1()",
        ),
        (
            b"""
                struct MyStruct {
                    // @req-id: need_001
                    field: i32,
                }
            """,
            "struct MyStruct",
        ),
    ],
)
def test_find_associated_scope_rust(code, result, init_rust_tree_sitter):
    parser, query = init_rust_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.rust
    )
    assert node
    assert node.text
    rust_def = node.text.decode("utf-8")
    assert result in rust_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        # leading comment is associated with the following key/value pair
        (
            b'{\n  // @req-id: need_001\n  "alpha": 1\n}\n',
            '"alpha": 1',
        ),
        # inline comment is associated with the array item on the same row
        (
            b'{\n  "items": [\n    "first", // @req-id: need_001\n    "second"\n  ]\n}\n',
            '"first"',
        ),
        # inline comment is associated with the pair on the same row
        (
            b'{\n  "alpha": 1, // @req-id: need_001\n  "beta": 2\n}\n',
            '"alpha": 1',
        ),
        # block comment is associated with the following pair
        (
            b'{\n  /* @req-id: need_001 */\n  "beta": 2\n}\n',
            '"beta": 2',
        ),
        # trailing comment falls back to the enclosing object
        (
            b'{\n  "alpha": 1\n  // @req-id: need_001\n}\n',
            '"alpha"',
        ),
    ],
)
def test_find_associated_scope_jsonc(code, result, init_jsonc_tree_sitter):
    parser, query = init_jsonc_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.jsonc
    )
    assert node
    assert node.text
    jsonc_structure = node.text.decode("utf-8")
    assert result in jsonc_structure


@pytest.mark.parametrize(
    ("code", "result"),
    [
        # comment above a POSIX-style function definition
        (
            b"""
                # @req-id: need_001
                greet() {
                    echo hi
                }
            """,
            "greet()",
        ),
        # comment above the `function` keyword form
        (
            b"""
                # @req-id: need_002
                function greet {
                    echo hi
                }
            """,
            "function greet",
        ),
        # comment inside a function body falls back to the enclosing function
        (
            b"""
                greet() {
                    # @req-id: need_003
                    echo hi
                }
            """,
            "greet()",
        ),
    ],
)
def test_find_associated_scope_bash(code, result, init_bash_tree_sitter):
    parser, query = init_bash_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.bash
    )
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert func_def.startswith(result)


@pytest.mark.parametrize(
    ("code", "result"),
    [
        # comment above a function
        (
            b"""# @req-id: need_001
function Start-Px {
    param([string] $Config)
}
""",
            "function Start-Px",
        ),
        # comment above a filter, PowerShell's pipeline function
        (b"# @req-id: need_002\nfilter Get-Odd { $_ }\n", "filter Get-Odd"),
        # comment after a function body's last statement falls back to the function
        (
            b"""function Start-Px {
    Write-Host 'start'
    # @req-id: need_003
}
""",
            "function Start-Px",
        ),
        # comment above a class
        (b"# @req-id: need_004\nclass Proxy { }\n", "class Proxy"),
        # comment above a method inside a class
        (
            b"""class Proxy {
    # @req-id: need_005
    [string] Start([string] $c) { return $c }
}
""",
            "[string] Start",
        ),
        # comment above a Pester It inside a Describe
        (
            b"""Describe 'px' {
    # @req-id: need_006
    It 'starts' {
        1 | Should -Be 1
    }
}
""",
            "It 'starts'",
        ),
        # PowerShell is case-insensitive, and so are Pester's block names
        (
            b"""describe 'px' {
    # @req-id: need_007
    it 'lower' { }
}
""",
            "it 'lower'",
        ),
        # comment above a Describe
        (b"# @req-id: need_008\nDescribe 'px' { }\n", "Describe 'px'"),
        # comment inside an It body falls back to the It
        (
            b"""Describe 'px' {
    It 'starts' {
        1 | Should -Be 1
        # @req-id: need_009
    }
}
""",
            "It 'starts'",
        ),
        # a plain command after the comment is code: it belongs to the Describe it is
        # in, not to the It past the command, as in every other language
        (
            b"""Describe 'px' {
    # @req-id: need_012
    BeforeAll { $x = 1 }
    It 'a' { }
}
""",
            "Describe 'px'",
        ),
        # a Context is a scope like an It
        (
            b"""Describe 'px' {
    # @req-id: need_013
    Context 'ctx' { }
}
""",
            "Context 'ctx'",
        ),
        # a block called through Pester's module qualifier is a Pester block too
        (
            b"""Describe 'px' {
    # @req-id: need_014
    Pester\\It 'qualified' { }
}
""",
            "Pester\\It 'qualified'",
        ),
        # comment above a property inside a class
        (
            b"""class Proxy {
    # @req-id: need_015
    [string] $Name
    [void] Start() { }
}
""",
            "[string] $Name",
        ),
        # comment above an enum
        (b"# @req-id: need_016\nenum Mode { Direct }\n", "enum Mode"),
    ],
)
def test_find_associated_scope_powershell(code, result, init_powershell_tree_sitter):
    parser, query = init_powershell_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    assert comments
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.powershell
    )
    assert node
    assert node.text
    assert node.text.decode("utf-8").startswith(result)


@pytest.mark.parametrize(
    "command",
    [
        b"Write-Host 'x'",
        # an It of another module is not Pester's
        b"Other\\It 'x' { }",
        # a plain command is code: the function past it is not the marker's
        b"Set-StrictMode -Version Latest\nfunction Start-Px { }",
    ],
)
def test_a_non_pester_command_is_no_scope(command, init_powershell_tree_sitter):
    """Only Pester's blocks are scopes among commands: a marker above any other
    command, at file level, binds to nothing, and not to an entity after it."""
    parser, query = init_powershell_tree_sitter
    comments = utils.extract_comments(
        b"# @req-id: need_010\n" + command + b"\n", parser, query
    )
    assert comments
    assert utils.find_associated_scope(comments[0], CommentType.powershell) is None


def _powershell_attached(
    source: str, parser: Parser, query: Query
) -> tuple[str, str] | None:
    """The first line of the entity the comment holding ``marker`` in the PowerShell
    ``source`` is attached to, and the mechanism; ``None`` for nothing."""
    comments = utils.extract_comments(source.encode(), parser, query) or []
    marker = next(c for c in comments if b"marker" in (c.text or b""))
    association = utils.associate(marker, CommentType.powershell)
    if association is None or isinstance(association, utils.Unattached):
        return None
    first_line = (association.node.text or b"").decode().splitlines()[0]
    return first_line.strip(), association.mechanism


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "function f { } # marker\n",
            ("function f { }", "trailing"),
            id="function",
        ),
        pytest.param(
            "Describe 'd' {\n    It 'x' { } # marker\n}\n",
            ("It 'x' { }", "trailing"),
            id="it-in-describe",
        ),
        pytest.param(
            "Describe 'top' { } # marker\nfunction f { }\n",
            ("Describe 'top' { }", "trailing"),
            id="describe-at-file-level",
        ),
        pytest.param(
            "Describe 'd' {\n    Context 'c' {\n    } # marker\n}\n",
            ("Context 'c' {", "trailing"),
            id="context-closing-on-the-row",
        ),
        pytest.param(
            "Set-StrictMode -Version 3 # marker\nfunction f { }\n",
            None,
            id="plain-command",
        ),
        pytest.param(
            "Describe 'd' {\n    Write-Host 'x' # marker\n}\n",
            ("Describe 'd' {", "enclosing"),
            id="plain-command-in-describe",
        ),
    ],
)
def test_a_trailing_powershell_marker_binds_the_entity_on_its_row(
    source, expected, init_powershell_tree_sitter
):
    """A trailing comment belongs to the entity that ends on its row, a Pester block
    included, which the grammar wraps in a pipeline; on a plain command's row it falls
    back to the enclosing entity, as in every other language."""
    parser, query = init_powershell_tree_sitter
    assert _powershell_attached(source, parser, query) == expected


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                function dummyFunc1() {
                }
            """,
            "function dummyFunc1()",
        ),
        (
            b"""
                class DummyClass {
                    // @req-id: need_001
                    method1() {
                    }
                }
            """,
            "method1()",
        ),
        # leading comment on an exported function must descend into
        # export_statement, not resolve to no scope
        (
            b"""
                // @req-id: need_001
                export function dummyFunc1() {
                }
            """,
            "function dummyFunc1()",
        ),
        # leading comment on an exported class
        (
            b"""
                // @req-id: need_001
                export class DummyClass {
                }
            """,
            "class DummyClass",
        ),
        # leading comment on an exported const arrow function
        (
            b"""
                // @req-id: need_001
                export const dummyFunc1 = () => {
                };
            """,
            "dummyFunc1",
        ),
        # arrow-function const still resolves to itself
        (
            b"""
                // @req-id: need_001
                const dummyFunc1 = () => {
                };
            """,
            "dummyFunc1",
        ),
        # JSX-returning component parses cleanly and resolves scope (.tsx content)
        (
            b"""
                // @req-id: need_001
                export function Button() {
                    return <button>Click me</button>;
                }
            """,
            "function Button()",
        ),
    ],
)
def test_find_associated_scope_typescript(code, result, init_typescript_tree_sitter):
    parser, query = init_typescript_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.ts
    )
    assert node
    assert node.text
    ts_def = node.text.decode("utf-8")
    assert result in ts_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                def dummy_func1():
                    # @req-id: need_001
                    pass
            """,
            "def dummy_func1()",
        ),
        (
            b"""
                def dummy_func1():
                '''@req-id: need_001'''
                    pass
            """,
            "def dummy_func1()",
        ),
        (
            b"""
                def dummy_func1():
                    def nested_dummy_func1():
                        '''@req-id: need_001'''
                        pass
                    pass
            """,
            "def nested_dummy_func1()",
        ),
        (
            b"""
                def dummy_func1():
                    '''@req-id: need_001'''
                    def nested_dummy_func1():
                        pass
                    pass
            """,
            "def dummy_func1()",
        ),
    ],
)
def test_find_enclosing_scope_python(code, result, init_python_tree_sitter):
    parser, query = init_python_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_enclosing_scope(
        comments[0], CommentType.python
    )
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                # @req-id: need_001
                def dummy_func1():
                    pass
            """,
            "def dummy_func1()",
        ),
        (
            b"""
                # @req-id: need_001
                # @req-id: need_002
                def dummy_func1():
                    pass
            """,
            "def dummy_func1()",
        ),
    ],
)
def test_find_next_scope_python(code, result, init_python_tree_sitter):
    parser, query = init_python_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_next_scope(comments[0], CommentType.python)
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                void dummy_func1(){
                }
            """,
            "void dummy_func1()",
        ),
        (
            b"""
                /* @req-id: need_001 */
                void dummy_func1(){
                }
            """,
            "void dummy_func1()",
        ),
    ],
)
def test_find_next_scope_cpp(code, result, init_cpp_tree_sitter):
    parser, query = init_cpp_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_next_scope(comments[0], CommentType.cpp)
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                public class DummyClass1
                {
                }
            """,
            "public class DummyClass1",
        ),
        (
            b"""

                public class DummyClass1
                {
                    /* @req-id: need_001 */
                    /* @req-id: need_002 */
                    public void DummyFunc1()
                    {
                    }
                }
            """,
            "public void DummyFunc1",
        ),
    ],
)
def test_find_next_scope_csharp(code, result, init_csharp_tree_sitter):
    parser, query = init_csharp_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_next_scope(comments[0], CommentType.cs)
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                function dummyFunc1() {
                }
            """,
            "function dummyFunc1()",
        ),
        (
            b"""
                // @req-id: need_001
                export function dummyFunc1() {
                }
            """,
            "function dummyFunc1()",
        ),
    ],
)
def test_find_next_scope_typescript(code, result, init_typescript_tree_sitter):
    parser, query = init_typescript_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_next_scope(comments[0], CommentType.ts)
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


def test_a_plain_const_breaks_adjacency_typescript(init_typescript_tree_sitter):
    """A plain (non-function) const between the comment and a function is code, not
    trivia: the comment is attached to neither, here to the file."""
    code = b"""
        // @req-id: need_001
        const helperFlag = true;
        function dummyFunc1() {
        }
    """
    parser, query = init_typescript_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    assert comments
    assert utils.find_next_scope(comments[0], CommentType.ts) is None
    assert utils.find_associated_scope(comments[0], CommentType.ts) is None


def test_find_associated_scope_typescript_jsx_no_parse_error(
    init_typescript_tree_sitter,
):
    """A JSX-returning component must parse cleanly under the TSX grammar."""
    code = b"""
        // @req-id: need_001
        export function Button() {
            return <button>Click me</button>;
        }
    """
    parser, _ = init_typescript_tree_sitter
    tree = parser.parse(code)
    assert not tree.root_node.has_error


@pytest.mark.parametrize(
    ("name", "grammar"),
    [
        ("a.ts", "typescript"),
        ("a.mts", "typescript"),
        ("a.cts", "typescript"),
        ("A.TS", "typescript"),
        ("a.Mts", "typescript"),
        # a declaration file's suffix is ``.ts``: TypeScript, as any ``.ts`` file
        ("a.d.ts", "typescript"),
        ("a.tsx", "tsx"),
        ("a.js", "tsx"),
        ("a.jsx", "tsx"),
        ("a.mjs", "tsx"),
        ("a.cjs", "tsx"),
    ],
)
def test_ts_grammar_key(name: str, grammar: str) -> None:
    """TypeScript's own suffixes, in any case, get the TypeScript grammar, where a
    ``<T>x`` cast is legal; every other suffix of the family gets TSX."""
    assert utils.ts_grammar_key(Path(name)) == grammar


def test_typescript_ts_suffix_recovers_markers_around_angle_bracket_cast():
    """A ``.ts`` file must use the plain TypeScript grammar, not TSX.

    ``<string>x`` is a legacy angle-bracket type assertion: valid TypeScript
    syntax, but JSX syntax under the TSX grammar. There it parses as a
    ``jsx_opening_element`` and swallows the rest of the file into a single
    ``jsx_text`` node, silently dropping every marker after it (``has_error``
    is also set). ``init_tree_sitter`` must pick the plain TypeScript grammar
    for a ``.ts`` path, via ``ts_grammar_key``, so markers both above and
    below the cast all survive.
    """
    code = b"""// @Top, IMPL_TOP
const v = <string>x;
// @Bottom, IMPL_BOTTOM
const y = 2;
// @Third, IMPL_THIRD
"""
    parser, query = utils.init_tree_sitter(CommentType.ts, Path("dummy.ts"))
    tree = parser.parse(code)
    assert not tree.root_node.has_error

    comments = utils.extract_comments(code, parser, query)
    assert comments is not None
    comments.sort(key=lambda node: node.start_point.row)
    texts = [node.text.decode("utf-8") for node in comments if node.text]
    assert texts == [
        "// @Top, IMPL_TOP",
        "// @Bottom, IMPL_BOTTOM",
        "// @Third, IMPL_THIRD",
    ]


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                void dummy_func1(){
                // @req-id: need_001
                }
            """,
            "void dummy_func1()",
        ),
        (
            b"""
                void dummy_func1(){
                /* @req-id: need_001 */
                }
            """,
            "void dummy_func1()",
        ),
    ],
)
def test_find_enclosing_scope_cpp(code, result, init_cpp_tree_sitter):
    parser, query = init_cpp_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_enclosing_scope(
        comments[0], CommentType.cpp
    )
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                public class DummyClass1
                {
                    // @req-id: need_001
                }
            """,
            "public class DummyClass1",
        ),
        (
            b"""
                public class DummyClass1
                {
                    public void DummyFunc1()
                    {
                        /* @req-id: need_001 */
                    }
                }
            """,
            "public void DummyFunc1()",
        ),
        (
            b"""
                public class DummyClass1
                {
                    public string DummyProperty1
                    {
                        get
                        {
                            /* @req-id: need_001 */
                            return "dummy";
                        }
                    }
                }
            """,
            "public string DummyProperty1",
        ),
    ],
)
def test_find_enclosing_scope_csharp(code, result, init_csharp_tree_sitter):
    parser, query = init_csharp_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_enclosing_scope(
        comments[0], CommentType.cs
    )
    assert node
    assert node.text
    func_def = node.text.decode("utf-8")
    assert result in func_def


@pytest.mark.parametrize(
    ("code", "num_comments", "result"),
    [
        (
            b"""
                // @req-id: need_001
                void dummy_func1(){
                }
            """,
            1,
            "// @req-id: need_001",
        ),
        (
            b"""
                void dummy_func1(){
                // @req-id: need_001
                }
            """,
            1,
            "// @req-id: need_001",
        ),
        (
            b"""
                /* @req-id: need_001 */
                void dummy_func1(){
                }
            """,
            1,
            "/* @req-id: need_001 */",
        ),
        (
            b"""
                //  @req-id: need_001
                //
                //
                void dummy_func1(){
                }
            """,
            3,
            "//  @req-id: need_001",
        ),
    ],
)
def test_cpp_comment(code, num_comments, result, init_cpp_tree_sitter):
    parser, query = init_cpp_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    assert len(comments) == num_comments
    comments.sort(key=lambda x: x.start_point.row)
    assert comments[0].text
    assert comments[0].text.decode("utf-8") == result


@pytest.mark.parametrize(
    ("code", "num_comments", "result"),
    [
        (
            b"""
                # @req-id: need_001
                def dummy_func1():
                    pass
            """,
            1,
            "# @req-id: need_001",
        ),
        (
            b"""
                def dummy_func1():
                    # @req-id: need_001
                    pass
            """,
            1,
            "# @req-id: need_001",
        ),
        (
            b"""
                # single line comment
                # @req-id: need_001
                def dummy_func1():
                    pass
            """,
            2,
            "# single line comment",
        ),
        (
            b"""
                def dummy_func1():
                    '''
                    @req-id: need_001
                    '''
                    pass
            """,
            1,
            "'''\n                    @req-id: need_001\n                    '''",
        ),
        (
            b"""
                def dummy_func1():
                    text = '''@req-id: need_001, need_002, this docstring shall not be extracted as comment'''
                    # @req-id: need_001
                    pass
            """,
            1,
            "# @req-id: need_001",
        ),
    ],
)
def test_python_comment(code, num_comments, result, init_python_tree_sitter):
    parser, query = init_python_tree_sitter
    comments: list[TreeSitterNode] = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)
    assert len(comments) == num_comments
    assert comments[0].text
    assert comments[0].text.decode("utf-8") == result


@pytest.mark.parametrize(
    ("code", "num_comments", "result"),
    [
        (
            b"""
                // @req-id: need_001
                void DummyFunc1(){
                }
            """,
            1,
            "// @req-id: need_001",
        ),
        (
            b"""
                void DummyFunc1(){
                // @req-id: need_001
                }
            """,
            1,
            "// @req-id: need_001",
        ),
        (
            b"""
                /* @req-id: need_001 */
                void DummyFunc1(){
                }
            """,
            1,
            "/* @req-id: need_001 */",
        ),
        (
            b"""
                //  @req-id: need_001
                //
                //
                void DummyFunc1(){
                }
            """,
            3,
            "//  @req-id: need_001",
        ),
    ],
)
def test_csharp_comment(code, num_comments, result, init_csharp_tree_sitter):
    parser, query = init_csharp_tree_sitter
    comments: list[TreeSitterNode] = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)
    assert len(comments) == num_comments
    assert comments[0].text
    assert comments[0].text.decode("utf-8") == result


@pytest.mark.parametrize(
    ("code", "num_comments", "result"),
    [
        (
            b"""
                // @req-id: need_001
                function dummyFunc1() {
                }
            """,
            1,
            "// @req-id: need_001",
        ),
        (
            b"""
                /* @req-id: need_001 */
                const value = 1;
            """,
            1,
            "/* @req-id: need_001 */",
        ),
    ],
)
def test_typescript_comment(code, num_comments, result, init_typescript_tree_sitter):
    parser, query = init_typescript_tree_sitter
    comments: list[TreeSitterNode] = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)
    assert len(comments) == num_comments
    assert comments[0].text
    assert comments[0].text.decode("utf-8") == result


@pytest.mark.parametrize(
    ("code", "num_comments", "result"),
    [
        (
            b"""
                # @req-id: need_001
                database:
                  host: localhost
            """,
            1,
            "# @req-id: need_001",
        ),
        (
            b"""
                services:
                  web:
                    # @req-id: need_001
                    image: nginx:latest
            """,
            1,
            "# @req-id: need_001",
        ),
        (
            b"""
                # Top level comment
                # @req-id: need_001
                version: "3.8"
            """,
            2,
            "# Top level comment",
        ),
    ],
)
def test_yaml_comment(code, num_comments, result, init_yaml_tree_sitter):
    parser, query = init_yaml_tree_sitter
    comments: list[TreeSitterNode] = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)
    assert len(comments) == num_comments
    assert comments[0].text
    assert comments[0].text.decode("utf-8") == result


@pytest.mark.parametrize(
    ("code", "num_comments", "result"),
    [
        (
            b"""
                // @req-id: need_001
                func dummyFunc1() {
                }
            """,
            1,
            "// @req-id: need_001",
        ),
        (
            b"""
                func dummyFunc1() {
                // @req-id: need_001
                }
            """,
            1,
            "// @req-id: need_001",
        ),
        (
            b"""
                /* @req-id: need_001 */
                func dummyFunc1() {
                }
            """,
            1,
            "/* @req-id: need_001 */",
        ),
        (
            b"""
                //  @req-id: need_001
                //
                //
                func dummyFunc1() {
                }
            """,
            3,
            "//  @req-id: need_001",
        ),
    ],
)
def test_go_comment(code, num_comments, result, init_go_tree_sitter):
    parser, query = init_go_tree_sitter
    comments: list[TreeSitterNode] = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)
    assert len(comments) == num_comments
    assert comments[0].text
    assert comments[0].text.decode("utf-8") == result


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                func dummyFunc1() {
                }
            """,
            "func dummyFunc1()",
        ),
        (
            b"""
                func dummyFunc2() {
                }
                // @req-id: need_001
                func dummyFunc1() {
                }
            """,
            "func dummyFunc1()",
        ),
        (
            b"""
                /* @req-id: need_001 */
                func dummyFunc1() {
                }
            """,
            "func dummyFunc1()",
        ),
    ],
)
def test_find_associated_scope_go(code, result, init_go_tree_sitter):
    parser, query = init_go_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_associated_scope(
        comments[0], CommentType.go
    )
    assert node
    assert node.text
    go_def = node.text.decode("utf-8")
    assert result in go_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                // @req-id: need_001
                func dummyFunc1() {
                }
            """,
            "func dummyFunc1()",
        ),
        (
            b"""
                // @req-id: need_001
                type DummyStruct struct {
                    Field int
                }
            """,
            "type DummyStruct struct",
        ),
    ],
)
def test_find_next_scope_go(code, result, init_go_tree_sitter):
    parser, query = init_go_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_next_scope(comments[0], CommentType.go)
    assert node
    assert node.text
    go_def = node.text.decode("utf-8")
    assert result in go_def


@pytest.mark.parametrize(
    ("code", "result"),
    [
        (
            b"""
                func dummyFunc1() {
                    // @req-id: need_001
                }
            """,
            "func dummyFunc1()",
        ),
        (
            b"""
                func dummyFunc1() {
                    /* @req-id: need_001 */
                }
            """,
            "func dummyFunc1()",
        ),
    ],
)
def test_find_enclosing_scope_go(code, result, init_go_tree_sitter):
    parser, query = init_go_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    node: TreeSitterNode | None = utils.find_enclosing_scope(
        comments[0], CommentType.go
    )
    assert node
    assert node.text
    go_def = node.text.decode("utf-8")
    assert result in go_def


@pytest.mark.parametrize(
    ("git_url", "rev", "project_path", "filepath", "lineno", "result"),
    [
        (
            "git@github.com:useblocks/sphinx-codelinks.git",
            "beef1234",
            Path(__file__).parent.parent,
            # ABSOLUTE, and under `project_path`. `form_https_url` resolves the
            # filepath with `.absolute()`, i.e. against the CWD, so a relative one
            # here only agrees with `project_path` when pytest happens to run from
            # the package directory -- which it does not when the whole workspace's
            # suite is invoked from the repository root
            Path(__file__).parent.parent / "example" / "to" / "here",
            3,
            "https://github.com/useblocks/sphinx-codelinks/blob/beef1234/example/to/here#L3",
        )
    ],
)
def test_form_https_url(
    git_url, rev, project_path, filepath, lineno, result
):  # need to have these args
    url = utils.form_https_url(git_url, rev, project_path, filepath, lineno=lineno)
    assert url == result


def get_git_path() -> str:
    """Get the path to the git executable."""
    git_path = shutil.which("git")
    if not git_path:
        raise FileNotFoundError("Git executable not found")
    if not Path(git_path).is_file():
        raise FileNotFoundError("Git executable path is invalid")
    return git_path


def init_git_repo(repo_path: Path, remote_url: str) -> Path:
    """Initialize a git repository for testing."""
    git_dir = repo_path / "test_repo"
    src_dir = git_dir / "src"
    src_dir.mkdir(parents=True)

    git_path = get_git_path()
    if not git_path:
        raise FileNotFoundError("Git executable not found")
    if not Path(git_path).is_file():
        raise FileNotFoundError("Git executable path is invalid")

    # Initialize git repo
    subprocess.run([git_path, "init"], cwd=git_dir, check=True, capture_output=True)
    subprocess.run(
        [git_path, "config", "user.email", "test@example.com"], cwd=git_dir, check=True
    )
    subprocess.run(
        [git_path, "config", "user.name", "Test User"], cwd=git_dir, check=True
    )

    # Create a test file and commit
    test_file = src_dir / "test_file.py"
    test_file.write_text("# Test file\nprint('hello')\n")
    subprocess.run([git_path, "add", "."], cwd=git_dir, check=True)
    subprocess.run(
        [git_path, "commit", "-m", "Initial commit"], cwd=git_dir, check=True
    )

    # Add a remote
    subprocess.run(
        [git_path, "remote", "add", "origin", remote_url],
        cwd=git_dir,
        check=True,
    )

    return git_dir


@pytest.fixture(
    params=[
        ("test_repo_git", "git@github.com:test-user/test-repo.git"),
        ("test_repo_https", "https://github.com/test-user/test-repo.git"),
    ]
)
def git_repo(tmp_path: str, request: pytest.FixtureRequest) -> tuple[Path, str]:
    """Create git repos for testing."""
    repo_name, remote_url = request.param
    repo_path = Path(tmp_path) / repo_name
    repo_path = init_git_repo(repo_path, remote_url)
    return repo_path, remote_url


def get_current_commit_hash(git_dir: Path) -> str:
    """Get the current commit hash of the git repository."""
    git_path = get_git_path()
    result = subprocess.run(
        [git_path, "rev-parse", "HEAD"],
        cwd=git_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    return str(result.stdout.strip())


def test_locate_git_root(git_repo: tuple[Path, str]) -> None:
    repo_path = git_repo[0]
    src_dir = repo_path / "src"
    git_root = utils.locate_git_root(src_dir)
    assert git_root == repo_path


def test_get_remote_url(git_repo: tuple[Path, str]) -> None:
    repo_path, expected_url = git_repo
    remote_url = utils.get_remote_url(repo_path)
    assert remote_url == expected_url


def test_get_current_rev(git_repo: tuple[Path, str]) -> None:
    repo_path, _ = git_repo
    current_rev = get_current_commit_hash(repo_path)
    assert current_rev == utils.get_current_rev(repo_path)


@pytest.fixture(params=["detached", "branch"])
def git_worktree(
    tmp_path: Path, request: pytest.FixtureRequest
) -> tuple[Path, str, str]:
    """A LINKED WORKTREE of a scratch repository, in both shapes git makes.

    A worktree is not a checkout with a `.git` directory: `.git` is a FILE holding
    `gitdir: <path>`, `config` lives in the main repository's git directory (named by
    the worktree's `commondir`), and only per-worktree state -- `HEAD` among it -- is in
    the worktree's own. `detached` puts a SHA in `HEAD`; `branch` puts `ref:
    refs/heads/...`, whose target is a shared ref in the common directory.

    This repository is worked in worktrees as a matter of routine, so a helper that
    demands a `.git` directory fails for every developer while staying green in CI
    (useblocks/sphinx-codelinks#106).
    """
    remote_url = "https://github.com/test-user/test-repo.git"
    repo_path = init_git_repo(tmp_path / "main", remote_url)
    git_path = get_git_path()
    worktree_path = tmp_path / "worktree"
    add = [git_path, "worktree", "add"]
    add += (
        ["--detach", str(worktree_path), "HEAD"]
        if request.param == "detached"
        else [str(worktree_path), "-b", "a-worktree-branch"]
    )
    subprocess.run(add, cwd=repo_path, check=True, capture_output=True)
    assert (worktree_path / ".git").is_file(), "a linked worktree's .git is a file"
    return worktree_path, remote_url, get_current_commit_hash(repo_path)


def test_locate_git_root_worktree(git_worktree: tuple[Path, str, str]) -> None:
    worktree_path, _, _ = git_worktree
    assert utils.locate_git_root(worktree_path / "src") == worktree_path


def test_get_remote_url_worktree(git_worktree: tuple[Path, str, str]) -> None:
    worktree_path, remote_url, _ = git_worktree
    assert utils.get_remote_url(worktree_path) == remote_url


def test_get_current_rev_worktree(git_worktree: tuple[Path, str, str]) -> None:
    worktree_path, _, rev = git_worktree
    assert utils.get_current_rev(worktree_path) == rev


def test_get_current_rev_packed_refs(git_worktree: tuple[Path, str, str]) -> None:
    """`git gc` packs the loose refs away, and the branch ref is then in `packed-refs`.

    Nothing unusual has to happen for this: `git gc` runs unattended on any long-lived
    checkout, and afterwards there is no `refs/heads/<branch>` FILE in either the
    worktree's git directory or the common one. It is the same failure shape as
    useblocks/sphinx-codelinks#106 reached by a different route -- and CI never sees it,
    because `actions/checkout` and Read the Docs both leave a detached HEAD.
    """
    worktree_path, _, rev = git_worktree
    git_path = get_git_path()
    subprocess.run(
        [git_path, "pack-refs", "--all"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )
    git_dir = utils._git_dir(worktree_path)
    assert git_dir is not None
    common = utils._git_common_dir(git_dir)
    assert not list((common / "refs" / "heads").glob("*")), (
        "the loose refs should be gone"
    )

    assert utils.get_current_rev(worktree_path) == rev


def test_get_current_rev_detached_head(tmp_path: Path) -> None:
    """In a detached HEAD (e.g. CI checkouts) .git/HEAD holds the commit SHA
    directly; get_current_rev returns it rather than warning and giving up."""
    git_root = tmp_path / "repo"
    (git_root / ".git").mkdir(parents=True)
    sha = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    (git_root / ".git" / "HEAD").write_text(f"{sha}\n")

    assert utils.get_current_rev(git_root) == sha


# ========== YAML-specific tests ==========


@pytest.mark.parametrize(
    ("code", "expected_structure"),
    [
        # Basic key-value pair
        (
            b"""
                # Comment before key
                database:
                  host: localhost
            """,
            "database:",
        ),
        # Comment in nested structure
        (
            b"""
                services:
                  web:
                    # Comment before image
                    image: nginx:latest
            """,
            "image: nginx:latest",
        ),
        # Comment before list item
        (
            b"""
                items:
                  # Comment before list item
                  - name: item1
                    value: test
            """,
            "- name: item1",
        ),
        # Comment in document structure
        (
            b"""---
# Comment in document
version: "3.8"
services:
  app:
    build: .
            """,
            "version:",
        ),
        # Flow mapping structure
        (
            b"""
                # Comment before flow mapping
                config: {debug: true, port: 8080}
            """,
            "config:",
        ),
    ],
)
def test_find_yaml_next_structure(code, expected_structure, init_yaml_tree_sitter):
    """Test the find_yaml_next_structure function."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    assert comments, "No comments found in the code"

    next_structure = utils.find_yaml_next_structure(comments[0])
    assert next_structure, "No next structure found"
    structure_text = next_structure.text.decode("utf-8")
    assert expected_structure in structure_text


@pytest.mark.parametrize(
    ("code", "expected_structure"),
    [
        # Comment associated with key-value pair
        (
            b"""
                # Database configuration
                database:
                  host: localhost
                  port: 5432
            """,
            "database:",
        ),
        # Comment associated with nested structure
        (
            b"""
                services:
                  web:
                    # Web service image
                    image: nginx:latest
                    ports:
                      - "80:80"
            """,
            "image: nginx:latest",
        ),
        # Comment associated with list item
        (
            b"""
                dependencies:
                  # First dependency
                  - name: redis
                    version: "6.0"
                  - name: postgres
                    version: "13"
            """,
            "- name: redis",
        ),
        # Comment inside parent structure
        (
            b"""
                app:
                  # Internal comment
                  name: myapp
                  version: "1.0"
            """,
            "name: myapp",
        ),
    ],
)
def test_find_yaml_associated_structure(
    code, expected_structure, init_yaml_tree_sitter
):
    """Test the find_yaml_associated_structure function."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    assert comments, "No comments found in the code"

    associated_structure = utils.find_yaml_associated_structure(comments[0])
    assert associated_structure, "No associated structure found"
    structure_text = associated_structure.text.decode("utf-8")
    assert expected_structure in structure_text


@pytest.mark.parametrize(
    ("code", "expected_results"),
    [
        # Multiple comments in sequence
        (
            b"""
                # First comment
                # Second comment
                database:
                  host: localhost
            """,
            ["database:", "database:"],  # Both comments should associate with database
        ),
        # Comments at different nesting levels
        (
            b"""
                # Top level comment
                services:
                  web:
                    # Nested comment
                    image: nginx:latest
            """,
            ["services:", "image: nginx:latest"],
        ),
    ],
)
def test_multiple_yaml_comments(code, expected_results, init_yaml_tree_sitter):
    """Test handling of multiple YAML comments in the same file."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)

    assert len(comments) == len(expected_results), (
        f"Expected {len(expected_results)} comments, found {len(comments)}"
    )

    for i, comment in enumerate(comments):
        associated_structure = utils.find_yaml_associated_structure(comment)
        assert associated_structure, f"No associated structure found for comment {i}"
        structure_text = associated_structure.text.decode("utf-8")
        assert expected_results[i] in structure_text


@pytest.mark.parametrize(
    ("code", "has_structure"),
    [
        # Comment at end of file with no following structure
        (
            b"""
database:
  host: localhost
# End of file comment
            """,
            True,  # This will actually find the parent database structure
        ),
        # Comment with only whitespace after
        (
            b"""
                # Lonely comment


            """,
            False,
        ),
        # Comment before valid structure
        (
            b"""
                # Valid comment
                key: value
            """,
            True,
        ),
    ],
)
def test_yaml_edge_cases(code, has_structure, init_yaml_tree_sitter):
    """Test edge cases in YAML comment processing."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)

    if comments:
        structure = utils.find_yaml_associated_structure(comments[0])
        if has_structure:
            assert structure, "Expected to find associated structure"
        else:
            assert structure is None, "Expected no associated structure"
    else:
        assert not has_structure, "No comments found but structure was expected"


@pytest.mark.parametrize(
    ("code", "expected_structures"),
    [
        # Simpler nested YAML structure
        (
            b"""# Global configuration
version: "3.8"

# Services section
services:
  web:
    image: nginx:latest
    # Port configuration
    ports:
      - "80:80"
            """,
            [
                "version:",  # Global configuration
                "services:",  # Services section
                '- "80:80"',  # Port configuration
            ],
        ),
    ],
)
def test_complex_yaml_structure(code, expected_structures, init_yaml_tree_sitter):
    """Test complex nested YAML structures with multiple comments."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)

    assert len(comments) == len(expected_structures), (
        f"Expected {len(expected_structures)} comments, found {len(comments)}"
    )

    for i, comment in enumerate(comments):
        associated_structure = utils.find_yaml_associated_structure(comment)
        assert associated_structure, f"No associated structure found for comment {i}"
        structure_text = associated_structure.text.decode("utf-8")
        assert expected_structures[i] in structure_text, (
            f"Expected '{expected_structures[i]}' in structure text: '{structure_text}'"
        )


@pytest.mark.parametrize(
    ("code", "expected_type"),
    [
        # Block mapping pair
        (
            b"""
                # Comment
                key: value
            """,
            "block_mapping_pair",
        ),
        # Block sequence item
        (
            b"""
                items:
                  # Comment
                  - item1
            """,
            "block_sequence_item",
        ),
        # Nested block mapping
        (
            b"""
                services:
                  # Comment
                  web:
                    image: nginx
            """,
            "block_mapping_pair",
        ),
    ],
)
def test_yaml_structure_types(code, expected_type, init_yaml_tree_sitter):
    """Test that YAML structures return the correct node types."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    assert comments, "No comments found"

    structure = utils.find_yaml_associated_structure(comments[0])
    assert structure, "No associated structure found"
    assert structure.type == expected_type, (
        f"Expected type {expected_type}, got {structure.type}"
    )


def test_yaml_document_structure(init_yaml_tree_sitter):
    """Test YAML document structure handling."""
    code = b"""---
# Document comment
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-config
data:
  # Data comment
  config.yml: |
    setting: value
    """

    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)

    # Should find both comments
    assert len(comments) >= 2, f"Expected at least 2 comments, found {len(comments)}"

    # First comment should associate with apiVersion
    first_structure = utils.find_yaml_associated_structure(comments[0])
    assert first_structure, "No structure found for first comment"
    first_text = first_structure.text.decode("utf-8")
    assert "apiVersion:" in first_text

    # Second comment should associate with config.yml
    second_structure = utils.find_yaml_associated_structure(comments[1])
    assert second_structure, "No structure found for second comment"
    second_text = second_structure.text.decode("utf-8")
    assert "config.yml:" in second_text


def test_yaml_inline_comments_current_behavior(init_yaml_tree_sitter):
    """Test improved behavior of inline comments in YAML after the fix."""
    code = b"""key1: value1  # inline comment about key1
key2: value2
key3: value3  # inline comment about key3
"""

    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)

    assert len(comments) == 2, f"Expected 2 comments, found {len(comments)}"

    # Fixed behavior: inline comment about key1 now correctly associates with key1
    first_structure = utils.find_yaml_associated_structure(comments[0])
    assert first_structure, "No structure found for first comment"
    first_text = first_structure.text.decode("utf-8")
    assert "key1:" in first_text, f"Expected 'key1:' in '{first_text}'"

    # Fixed behavior: inline comment about key3 now correctly associates with key3
    second_structure = utils.find_yaml_associated_structure(comments[1])
    assert second_structure, "No structure found for second comment"
    second_text = second_structure.text.decode("utf-8")
    assert "key3:" in second_text, f"Expected 'key3:' in '{second_text}'"


@pytest.mark.parametrize(
    ("code", "expected_associations"),
    [
        # Basic inline comment case
        (
            b"""key1: value1  # comment about key1
key2: value2
            """,
            ["key1:"],  # Now correctly associates with key1
        ),
        # Multiple inline comments
        (
            b"""database:
  host: localhost  # production server
  port: 5432       # default postgres port
  user: admin
            """,
            [
                "host: localhost",
                "port: 5432",
            ],  # Now correctly associates with the right structures
        ),
    ],
)
def test_yaml_inline_comments_fixed_behavior(
    code, expected_associations, init_yaml_tree_sitter
):
    """Test that inline comments now correctly associate with the structure they comment on."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)

    assert len(comments) == len(expected_associations), (
        f"Expected {len(expected_associations)} comments, found {len(comments)}"
    )

    for i, comment in enumerate(comments):
        structure = utils.find_yaml_associated_structure(comment)
        assert structure, f"No structure found for comment {i}"
        structure_text = structure.text.decode("utf-8")
        assert expected_associations[i] in structure_text, (
            f"Expected '{expected_associations[i]}' in structure text: '{structure_text}'"
        )


@pytest.mark.parametrize(
    ("code", "expected_associations"),
    [
        # Inline comments with list items
        (
            b"""items:
  - name: item1  # first item
  - name: item2  # second item
            """,
            [
                "name: item1",
                "name: item2",
            ],  # The inline comment finds the key-value pair within the list item
        ),
        # Mixed inline and block comments
        (
            b"""# Block comment for database
database:
  host: localhost  # inline comment for host
  port: 5432
  # Block comment for user
  user: admin
            """,
            ["database:", "host: localhost", "user: admin"],
        ),
        # Inline comments in nested structures
        (
            b"""services:
  web:
    image: nginx  # web server image
    ports:
      - "80:80"   # http port
            """,
            ["image: nginx", '- "80:80"'],
        ),
    ],
)
def test_yaml_inline_comments_comprehensive(
    code, expected_associations, init_yaml_tree_sitter
):
    """Comprehensive test for inline comment behavior in various YAML structures."""
    parser, query = init_yaml_tree_sitter
    comments = utils.extract_comments(code, parser, query)
    comments.sort(key=lambda x: x.start_point.row)

    assert len(comments) == len(expected_associations), (
        f"Expected {len(expected_associations)} comments, found {len(comments)}"
    )

    for i, comment in enumerate(comments):
        structure = utils.find_yaml_associated_structure(comment)
        assert structure, (
            f"No structure found for comment {i}: '{comment.text.decode('utf-8')}'"
        )
        structure_text = structure.text.decode("utf-8")
        assert expected_associations[i] in structure_text, (
            f"Comment {i} '{comment.text.decode('utf-8')}' -> Expected '{expected_associations[i]}' in '{structure_text}'"
        )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("a@file.com", False, id="address"),
        pytest.param("x@module", False, id="no-left-boundary"),
        pytest.param("* @file", True, id="after-star"),
        pytest.param("\\file widget.h", True, id="backslash-at-start"),
        pytest.param("@filename", False, id="longer-word"),
        pytest.param("@file_x", False, id="underscore"),
        pytest.param("/// @fileoverview Widgets.", True, id="fileoverview"),
        pytest.param("@fileͅ x", True, id="non-ascii-mark-ends-the-word"),
    ],
)
def test_documents_file(text: str, expected: bool) -> None:
    """A file tag counts at the start of the text or after whitespace, ``*``, ``/`` or
    ``!``, and only as a whole ASCII word: an address or a longer word never counts,
    and a non-ASCII mark ends the word rather than extending it."""
    assert utils.documents_file(text) is expected
