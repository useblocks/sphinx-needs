# @Test suite for source code analysis and marker extraction, TEST_ANA_1, test, [IMPL_LNK_1, IMPL_ONE_1, IMPL_MLN_1]
import json
from pathlib import Path

import pytest

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse, _count
from sphinx_codelinks.analyse.utils import NotText, decode_source
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig
from sphinx_codelinks.source_discover.config import CommentType
from tests.conftest import (
    ONELINE_COMMENT_STYLE,
    ONELINE_COMMENT_STYLE_DEFAULT,
    TEST_DIR,
)

TEST_DATA_DIR = Path(__file__).parent.parent / "tests" / "data"


@pytest.mark.parametrize(
    ("src_dir", "src_paths"),
    [
        (
            TEST_DATA_DIR,
            [
                TEST_DATA_DIR / "oneline_comment_default" / "default_oneliners.c",
                TEST_DATA_DIR / "need_id_refs" / "dummy_1.cpp",
                TEST_DATA_DIR / "multiline_needs" / "dummy_1.cpp",
            ],
        )
    ],
)
def test_analyse(src_dir, src_paths, tmp_path, snapshot_marks):
    src_analyse_config = SourceAnalyseConfig(
        src_files=src_paths,
        src_dir=src_dir,
        get_need_id_refs=True,
        get_oneline_needs=True,
        get_multiline_needs=True,
    )

    analyse = SourceAnalyse(src_analyse_config)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    analyse.dump_marked_content(tmp_path)

    dumped_content = tmp_path / "marked_content.json"
    with dumped_content.open("r") as f:
        marked_content = json.load(f)
    # normalize filepath
    for obj in marked_content:
        obj["filepath"] = (
            Path(obj["filepath"]).relative_to(src_analyse_config.src_dir)
        ).as_posix()
        if "source" in obj:
            # a multi-line need's path is relative to the git root when the checkout is
            # a repository, else to src_dir: pin it against src_dir, as filepath is
            assert obj["source"].pop("root") in ("git", "src_dir")
            assert obj["source"]["path"].endswith(obj["filepath"])
            obj["source"]["path"] = obj["filepath"]
    assert marked_content == snapshot_marks


@pytest.mark.parametrize(
    "case",
    [
        {
            "src_dir": TEST_DIR / "data" / "dcdc",
            "src_paths": [
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_1.cpp",
                TEST_DIR / "data" / "dcdc" / "charge" / "demo_2.cpp",
                TEST_DIR / "data" / "dcdc" / "discharge" / "demo_3.cpp",
                TEST_DIR / "data" / "dcdc" / "supercharge.cpp",
            ],
            "comment_type": CommentType.cpp,
            "oneline_comment_style": ONELINE_COMMENT_STYLE,
            "result": {
                "num_src_files": 4,
                "num_uncached_files": 4,
                "num_cached_files": 0,
                "num_comments": 29,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 12,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "oneline_comment_basic",
            "src_paths": [
                TEST_DIR / "data" / "oneline_comment_basic" / "basic_oneliners.c",
            ],
            "comment_type": CommentType.cpp,
            "oneline_comment_style": ONELINE_COMMENT_STYLE,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 14,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 8,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "oneline_comment_default",
            "src_paths": [
                TEST_DIR / "data" / "oneline_comment_default" / "default_oneliners.c",
            ],
            "comment_type": CommentType.cpp,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 5,
                "num_oneline_warnings": 1,
                "num_oneline_needs": 4,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "rust",
            "src_paths": [
                TEST_DIR / "data" / "rust" / "demo.rs",
            ],
            "comment_type": CommentType.rust,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 6,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 4,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "typescript",
            "src_paths": [
                TEST_DIR / "data" / "typescript" / "demo.ts",
            ],
            "comment_type": CommentType.ts,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 4,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 1,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "typescript",
            "src_paths": [
                TEST_DIR / "data" / "typescript" / "demo.tsx",
            ],
            "comment_type": CommentType.ts,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 1,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 1,
            },
        },
        {
            "src_dir": TEST_DIR / "data" / "jsonc",
            "src_paths": [
                TEST_DIR / "data" / "jsonc" / "demo.jsonc",
            ],
            "comment_type": CommentType.jsonc,
            "oneline_comment_style": ONELINE_COMMENT_STYLE_DEFAULT,
            "result": {
                "num_src_files": 1,
                "num_uncached_files": 1,
                "num_cached_files": 0,
                "num_comments": 4,
                "num_oneline_warnings": 0,
                "num_oneline_needs": 3,
            },
        },
    ],
)
def test_analyse_oneline_needs(tmp_path, case):
    src_analyse_config = SourceAnalyseConfig(
        src_files=case["src_paths"],
        src_dir=case["src_dir"],
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_multiline_needs=False,
        oneline_comment_style=case["oneline_comment_style"],
        comment_type=case["comment_type"],
    )
    src_analyse = SourceAnalyse(src_analyse_config)
    src_analyse.run()

    result = case["result"]
    assert len(src_analyse.src_files) == result["num_src_files"]
    assert len(src_analyse.warnings) == result["num_oneline_warnings"]
    assert len(src_analyse.oneline_needs) == result["num_oneline_needs"]

    cnt_comments = 0
    for src_file in src_analyse.src_files:
        cnt_comments += len(src_file.src_comments)
    assert cnt_comments == result["num_comments"]


