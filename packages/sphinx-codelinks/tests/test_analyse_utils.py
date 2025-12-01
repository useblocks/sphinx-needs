# @Test suite for tree-sitter parsing utilities and language support, TEST_LANG_1, test, [IMPL_LANG_1, IMPL_EXTR_1, IMPL_RST_1]
from pathlib import Path
import shutil
import subprocess

import pytest
from tree_sitter import Language, Parser, Query
from tree_sitter import Node as TreeSitterNode
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_python
import tree_sitter_rust
import tree_sitter_yaml

from sphinx_codelinks.analyse import utils
from sphinx_codelinks.config import UNIX_NEWLINE
from sphinx_codelinks.source_discover.config import CommentType


@pytest.fixture(scope="session")
def init_cpp_tree_sitter() -> tuple[Parser, Query]:
    parsed_language = Language(tree_sitter_cpp.language())
    query = Query(parsed_language, utils.CPP_QUERY)
    parser = Parser(parsed_language)
    return parser, query


@pytest.fixture(scope="session")
def init_python_tree_sitter() -> tuple[Parser, Query]:
    parsed_language = Language(tree_sitter_python.language())
    query = Query(parsed_language, utils.PYTHON_QUERY)
    parser = Parser(parsed_language)
    return parser, query


@pytest.fixture(scope="session")
def init_csharp_tree_sitter() -> tuple[Parser, Query]:
    parsed_language = Language(tree_sitter_c_sharp.language())
    query = Query(parsed_language, utils.C_SHARP_QUERY)
    parser = Parser(parsed_language)
    return parser, query


@pytest.fixture(scope="session")
def init_yaml_tree_sitter() -> tuple[Parser, Query]:
    parsed_language = Language(tree_sitter_yaml.language())
    query = Query(parsed_language, utils.YAML_QUERY)
    parser = Parser(parsed_language)
    return parser, query


@pytest.fixture(scope="session")
def init_rust_tree_sitter() -> tuple[Parser, Query]:
    parsed_language = Language(tree_sitter_rust.language())
    query = Query(parsed_language, utils.RUST_QUERY)
    parser = Parser(parsed_language)
    return parser, query


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
    ("git_url", "rev", "project_path", "filepath", "lineno", "result"),
    [
        (
            "git@github.com:useblocks/sphinx-codelinks.git",
            "beef1234",
            Path(__file__).parent.parent,
            Path("example") / "to" / "here",
            3,
            "https://github.com/useblocks/sphinx-codelinks/blob/beef1234/example/to/here#L3",
        )
    ],
)
def test_form_https_url(git_url, rev, project_path, filepath, lineno, result):  # noqa: PLR0913  # need to have these args
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
    subprocess.run([git_path, "init"], cwd=git_dir, check=True, capture_output=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [git_path, "config", "user.email", "test@example.com"], cwd=git_dir, check=True
    )
    subprocess.run(  # noqa: S603
        [git_path, "config", "user.name", "Test User"], cwd=git_dir, check=True
    )

    # Create a test file and commit
    test_file = src_dir / "test_file.py"
    test_file.write_text("# Test file\nprint('hello')\n")
    subprocess.run([git_path, "add", "."], cwd=git_dir, check=True)  # noqa: S603
    subprocess.run(  # noqa: S603
        [git_path, "commit", "-m", "Initial commit"], cwd=git_dir, check=True
    )

    # Add a remote
    subprocess.run(  # noqa: S603
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
    result = subprocess.run(  # noqa: S603
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


@pytest.mark.parametrize(
    ("text", "leading_sequences", "result"),
    [
        (
            """
*    some text in a comment
*    some text in a comment
*
""",
            ["*"],
            """
    some text in a comment
    some text in a comment

""",
        ),
    ],
)
def test_remove_leading_sequences(text, leading_sequences, result):
    clean_text = utils.remove_leading_sequences(text, leading_sequences)
    assert clean_text == result


@pytest.mark.parametrize(
    ("text", "rst_markers", "rst_text", "positions"),
    [
        (
            """
@rst
.. impl:: multiline rst text
   :id: IMPL_71
@endrst
""",
            ["@rst", "@endrst"],
            f""".. impl:: multiline rst text{UNIX_NEWLINE}   :id: IMPL_71{UNIX_NEWLINE}""",
            {"row_offset": 1, "start_idx": 6, "end_idx": 51},
        ),
        (
            """
@rst.. impl:: oneline rst text@endrst
""",
            ["@rst", "@endrst"],
            """.. impl:: oneline rst text""",
            {"row_offset": 0, "start_idx": 5, "end_idx": 31},
        ),
    ],
)
def test_extract_rst(text, rst_markers, rst_text, positions):
    extracted_rst = utils.extract_rst(text, rst_markers[0], rst_markers[1])
    assert extracted_rst is not None
    assert extracted_rst["rst_text"] == rst_text
    assert extracted_rst["start_idx"] == positions["start_idx"]
    assert extracted_rst["end_idx"] == positions["end_idx"]


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
