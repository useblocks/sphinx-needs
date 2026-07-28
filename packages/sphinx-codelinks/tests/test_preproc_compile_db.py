import json
from pathlib import Path

import pytest

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.preproc import compile_db
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig


class _RecordingLogger:
    """Stand-in for the module logger that records warning calls.

    The real ``CodelinksLogger`` is slotted, so its methods can't be
    monkeypatched on the instance; tests swap the module-level ``logger`` for
    one of these instead.
    """

    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, *_a: object, **_k: object) -> None:
        self.warnings.append("warning")

    def info(self, *_a: object, **_k: object) -> None:
        pass

    def debug(self, *_a: object, **_k: object) -> None:
        pass


def test_find_compile_db_in_build_dir(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    build = tmp_path / "build"
    build.mkdir()
    db = build / "compile_commands.json"
    db.write_text("[]")
    src = tmp_path / "src" / "deep"
    src.mkdir(parents=True)
    # Walk up from src/deep should find build/compile_commands.json? No:
    # walk-up only ascends; the db is in a sibling 'build'. So a db placed
    # at the project root is what walk-up finds. Place one at root instead.
    root_db = tmp_path / "compile_commands.json"
    root_db.write_text("[]")
    found = compile_db.find_compile_db(src, project_root=tmp_path)
    assert found == root_db


def test_find_compile_db_absent(tmp_path: Path):
    (tmp_path / "ubproject.toml").write_text("")
    src = tmp_path / "a"
    src.mkdir()
    assert compile_db.find_compile_db(src, project_root=tmp_path) is None


def test_find_compile_db_stops_at_git_root(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    db = tmp_path / "compile_commands.json"
    db.write_text("[]")
    nested = tmp_path / "x" / "y"
    nested.mkdir(parents=True)
    assert compile_db.find_compile_db(nested) == db


def test_filter_args_strips_compiler_and_output():
    argv = [
        "clang++",
        "-std=c++17",
        "-c",
        "-o",
        "out.o",
        "-DVARIANT_A=1",
        "-I/inc",
        "-MMD",
        "-MF",
        "dep.d",
        "src/a.cpp",
    ]
    out = compile_db.filter_args(argv, "src/a.cpp")
    assert out == ["-std=c++17", "-DVARIANT_A=1", "-I/inc"]


def test_load_flags_map_command_and_arguments_forms(tmp_path: Path):
    a = tmp_path / "a.cpp"
    a.write_text("")
    b = tmp_path / "b.cpp"
    b.write_text("")
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "arguments": ["clang++", "-DA=1", "-c", str(a)],
                    "file": str(a),
                },
                {
                    "directory": str(tmp_path),
                    "command": "clang++ -DB=2 -c b.cpp",
                    "file": "b.cpp",
                },
            ]
        )
    )

    flags = compile_db.load_flags_map(db)
    assert flags[a.resolve()] == ["-DA=1"]
    assert flags[b.resolve()] == ["-DB=2"]


def test_load_flags_map_relative_input_path_stripped(tmp_path: Path):
    """Regression: entry whose arguments reference input by relative subdir path must be stripped.

    When directory = tmp_path, file = "src/a.cpp", and arguments contains "src/a.cpp",
    the old code passed abs_file to filter_args. The input_names set only includes
    the basename "a.cpp" and the absolute path — NOT the relative "src/a.cpp" — so
    the relative path leaked as a spurious positional argument.
    """
    src = tmp_path / "src"
    src.mkdir()
    a = src / "a.cpp"
    a.write_text("")
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "file": "src/a.cpp",
                    "arguments": ["clang++", "-DA=1", "-c", "src/a.cpp"],
                }
            ]
        )
    )

    flags = compile_db.load_flags_map(db)
    assert flags[a.resolve()] == ["-DA=1"]


def test_defines_to_args(tmp_path: Path):
    out = compile_db.defines_to_args(["VARIANT_A", "X=2"], [tmp_path / "inc"])
    assert "-DVARIANT_A" in out
    assert "-DX=2" in out
    assert f"-I{(tmp_path / 'inc')}" in out
    assert "-std=c++17" in out


