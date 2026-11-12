import json
from pathlib import Path

import pytest

# `sphinx_codelinks.analyse.preproc.__init__` imports the libclang loader eagerly, and
# `loader.py` evaluates `PARSE_OPTIONS = _parse_options()` at module scope -- so importing
# anything from that package needs the optional `libclang` extra. Without this guard the
# module raises ModuleNotFoundError during COLLECTION, taking the whole run with it, while
# the three sibling modules that already carry the guard skip politely. libclang is
# genuinely optional here: it is behind an extra at runtime and behind the
# `codelinks-libclang` dependency group in CI
pytest.importorskip("clang.cindex")

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
    working = f"-working-directory={tmp_path.resolve()}"
    assert flags[a.resolve()] == [working, "-DA=1"]
    assert flags[b.resolve()] == [working, "-DB=2"]


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
    assert flags[a.resolve()] == [f"-working-directory={tmp_path.resolve()}", "-DA=1"]


def test_load_flags_map_starts_every_entry_with_its_working_directory(
    tmp_path: Path,
) -> None:
    """Each entry's arguments start with ``-working-directory=<its directory>``, so a
    relative ``-I`` (or ``-iquote``, ``-isystem``, ``-include``, ``-imacros``) resolves
    against the entry's directory, as the build resolves it, and not against the
    directory the analysis happens to run in. The flag is first, and the entry's own
    arguments follow unchanged."""
    build = tmp_path / "build"
    other = tmp_path / "other"
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(build),
                    "file": "../a.cpp",
                    "arguments": ["clang++", "-I../include", "-c", "../a.cpp"],
                },
                {
                    "directory": str(other),
                    "file": "b.cpp",
                    "command": "clang++ -iquote q -DB=1 -c b.cpp",
                },
            ]
        )
    )

    flags = compile_db.load_flags_map(db)

    assert flags[(tmp_path / "a.cpp").resolve()] == [
        f"-working-directory={build.resolve()}",
        "-I../include",
    ]
    assert flags[(other / "b.cpp").resolve()] == [
        f"-working-directory={other.resolve()}",
        "-iquote",
        "q",
        "-DB=1",
    ]


@pytest.mark.parametrize("directory", [".", "build", "build/../build"])
def test_load_flags_map_relative_directory_is_taken_against_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: str
) -> None:
    """A relative ``directory`` is taken against the database file's own directory,
    never against the process' working directory: the analysis runs elsewhere here,
    and both the entry's file and its working directory still land beside the
    database."""
    project = tmp_path / "project"
    (project / "build").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    db = project / "compile_commands.json"
    db.write_text(
        json.dumps(
            [{"directory": directory, "file": "a.cpp", "arguments": ["cc", "a.cpp"]}]
        )
    )

    flags = compile_db.load_flags_map(db)

    expected_dir = (project / directory).resolve()
    assert flags == {
        expected_dir / "a.cpp": [f"-working-directory={expected_dir}"],
    }


def test_working_directory_reads_the_flag_else_the_process_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The working directory of an argument list is its ``-working-directory=``;
    without one it is the process' working directory, where libclang takes a
    relative path."""
    assert compile_db.working_directory(
        ["-DA", f"-working-directory={tmp_path}", "-I."]
    ) == Path(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert compile_db.working_directory(["-DA"]) == Path.cwd()
    # an entry's own -working-directory follows the one load_flags_map puts first,
    # and libclang takes the last
    assert compile_db.working_directory(
        ["-working-directory=/first", "-DA", "-working-directory=/own"]
    ) == Path("/own")


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


def test_filter_args_drops_an_options_terminator_and_the_inputs_after_it():
    """``--`` ends the options (CMake and some generators write ``-c -- <file>``):
    it and every argument after it are inputs, and are left out. Passed on, the
    arguments libclang adds after the entry's own would be read as inputs too (no
    preprocessing record, so the markers of every arm), and a second input makes a
    second compiler job, which libclang refuses."""
    argv = ["clang++", "-DX=1", "-c", "--", "src/a.cpp", "other.cpp", "-DY=1"]
    assert compile_db.filter_args(argv, "src/a.cpp") == ["-DX=1"]


def test_filter_args_double_dash_as_the_last_argument():
    """A trailing ``--`` ends nothing that follows, and is left out all the same."""
    argv = ["clang++", "-DX=1", "-c", "a.cpp", "--"]
    assert compile_db.filter_args(argv, "a.cpp") == ["-DX=1"]


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        pytest.param(
            ["clang++", "-DX", "--", "a.cpp", "--", "b.cpp"], ["-DX"], id="two-ends"
        ),
        pytest.param(
            ["clang++", "-Xlinker", "--", "-DX", "--", "a.cpp", "-DY"],
            ["-DX"],
            id="a-value-then-an-end",
        ),
        pytest.param(
            ["clang++", "-DX", "--", "-Xlinker", "--", "-DY"],
            ["-DX"],
            id="an-end-then-a-value",
        ),
    ],
)
def test_filter_args_two_double_dashes(argv: list[str], expected: list[str]):
    """The first ``--`` that is not an option's value ends the options; one that is
    an option's value ends nothing, and after the end nothing is an option."""
    assert compile_db.filter_args(argv, "a.cpp") == expected