def test_explicit_git_root_configuration(tmp_path):
    """Test that explicit git_root configuration is used instead of auto-detection."""
    # Create a fake git repo structure in tmp_path
    fake_git_root = tmp_path / "fake_repo"
    fake_git_root.mkdir()
    (fake_git_root / ".git").mkdir()

    # Create a minimal .git/config with remote URL
    git_config = fake_git_root / ".git" / "config"
    git_config.write_text(
        '[remote "origin"]\n    url = https://github.com/test/repo.git\n'
    )

    # Create HEAD file pointing to a branch ref
    git_head = fake_git_root / ".git" / "HEAD"
    git_head.write_text("ref: refs/heads/main\n")

    # Create the refs/heads/main file with the commit hash
    refs_dir = fake_git_root / ".git" / "refs" / "heads"
    refs_dir.mkdir(parents=True)
    (refs_dir / "main").write_text("abc123def456\n")

    # Create source file in a deeply nested location
    src_dir = tmp_path / "deeply" / "nested" / "src"
    src_dir.mkdir(parents=True)
    src_file = src_dir / "test.c"
    src_file.write_text("// @Test, TEST_1\nvoid test() {}\n")

    # Configure with explicit git_root
    src_analyse_config = SourceAnalyseConfig(
        src_files=[src_file],
        src_dir=src_dir,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_multiline_needs=False,
        git_root=fake_git_root,
    )

    src_analyse = SourceAnalyse(src_analyse_config)

    # Verify the explicit git_root was used
    assert src_analyse.git_root == fake_git_root.resolve()
    assert src_analyse.git_remote_url == "https://github.com/test/repo.git"
    assert src_analyse.git_commit_rev == "abc123def456"


def test_git_root_auto_detection_when_not_configured(tmp_path):
    """Test that git_root is auto-detected when not explicitly configured."""
    src_dir = TEST_DIR / "data" / "dcdc"
    src_paths = [src_dir / "charge" / "demo_1.cpp"]

    # Don't set git_root - it should auto-detect
    src_analyse_config = SourceAnalyseConfig(
        src_files=src_paths,
        src_dir=src_dir,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_multiline_needs=False,
        # git_root is not set, so auto-detection should be used
    )

    src_analyse = SourceAnalyse(src_analyse_config)

    # The test is running inside a git repo, so git_root should be detected
    # We just verify it's not None (since this test runs in the sphinx-codelinks repo)
    assert src_analyse.git_root is not None
    assert (src_analyse.git_root / ".git").exists()


