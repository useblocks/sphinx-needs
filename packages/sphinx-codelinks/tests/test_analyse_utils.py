from pathlib import Path
import shutil
import subprocess

import pytest
from tree_sitter import Language, Parser, Query
from tree_sitter import Node as TreeSitterNode
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_python
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