#: clang 18's options that take the argument after them as their value for another
#: tool or for one architecture (``clang --help-hidden``), plus the joined-target forms.
PASS_THROUGH_OPTIONS = [
    "-Xanalyzer",
    "-Xarch_device",
    "-Xarch_host",
    "-Xarch_x86_64",
    "-Xassembler",
    "-Xclang",
    "-Xcuda-fatbinary",
    "-Xcuda-ptxas",
    "-Xlinker",
    "-Xoffload-linker",
    "-Xoffload-linker-nvptx64",
    "-Xopenmp-target",
    "-Xopenmp-target=nvptx64",
    "-Xpreprocessor",
    "-mllvm",
    "-z",
]


@pytest.mark.parametrize("option", PASS_THROUGH_OPTIONS)
def test_filter_args_double_dash_handed_to_another_tool_ends_nothing(option: str):
    """``-Xlinker --`` hands the ``--`` to the linker: the driver reads the arguments
    after it as options. libclang, though, takes the first ``--`` of its arguments
    for the end of the options whatever precedes it, so the option is left out with
    its ``--`` (none of these tools runs in a parse), and the ``-DFEATURE`` after it
    is kept."""
    argv = ["clang++", "-std=c++17", option, "--", "-DFEATURE", "-c", "a.cpp"]
    assert compile_db.filter_args(argv, "a.cpp") == ["-std=c++17", "-DFEATURE"]


@pytest.mark.parametrize("option", PASS_THROUGH_OPTIONS)
def test_filter_args_keeps_another_tools_argument_verbatim(option: str):
    """Any other value of such an option is kept with it, verbatim: it is not read
    as one of the driver's own options (``-c``, ``-o``) or as the input."""
    argv = ["clang++", option, "-o", option, "a.cpp", "-DX", "-c", "a.cpp"]
    assert compile_db.filter_args(argv, "a.cpp") == [
        option,
        "-o",
        option,
        "a.cpp",
        "-DX",
    ]


def test_filter_args_keeps_a_pass_through_option_missing_its_value():
    """An entry that ends with ``-Xlinker`` is passed on as it is."""
    assert compile_db.filter_args(["clang++", "-DX", "-Xlinker"], "a.cpp") == [
        "-DX",
        "-Xlinker",
    ]


@pytest.mark.parametrize(
    "option", ["-include", "-isystem", "-iquote", "-idirafter", "-isysroot", "-x", "-I"]
)
def test_filter_args_joins_a_double_dash_value_to_its_option(option: str):
    """A ``--`` that is the value of ``-I`` (likewise ``-include``, ``-isystem``, ...)
    ends nothing, and is passed on joined to its option (``-I--``), which the driver
    reads the same, so that libclang does not take it for the end of the options."""
    argv = ["clang++", option, "--", "-DFEATURE", "-c", "a.cpp"]
    assert compile_db.filter_args(argv, "a.cpp") == [f"{option}--", "-DFEATURE"]


@pytest.mark.parametrize("option", ["-o", "-MF", "-MT", "-MQ"])
def test_filter_args_drops_a_double_dash_value_with_its_dropped_option(option: str):
    """``-o --`` names an output: it is left out with its value, as before, and the
    arguments after it are still options."""
    argv = ["clang++", option, "--", "-DFEATURE", "-c", "a.cpp"]
    assert compile_db.filter_args(argv, "a.cpp") == ["-DFEATURE"]


def test_filter_args_openmp_target_joined_and_separate_forms():
    """``-Xopenmp-target=<triple> <arg>`` takes the ``--`` after the triple as its
    value; ``-Xopenmp-target <arg>`` takes the triple, and the ``--`` after it ends
    the options (clang 18: "no such file or directory: '-DFEATURE'")."""
    joined = ["clang++", "-Xopenmp-target=nvptx64", "--", "-DFEATURE", "a.cpp"]
    assert compile_db.filter_args(joined, "a.cpp") == ["-DFEATURE"]
    separate = ["clang++", "-Xopenmp-target", "nvptx64", "--", "-DFEATURE", "a.cpp"]
    assert compile_db.filter_args(separate, "a.cpp") == [
        "-Xopenmp-target",
        "nvptx64",
    ]


def test_load_flags_map_entry_with_options_terminator(tmp_path: Path):
    """The ``command`` form of an entry that ends its options with ``--`` gives its
    file the options before it, and nothing after."""
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(tmp_path),
                    "file": "a.cpp",
                    "command": "clang++ -DX=1 -c -- a.cpp",
                }
            ]
        )
    )
    flags = compile_db.load_flags_map(db)
    assert flags[(tmp_path / "a.cpp").resolve()] == [
        f"{compile_db.WORKING_DIRECTORY_FLAG}{tmp_path.resolve()}",
        "-DX=1",
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

    args = analyse._resolve_preproc_args(src)

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

    args = analyse._resolve_preproc_args(src)

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