def test_oneline_parser_warnings_are_collected(tmp_path):
    """Test that oneline parser warnings are collected for later output."""
    src_dir = TEST_DIR / "data" / "oneline_comment_default"
    src_paths = [src_dir / "default_oneliners.c"]
    src_analyse_config = SourceAnalyseConfig(
        src_files=src_paths,
        src_dir=src_dir,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_multiline_needs=False,
        oneline_comment_style=ONELINE_COMMENT_STYLE_DEFAULT,
    )
    src_analyse = SourceAnalyse(src_analyse_config)
    src_analyse.run()

    # Verify that warnings were collected
    assert len(src_analyse.warnings) == 1
    warning = src_analyse.warnings[0]
    assert "too_many_fields" in warning.sub_type
    assert warning.lineno == 17
    # the old name reads the same list, for one release
    assert src_analyse.oneline_warnings is src_analyse.warnings


def test_a_hash_comment_is_never_a_docstring_tag(tmp_path: Path) -> None:
    """The ``docstring_tag`` rule reads Python docstrings only: a field-shaped tag line
    in a ``#`` comment goes to the one-line parser, as in any other language."""
    src = tmp_path / "x.py"
    src.write_text(
        "# @param a: the first, thing\ndef f(a):\n    pass\n", encoding="utf-8"
    )
    src_analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[src],
            src_dir=tmp_path,
            comment_type=CommentType.python,
            get_need_id_refs=False,
            get_oneline_needs=True,
            get_multiline_needs=False,
            oneline_comment_style=ONELINE_COMMENT_STYLE_DEFAULT,
        )
    )
    src_analyse.run()

    assert src_analyse.warnings == []
    assert [need.need["id"] for need in src_analyse.oneline_needs] == ["thing"]


@pytest.mark.parametrize("ts_first", [True, False], ids=["ts-first", "tsx-first"])
def test_a_ts_and_a_tsx_file_in_one_run_each_get_their_grammar(
    tmp_path: Path, ts_first: bool
) -> None:
    """One analysis of a ``.ts`` and a ``.tsx`` file parses each with its own
    grammar, whichever comes first: the ``.ts`` marker after a ``<T>`` cast is kept
    (the TypeScript grammar), and the ``//`` in the ``.tsx`` file's JSX text is text,
    not a marker (the TSX grammar)."""
    ts_src = tmp_path / "a.ts"
    ts_src.write_text(
        "// @Before cast, IMPL_BEFORE, impl\n"
        "const v = <string>x;\n"
        "// @After cast, IMPL_AFTER, impl\n"
        "function g(): void {}\n",
        encoding="utf-8",
    )
    tsx_src = tmp_path / "b.tsx"
    tsx_src.write_text(
        "// @Component, IMPL_COMPONENT, impl\n"
        "export const A = () => <p>// @Fake, FAKE_ID, impl</p>;\n",
        encoding="utf-8",
    )
    src_analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[ts_src, tsx_src] if ts_first else [tsx_src, ts_src],
            src_dir=tmp_path,
            comment_type=CommentType.ts,
            get_need_id_refs=False,
            get_oneline_needs=True,
            get_multiline_needs=False,
            oneline_comment_style=ONELINE_COMMENT_STYLE_DEFAULT,
        )
    )
    src_analyse.run()

    assert sorted(need.need["id"] for need in src_analyse.oneline_needs) == [
        "IMPL_AFTER",
        "IMPL_BEFORE",
        "IMPL_COMPONENT",
    ]


def test_count_pluralizes_nouns() -> None:
    assert _count(0, "file") == "0 files"
    assert _count(1, "file") == "1 file"
    assert _count(2, "marker") == "2 markers"
    assert _count(1, "multi-line need") == "1 multi-line need"