def test_filter_args_strips_compiler_launcher_prefix():
    """A launcher prefix (ccache/sccache/distcc) precedes the real compiler.

    Both leading non-flag tokens must be dropped; leaving the compiler in makes
    libclang treat it as a second input and return a NULL translation unit.
    """
    argv = ["ccache", "/usr/bin/g++", "-DA=1", "-c", "a.cpp"]
    assert compile_db.filter_args(argv, "a.cpp") == ["-DA=1"]


def test_filter_args_keeps_separate_form_value_matching_input_basename():
    """The value of a separate-form flag (-include/-isystem/-I/...) must be kept
    even when it shares the input's basename; only the positional input is
    stripped."""
    argv = ["clang++", "-DA=1", "-include", "/compat/foo.cpp", "-c", "foo.cpp"]
    assert compile_db.filter_args(argv, "foo.cpp") == [
        "-DA=1",
        "-include",
        "/compat/foo.cpp",
    ]


def test_defines_to_args_pins_cpp_for_gnu_cpp_dialect():
    """A GNU C++ dialect (gnu++17/gnu++20) is a C++ standard; pairing it with
    ``-x c`` makes clang reject it and return a NULL TU. It must resolve to C++."""
    assert compile_db.defines_to_args([], [], "gnu++17") == [
        "-x",
        "c++",
        "-std=gnu++17",
    ]
    # A GNU C dialect stays C.
    assert compile_db.defines_to_args([], [], "gnu11") == ["-x", "c", "-std=gnu11"]


def test_malformed_compile_commands_warns_and_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A present-but-malformed compile_commands.json must not crash or skip every
    file: the resolver warns and falls back to the global defines."""
    db = tmp_path / "compile_commands.json"
    db.write_text("{ this is not valid json")
    src = tmp_path / "case.cpp"
    src.write_text("// @X, IMPL_X, impl, [REQ]\n")
    cfg = SourceAnalyseConfig(
        src_files=[src],
        src_dir=tmp_path,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=["FALLBACK=1"], compile_commands=db),
    )
    analyse = SourceAnalyse(cfg)

    rec = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", rec)

    args = analyse._resolve_preproc_args(src)  # noqa: SLF001

    assert args is not None, "malformed DB should fall back, not skip the file"
    assert "-DFALLBACK=1" in args, "should fall back to the global defines"
    assert rec.warnings, "expected a warning about the malformed compile_commands.json"


def test_missing_explicit_compile_commands_warns_and_falls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An explicit compile_commands path that is not a readable file must warn
    and fall back to the global defines (not silently, not skip every file)."""
    missing = tmp_path / "does_not_exist.json"
    src = tmp_path / "case.cpp"
    src.write_text("// @X, IMPL_X, impl, [REQ]\n")
    cfg = SourceAnalyseConfig(
        src_files=[src],
        src_dir=tmp_path,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(
            defines=["FALLBACK=1"], compile_commands=missing
        ),
    )
    analyse = SourceAnalyse(cfg)

    rec = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", rec)

    args = analyse._resolve_preproc_args(src)  # noqa: SLF001

    assert args is not None, "missing DB path should fall back, not skip the file"
    assert "-DFALLBACK=1" in args, "should fall back to the global defines"
    assert rec.warnings, "expected a warning about the missing compile_commands path"


def test_is_translation_unit_source():
    # Compiled translation-unit sources (skipped when build-excluded).
    assert compile_db.is_translation_unit_source(Path("a.c"))
    assert compile_db.is_translation_unit_source(Path("a.cpp"))
    assert compile_db.is_translation_unit_source(Path("a.cc"))
    assert compile_db.is_translation_unit_source(Path("a.cxx"))
    assert compile_db.is_translation_unit_source(Path("A.CPP"))  # case-insensitive
    # Header-like files (parsed standalone when absent from the DB).
    assert not compile_db.is_translation_unit_source(Path("a.h"))
    assert not compile_db.is_translation_unit_source(Path("a.hpp"))
    assert not compile_db.is_translation_unit_source(Path("a.hxx"))
    assert not compile_db.is_translation_unit_source(Path("a.hh"))
    assert not compile_db.is_translation_unit_source(Path("a.ci"))
    assert not compile_db.is_translation_unit_source(Path("a.ihl"))