def test_dump_marked_content_when_its_directory_appears_after_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another process may create the output directory between a check for it and the
    ``mkdir``: the dump must not fail with ``FileExistsError`` then."""
    outdir = tmp_path / "out"
    real_exists = Path.exists

    def exists_then_created_elsewhere(self: Path, *args, **kwargs) -> bool:
        found = real_exists(self, *args, **kwargs)
        if self == outdir and not found:
            outdir.mkdir()  # the other process wins the race
        return found

    analyse = SourceAnalyse(SourceAnalyseConfig(src_files=[], src_dir=tmp_path))
    monkeypatch.setattr(Path, "exists", exists_then_created_elsewhere)
    analyse.dump_marked_content(outdir)

    marked = json.loads((outdir / "marked_content.json").read_text(encoding="utf-8"))
    assert marked == []


def test_a_bom_before_a_powershell_marker_keeps_the_title_clean(tmp_path: Path):
    """Windows PowerShell 5.1 saves a script with a UTF-8 BOM: the marker on the
    first line is still a need on that line, and the BOM is not part of its title."""
    source = tmp_path / "demo.ps1"
    source.write_bytes("﻿# @Bom Title, IMPL_BOM, impl\nfunction f { }\n".encode())
    config = SourceAnalyseConfig(
        src_files=[source],
        src_dir=tmp_path,
        get_oneline_needs=True,
        comment_type=CommentType.powershell,
    )
    analyse = SourceAnalyse(config)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()

    assert len(analyse.oneline_needs) == 1
    need = analyse.oneline_needs[0]
    assert need.need["title"] == "Bom Title"
    assert need.need["id"] == "IMPL_BOM"
    assert need.source_map["start"]["row"] == 0


def _oneline_run(
    tmp_path: Path, name: str, source: str, comment_type: CommentType
) -> SourceAnalyse:
    """One file analysed with the default one-line style, outside a repository."""
    path = tmp_path / name
    path.write_bytes(source.encode())
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[path],
            src_dir=tmp_path,
            get_oneline_needs=True,
            comment_type=comment_type,
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return analyse


POWERSHELL_LITERALS = """\
# @{ Keys = 'k' }, $Value.Keys is the string 'k' and not an array
# @() or $null is provided and allowed, do nothing
#   @($null) which evaluates to false, even though, it is
# `@(9, 9, 1) -eq 1` returns 1, not a list
<#
.EXAMPLE
    @{ Name = 'Jakub'; Age = 30 } | Should-BeHashtable -Key Name, Age
    @(1, 2, 3) | Should-BeHashtable
#>
# @Real, IMPL_PS_REAL, impl
function Start-Demo { }
"""


def test_a_powershell_hashtable_or_array_is_no_marker(tmp_path: Path) -> None:
    """PowerShell's ``@`` is the sigil of a hashtable ``@{ }`` and an array ``@( )``,
    which commented-out code and ``.EXAMPLE`` help hold at the start of a line: the
    start sequence directly followed by ``{`` or ``(`` opens no marker, and no
    warning."""
    analyse = _oneline_run(
        tmp_path, "demo.ps1", POWERSHELL_LITERALS, CommentType.powershell
    )

    assert [need.need["id"] for need in analyse.oneline_needs] == ["IMPL_PS_REAL"]
    assert analyse.warnings == []


def test_a_brace_after_the_start_sequence_is_a_marker_elsewhere(
    tmp_path: Path,
) -> None:
    """The rule is PowerShell's: in another language, ``@{`` opens a marker as
    before."""
    analyse = _oneline_run(
        tmp_path,
        "demo.py",
        "# @{ a }, ID_PY, impl\ndef f(): pass\n",
        CommentType.python,
    )

    assert [need.need["id"] for need in analyse.oneline_needs] == ["ID_PY"]


def test_a_powershell_title_cannot_open_with_a_parenthesis_or_a_brace(
    tmp_path: Path,
) -> None:
    """The hashtable and array rule is deliberate and has a cost: a marker whose title
    starts with ``(`` or ``{`` is read as ``@(`` or ``@{``, and is dropped without a
    warning, as the documentation says. Only PowerShell pays it."""
    source = (
        "# @(Draft) Login handler, S1_PAREN, impl, [R]\n"
        "# @{Braced} title, S1_BRACE, impl\n"
        "function Start-Login { }\n"
    )
    analyse = _oneline_run(tmp_path, "login.ps1", source, CommentType.powershell)

    assert analyse.oneline_needs == []
    assert analyse.warnings == []

    other = _oneline_run(tmp_path, "login.py", source, CommentType.python)
    assert [need.need["id"] for need in other.oneline_needs] == [
        "S1_PAREN",
        "S1_BRACE",
    ]


SWIFT_ATTRIBUTES = """\
// @available(iOS 15, macOS 12, *)
/// @Available(Swift, introduced: 6.3)
/// @Flag(name: [.short, .long])
//@available(SwiftStdlib 5.0, *)
// @objc(handle:)
// @Real, IMPL_SWIFT_REAL, impl
func handle() {}
"""


def test_a_swift_attribute_is_no_marker(tmp_path: Path) -> None:
    """Under the start sequence ``@``, a Swift comment line holding an attribute's
    shape, ``@name(``, is no need: a ``swift_attribute`` warning where the one-line
    parser would have read it (a need, or a malformed one), silence where it would not
    (``@objc(handle:)`` holds no field separator)."""
    analyse = _oneline_run(tmp_path, "demo.swift", SWIFT_ATTRIBUTES, CommentType.swift)

    assert [need.need["id"] for need in analyse.oneline_needs] == ["IMPL_SWIFT_REAL"]
    assert [(w.lineno, w.sub_type) for w in analyse.warnings] == [
        (1, "swift_attribute"),
        (2, "swift_attribute"),
        (3, "swift_attribute"),
        (4, "swift_attribute"),
    ]
    assert analyse.warnings[0].msg == (
        "'@available' is a Swift attribute, not a one-line need; use a start "
        "sequence that Swift attributes do not contain"
    )


def test_a_swift_attribute_is_a_marker_elsewhere(tmp_path: Path) -> None:
    """The rule is Swift's: in another language, the same line is a need as before."""
    analyse = _oneline_run(
        tmp_path, "demo.cpp", "// @available(iOS 15, *)\nvoid f() {}\n", CommentType.cpp
    )

    assert [need.need["id"] for need in analyse.oneline_needs] == ["*)"]


class _RecordingLogger:
    """Records the analysis' logger warnings with their subtype and location (the
    real logger is slotted, so the module-level one is swapped)."""

    def __init__(self) -> None:
        self.warnings: list[tuple[str, str, str | None]] = []

    def warning(
        self, msg: str, *, subtype: str = "", location: str | None = None
    ) -> None:
        self.warnings.append((msg, subtype, location))

    def info(self, *_a: object, **_k: object) -> None:
        pass

    def debug(self, *_a: object, **_k: object) -> None:
        pass


#: the two engines that read a C/C++ file; both apply one rule to its bytes
ENGINES = ["treesitter", "libclang"]


def _cpp_run(
    tmp_path: Path,
    files: dict[str, bytes],
    engine: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[SourceAnalyse, _RecordingLogger]:
    """The files analysed as C++ by ``engine`` with the default one-line style,
    outside a repository, with the warnings the analysis logged."""
    if engine == "libclang":
        pytest.importorskip("clang.cindex")
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[tmp_path / name for name in files],
            src_dir=tmp_path,
            get_oneline_needs=True,
            comment_type=CommentType.cpp,
            preprocessor=PreprocessorConfig() if engine == "libclang" else None,
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    return analyse, recorder


def _ids(analyse: SourceAnalyse) -> set[str]:
    return {need.need["id"] for need in analyse.oneline_needs}


#: a file whose markers the analysis must keep, beside one it skips
GOOD = b"// @Kept, IMPL_GOOD, impl\nvoid good() {}\n"


def _padded(before: bytes, after: bytes, at: int) -> bytes:
    """``before``, a comment line padding it to ``at`` bytes, then ``after``: the
    first byte of ``after`` is the file's byte ``at`` (from 0)."""
    pad = at - len(before) - len(b"//\n")
    assert pad >= 0
    return before + b"//" + b"x" * pad + b"\n" + after


@pytest.mark.parametrize("engine", ENGINES)
def test_a_character_across_byte_2048_does_not_skip_the_file(
    tmp_path: Path, engine: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A UTF-8 file whose 2048th byte starts a two-byte character is text: the file
    was taken for a binary one, and skipped silently, when only its first 2048 bytes
    were decoded, which cut the character in two."""
    data = _padded(
        b"// @Before, IMPL_BEFORE, impl\n",
        "// \u00fc\n// @After, IMPL_AFTER, impl\nvoid f() {}\n".encode(),
        2044,
    )
    assert data[2047:2049] == "\u00fc".encode()  # the lead byte is the 2048th

    analyse, recorder = _cpp_run(tmp_path, {"cut.cpp": data}, engine, monkeypatch)

    assert _ids(analyse) == {"IMPL_BEFORE", "IMPL_AFTER"}
    assert recorder.warnings == []


@pytest.mark.parametrize("engine", ENGINES)
@pytest.mark.parametrize(
    ("position", "line"),
    [
        pytest.param(34, 2, id="in_the_first_2048_bytes"),
        pytest.param(3046, 3, id="past_the_first_2048_bytes"),
    ],
)
def test_a_file_that_is_not_utf8_is_skipped_with_a_warning(
    tmp_path: Path,
    engine: str,
    position: int,
    line: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Latin-1 byte anywhere in a file skips that file, with a ``not_text``
    warning naming it and the first invalid byte's position and line; every other
    file keeps its needs. Past the first 2048 bytes it used to stop the whole
    analysis with a ``UnicodeDecodeError``; within them, skip the file silently."""
    marker = b"// @Lost, IMPL_LATIN1, impl\n"
    if position < 2048:
        data = marker + b"// caf\xe9\n"
    else:
        data = _padded(marker, b"// caf\xe9\n", position - len(b"// caf"))
    assert data.index(b"\xe9") == position

    analyse, recorder = _cpp_run(
        tmp_path, {"good.cpp": GOOD, "latin1.cpp": data}, engine, monkeypatch
    )

    assert _ids(analyse) == {"IMPL_GOOD"}
    path = tmp_path / "latin1.cpp"
    assert recorder.warnings == [
        (
            f"codelinks: skipping {path} \u2014 not UTF-8 (invalid continuation "
            f"byte): byte 0xe9 at position {position}, line {line}; save the file "
            "as UTF-8 to trace it",
            "not_text",
            f"{path}:{line}",
        )
    ]


@pytest.mark.parametrize("engine", ENGINES)
def test_a_utf16_file_is_skipped_with_a_warning(
    tmp_path: Path, engine: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file saved as UTF-16 (here with its byte order mark) is not read: it is
    skipped with the ``not_text`` warning, at its first byte, where it was skipped
    without one."""
    data = "\ufeff// @Wide, IMPL_WIDE, impl\n".encode("utf-16-le")

    analyse, recorder = _cpp_run(
        tmp_path, {"good.cpp": GOOD, "wide.cpp": data}, engine, monkeypatch
    )

    assert _ids(analyse) == {"IMPL_GOOD"}
    ((message, subtype, location),) = recorder.warnings
    assert subtype == "not_text"
    assert "not UTF-8 (invalid start byte): byte 0xff at position 0, line 1" in message
    assert location == f"{tmp_path / 'wide.cpp'}:1"


@pytest.mark.parametrize("engine", ENGINES)
def test_a_nul_byte_in_the_first_2048_bytes_skips_the_file_as_binary(
    tmp_path: Path, engine: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The binary-file heuristic is kept: a NUL byte in a file's first 2048 bytes
    skips it, valid UTF-8 or not, now with the ``not_text`` warning naming the
    byte."""
    data = b"// @Hidden, IMPL_BINARY, impl\n\x00\x01\x02\n"

    analyse, recorder = _cpp_run(
        tmp_path, {"good.cpp": GOOD, "blob.cpp": data}, engine, monkeypatch
    )

    assert _ids(analyse) == {"IMPL_GOOD"}
    path = tmp_path / "blob.cpp"
    assert recorder.warnings == [
        (
            f"codelinks: skipping {path} \u2014 taken for a binary file: a NUL byte "
            "at position 30, line 2, within its first 2048 bytes",
            "not_text",
            f"{path}:2",
        )
    ]


def test_a_nul_byte_past_the_first_2048_bytes_is_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a file's first 2048 bytes are searched for a NUL byte: a later one, in a
    file that is UTF-8, leaves it read, as before."""
    data = _padded(b"// @Read, IMPL_LATE_NUL, impl\n", b"// \x00\n", 3000)

    analyse, recorder = _cpp_run(
        tmp_path, {"late.cpp": data}, "treesitter", monkeypatch
    )

    assert _ids(analyse) == {"IMPL_LATE_NUL"}
    assert recorder.warnings == []


@pytest.mark.parametrize(
    ("data", "position", "line"),
    [
        pytest.param(b"a\nb\nc\xe9\n", 5, 3, id="lf"),
        pytest.param(b"a\r\nb\r\nc\xe9\r\n", 7, 3, id="crlf"),
        pytest.param(b"a\rb\rc\xe9\r", 5, 3, id="cr"),
        pytest.param(b"\xe9", 0, 1, id="first_byte"),
        pytest.param(b"ok \xc3", 3, 1, id="cut_at_the_end"),
    ],
)
def test_the_line_of_the_first_invalid_byte(
    data: bytes, position: int, line: int
) -> None:
    """The warning's line counts LF, CRLF and a lone CR each as one line break, as
    the analysis reads them; a character cut short by the end of the file is invalid
    too."""
    found = decode_source(data)

    assert isinstance(found, NotText)
    assert (found.position, found.line) == (position, line)


@pytest.mark.parametrize(
    ("data", "binary"),
    [
        pytest.param(b"a" * 2047 + b"\x00", True, id="nul_at_index_2047"),
        pytest.param(b"a" * 2048 + b"\x00", False, id="nul_at_index_2048"),
    ],
)
def test_only_the_first_2048_bytes_are_searched_for_a_nul(
    data: bytes, binary: bool
) -> None:
    """A NUL byte makes a file binary only within its first 2048 bytes: the last
    byte searched is index 2047, and one at index 2048 is ordinary text."""
    found = decode_source(data)

    if binary:
        assert isinstance(found, NotText)
        assert found.position == 2047
        assert "binary" in found.reason
    else:
        assert found == data.decode("utf-8")


@pytest.mark.parametrize(
    ("data", "position", "kind"),
    [
        pytest.param(b"\x00\xe9", 0, "binary", id="nul_first"),
        pytest.param(b"\xe9\x00", 0, "not UTF-8", id="invalid_byte_first"),
        pytest.param(b"ok\x00 \xe9", 2, "binary", id="nul_earlier_in_the_file"),
        pytest.param(b"ok\xe9 \x00", 2, "not UTF-8", id="invalid_earlier_in_the_file"),
    ],
)
def test_the_earlier_of_a_nul_and_an_invalid_byte_is_named(
    data: bytes, position: int, kind: str
) -> None:
    """When a NUL byte and a byte that is not UTF-8 both stop a file, the warning
    names the one that comes first."""
    found = decode_source(data)

    assert isinstance(found, NotText)
    assert found.position == position
    assert kind in found.reason
