"""clang's builtin headers: the shipped files, and how the libclang engine uses them.

The package ships clang's 30 portable builtin headers under
``analyse/preproc/clang_resource/`` and gives every libclang parse a resource
directory (``analyse/preproc/builtin_headers.py``). The shared extraction cases
``builtin_headers_libclang`` and ``builtin_headers_entry_nostdinc_libclang``
(``tests/data/extraction/preproc_compile_db.yaml``) pin the arms a file takes; the
tests here pin the files, each step of the resolution and the warnings.
"""

import hashlib
import json
import re
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
import sphinx

from sphinx_codelinks.analyse.analyse import BuiltinHeaderWarnings
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig

RESOURCE = (
    Path(__file__).parents[1]
    / "src"
    / "sphinx_codelinks"
    / "analyse"
    / "preproc"
    / "clang_resource"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict:
    return tomllib.loads((RESOURCE / "manifest.toml").read_text(encoding="utf-8"))


def test_the_shipped_headers_are_the_ones_the_manifest_pins():
    """Every header under ``include/`` and the licence are byte for byte the files of
    the LLVM tag the manifest names, and no other header is there: a hand edit, a
    line-ending conversion or a stray file is red here
    (``tools/src/sn_tools/clang_headers.py`` re-fetches them)."""
    manifest = _manifest()
    assert manifest["llvm_tag"] == "llvmorg-18.1.1"
    on_disk = {p.name: _sha256(p) for p in (RESOURCE / "include").iterdir()}
    assert on_disk == manifest["headers"]
    assert len(on_disk) == 30
    assert _sha256(RESOURCE / "LICENSE.TXT") == manifest["license_sha256"]
    assert _sha256(RESOURCE / "names.txt") == manifest["names_sha256"]
    names = (RESOURCE / "names.txt").read_text(encoding="utf-8").split()
    assert names == sorted(set(names))
    assert set(on_disk) <= set(names)


@pytest.fixture
def builtin_headers() -> ModuleType:
    """The engine module; importing anything under ``preproc`` needs libclang."""
    pytest.importorskip("clang.cindex")
    from sphinx_codelinks.analyse.preproc import builtin_headers

    return builtin_headers


def test_the_header_names_are_the_shipped_ones(builtin_headers):
    """The names the engine treats as builtin are exactly the files it ships."""
    assert set(_manifest()["headers"]) == builtin_headers.BUILTIN_HEADERS
    assert builtin_headers.bundled_resource_dir() == RESOURCE


def test_a_parse_is_given_the_shipped_headers(builtin_headers):
    """Step 3: arguments that choose nothing get the shipped resource directory."""
    args, unavailable = builtin_headers.resource_dir_args(["-std=c11"], None)
    assert args == ["-std=c11", "-resource-dir", str(RESOURCE)]
    assert not unavailable


@pytest.mark.parametrize(
    "choice",
    [
        pytest.param(["-resource-dir", "/opt/clang"], id="resource-dir"),
        pytest.param(["-resource-dir=/opt/clang"], id="resource-dir="),
        pytest.param(["-nostdinc"], id="nostdinc"),
        pytest.param(["--no-standard-includes"], id="no-standard-includes"),
        pytest.param(["-nobuiltininc"], id="nobuiltininc"),
    ],
)
def test_a_compile_command_that_chooses_its_builtin_headers_keeps_its_choice(
    builtin_headers, choice: list[str]
):
    """Step 2: a compile command with its own resource directory, or none, is left as
    it is, in every spelling the driver accepts."""
    args = ["-std=c11", *choice]
    assert builtin_headers.resource_dir_args(args, None) == (args, False)


@pytest.mark.parametrize(
    "flags",
    [
        pytest.param(["-nostdlibinc"], id="nostdlibinc"),
        pytest.param(["-nostdinc++"], id="nostdinc++"),
        pytest.param(["--resource=/opt/clang"], id="resource-is-another-flag"),
        pytest.param(["-Xclang", "-nobuiltininc"], id="Xclang-nobuiltininc"),
        pytest.param(["-Xclang", "-resource-dir"], id="Xclang-resource-dir"),
        pytest.param(["-Xpreprocessor", "-nostdinc"], id="Xpreprocessor-nostdinc"),
        pytest.param(["-Xarch_device", "-nobuiltininc"], id="Xarch_device"),
        pytest.param(
            ["--target=x86_64-linux-gnu", "-Xarch_x86_64", "-nostdinc"],
            id="Xarch-not-macho",
        ),
    ],
)
def test_flags_that_keep_the_builtin_headers_choose_nothing(
    builtin_headers, flags: list[str]
):
    """``-nostdlibinc`` and ``-nostdinc++`` drop the C library's or the C++ library's
    headers, not the compiler's; ``--resource`` is ``-fcompile-resource``; and a flag
    passed through to another tool (``-Xclang -nobuiltininc``) is not read by the
    driver, which still adds the builtin headers' directory: the shipped headers are
    still given."""
    args, _ = builtin_headers.resource_dir_args(flags, None)
    assert args == [*flags, "-resource-dir", str(RESOURCE)]


#: compile commands and whether the driver takes its builtin headers from them, as
#: clang 18 reads them (each one checked against libclang below)
DRIVER_CASES = [
    pytest.param(["-nobuiltininc"], True, id="nobuiltininc"),
    pytest.param(["-Xclang", "-nobuiltininc"], False, id="Xclang"),
    pytest.param(["-Xanalyzer", "-nostdinc"], False, id="Xanalyzer"),
    pytest.param(["-Xopenmp-target=nvptx64", "-nostdinc"], False, id="Xopenmp-target="),
    pytest.param(["-Xopenmp-target", "-nostdinc"], False, id="Xopenmp-target"),
    pytest.param(["-Xoffload-linker", "-nostdinc"], False, id="Xoffload-linker"),
    pytest.param(["-Xcuda-ptxas", "-nostdinc"], False, id="Xcuda-ptxas"),
    pytest.param(["-Xassembler", "-nostdinc"], False, id="Xassembler"),
    pytest.param(["-Xlinker", "-nostdinc"], False, id="Xlinker"),
    pytest.param(["-z", "-nostdinc"], False, id="z"),
    # no clang driver option: the driver reads the argument after it
    pytest.param(["-Xflang", "-nostdinc"], True, id="Xflang-unknown"),
    pytest.param(["-Xarch_host", "-nobuiltininc"], True, id="Xarch_host"),
    pytest.param(["-Xarch_device", "-nobuiltininc"], False, id="Xarch_device"),
    pytest.param(["-Xarch_x86_64", "-nobuiltininc"], False, id="Xarch-linux"),
    pytest.param(
        ["--target=arm64-apple-macos", "-Xarch_arm64", "-nostdinc"],
        True,
        id="Xarch-macho-own-arch",
    ),
    pytest.param(
        ["-target", "arm64-apple-macos", "-Xarch_arm64", "-nostdinc"],
        True,
        id="Xarch-macho-own-arch-separate-target",
    ),
    pytest.param(
        ["--target=arm64-apple-macos", "-Xarch_x86_64", "-nostdinc"],
        False,
        id="Xarch-macho-other-arch",
    ),
    pytest.param(
        ["--target=aarch64-apple-darwin", "-Xarch_arm64", "-nostdinc"],
        True,
        id="Xarch-macho-name",
    ),
    pytest.param(
        ["--target=aarch64-apple-darwin", "-Xarch_aarch64", "-nostdinc"],
        False,
        id="Xarch-macho-not-the-macho-name",
    ),
    pytest.param(
        [
            "--target=x86_64-apple-macos",
            "-arch",
            "x86_64",
            "-Xarch_x86_64",
            "-nostdinc",
        ],
        True,
        id="Xarch-macho-arch",
    ),
    pytest.param(
        ["--target=arm64-apple-macos", "-arch", "x86_64", "-Xarch_x86_64", "-nostdinc"],
        True,
        id="Xarch-macho-arch-replaces-target",
    ),
    pytest.param(
        ["--target=arm64-apple-macos", "-arch", "x86_64", "-Xarch_arm64", "-nostdinc"],
        False,
        id="Xarch-macho-target-replaced",
    ),
    pytest.param(
        ["--target=arm64-apple-macos", "-Xarch_arm64", "-resource-dir=/nonexistent"],
        False,
        id="Xarch-refuses-resource-dir",
    ),
]


@pytest.mark.parametrize(("flags", "chooses"), DRIVER_CASES)
def test_the_driver_options_are_read_as_the_driver_reads_them(
    builtin_headers, tmp_path: Path, flags: list[str], chooses: bool
):
    """Whether a compile command chooses its builtin headers is what libclang's
    driver makes of it: given the shipped headers as well, it finds them exactly when
    the command does not choose. The target is explicit (Linux unless the case names
    an Apple one), so the case holds on every host."""
    import clang.cindex as cx

    args = ["-std=c11", "-nostdlibinc", "--target=x86_64-linux-gnu", *flags]
    assert builtin_headers.chooses_builtin_headers(args) is chooses
    source = tmp_path / "a.c"
    source.write_text("#include <stdint.h>\n")
    tu = cx.Index.create().parse(
        str(source), args=[*args, "-resource-dir", str(RESOURCE)]
    )
    found = not any("file not found" in d.spelling for d in tu.diagnostics)
    assert found is not chooses


def test_a_flag_after_a_pass_through_value_is_read_again(builtin_headers):
    """Only the one argument after ``-Xclang`` is passed through."""
    assert builtin_headers.chooses_builtin_headers(["-Xclang", "-v", "-nostdinc"])


@pytest.mark.parametrize(
    "args",
    [
        pytest.param([], id="no-choice"),
        pytest.param(["-nostdinc"], id="nostdinc"),
        pytest.param(["-resource-dir", "/entry"], id="entry-resource-dir"),
    ],
)
def test_the_setting_comes_first(builtin_headers, args: list[str]):
    """Step 1: ``resource_dir`` is passed whatever the compile command says, last, so
    it wins over the entry's own ``-resource-dir`` (clang takes the last one)."""
    configured = Path("/opt/clang/lib/clang/18")
    assert builtin_headers.resource_dir_args(args, configured) == (
        [*args, "-resource-dir", str(configured)],
        False,
    )


@pytest.mark.parametrize("kept", [0, 29], ids=["none", "one-missing"])
def test_missing_shipped_headers_give_none_and_say_so(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kept: int
):
    """Step 4: when the shipped headers are not all files (an archive import, a
    repackaging that dropped some of them), nothing is added and the caller is told:
    a directory missing one header is no resource directory."""
    (tmp_path / "include").mkdir()
    for name in sorted(builtin_headers.BUILTIN_HEADERS)[:kept]:
        (tmp_path / "include" / name).write_bytes(b"")
    monkeypatch.setattr(builtin_headers, "BUNDLED_RESOURCE_DIR", tmp_path)
    assert builtin_headers.resource_dir_args(["-std=c11"], None) == (
        ["-std=c11"],
        True,
    )


@pytest.mark.parametrize(
    ("name", "builtin"),
    [
        ("stddef.h", True),
        ("stdatomic.h", True),
        ("immintrin.h", True),
        ("arm_neon.h", True),
        ("cpuid.h", True),
        ("mm_malloc.h", True),
        ("unwind.h", True),
        ("cuda_wrappers/new", True),
        ("sanitizer/asan_interface.h", True),
        ("xray/xray_interface.h", True),
        ("fuzzer/FuzzedDataProvider.h", True),
        ("hlsl.h", False),
        ("hlsl/hlsl_intrinsics.h", False),
        ("ISO_Fortran_binding.h", False),
        ("new", False),
        ("omp.h", False),
        ("sys/stdint.h", False),
        ("x86/immintrin.h", False),
        ("config.h", False),
        ("stdio.h", False),
    ],
)
def test_which_headers_are_builtin(builtin_headers, name: str, builtin: bool):
    """A builtin header is a name a default full install of clang puts in its
    resource ``include`` directory, as an ``#include`` writes it: not only the 30
    shipped ones nor only the intrinsics (``cpuid.h``, ``unwind.h``, compiler-rt's
    ``sanitizer/`` headers), and not ``omp.h`` (an OpenMP runtime's), flang's
    ``ISO_Fortran_binding.h`` or the HLSL headers a default build does not install."""
    assert builtin_headers.is_builtin_header(name) is builtin


class _Recorder:
    """Stands in for the analysis' logger and keeps every warning."""

    def __init__(self) -> None:
        self.warnings: list[tuple[str, str]] = []

    def warning(self, msg: str, *, subtype: str = "", **_k: object) -> None:
        self.warnings.append((msg, subtype))

    def info(self, *_a: object, **_k: object) -> None:
        pass

    def debug(self, *_a: object, **_k: object) -> None:
        pass


def _analyse(
    root: Path,
    sources: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    *,
    preprocessor: PreprocessorConfig,
    analysed: list[str] | None = None,
    shared: BuiltinHeaderWarnings | None = None,
) -> tuple[set[str], list[tuple[str, str]]]:
    """Run the libclang engine over ``sources``: the one-line need ids and warnings."""
    from sphinx_codelinks.analyse import analyse as analyse_module

    for name, text in sources.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
    recorder = _Recorder()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    analyse = analyse_module.SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[root / name for name in (analysed or list(sources))],
            src_dir=root,
            get_oneline_needs=True,
            get_need_id_refs=False,
            preprocessor=preprocessor,
        ),
        builtin_header_warnings=shared,
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return {n.need["id"] for n in analyse.oneline_needs}, recorder.warnings


WIDTH_ARMS = (
    "#include <stdint.h>\n"
    "#if UINT32_MAX > 0xFFFFu\n"
    "// @wide, IMPL_WIDE, impl\n"
    "#else\n"
    "// @narrow, IMPL_NARROW, impl\n"
    "#endif\n"
)


def _db(root: Path, entries: list[tuple[str, list[str]]]) -> Path:
    db = root / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {"directory": str(root), "file": file, "arguments": ["clang", *args]}
                for file, args in entries
            ]
        )
    )
    return db


def test_the_resource_dir_setting_is_what_the_parse_searches(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """``resource_dir`` is the directory the parse takes its builtin headers from: a
    header only it holds is found, so the arm its macro selects is active."""
    resource = tmp_path / "clang"
    (resource / "include").mkdir(parents=True)
    (resource / "include" / "vendor_builtin.h").write_text("#define FROM_RESOURCE 1\n")
    source = (
        "#include <vendor_builtin.h>\n"
        "#ifdef FROM_RESOURCE\n"
        "// @set, IMPL_SET, impl\n"
        "#else\n"
        "// @unset, IMPL_UNSET, impl\n"
        "#endif\n"
    )

    ids, _ = _analyse(
        tmp_path / "src",
        {"a.c": source},
        monkeypatch,
        preprocessor=PreprocessorConfig(std="c11", resource_dir=resource),
    )

    assert ids == {"IMPL_SET"}


def test_a_source_read_through_its_includer_gets_the_builtin_headers(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A source with no entry, read through the entry that includes it, is parsed
    with the builtin headers too: its ``UINT32_MAX`` arm is the compiler's.
    ``-nostdlibinc`` leaves the builtin headers the only system headers, on every
    host."""
    db = _db(tmp_path, [("unity.c", ["-std=c11", "-nostdlibinc"])])
    ids, warnings = _analyse(
        tmp_path,
        {"unity.c": '#include "s.c"\n', "s.c": WIDTH_ARMS},
        monkeypatch,
        preprocessor=PreprocessorConfig(compile_commands=db),
        analysed=["s.c"],
    )

    assert ids == {"IMPL_WIDE"}
    assert warnings == []


def test_a_missing_builtin_header_is_warned_about_once_per_file(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An intrinsics header is not shipped: a file that includes one is warned about
    once, naming the header and the setting; a file whose missing include is not a
    builtin header, and a file that finds everything, are not."""
    db = _db(
        tmp_path,
        [
            ("intrin.c", ["-std=c11"]),
            ("generated.c", ["-std=c11"]),
            ("fine.c", ["-std=c11", "-nostdlibinc"]),
        ],
    )
    _ids, warnings = _analyse(
        tmp_path,
        {
            "intrin.c": "#include <immintrin.h>\n#include <arm_neon.h>\n",
            "generated.c": '#include "generated/config.h"\n',
            "fine.c": WIDTH_ARMS,
        },
        monkeypatch,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )

    assert len(warnings) == 1, warnings
    message, subtype = warnings[0]
    assert subtype == "builtin_header"
    assert str(tmp_path / "intrin.c") in message
    assert "'immintrin.h'" in message
    assert "resource_dir" in message


def test_an_entry_without_builtin_headers_is_warned_about(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An entry that turns the builtin headers off (``-nostdinc``) keeps its choice,
    and the header it then misses is named."""
    db = _db(tmp_path, [("a.c", ["-std=c11", "-nostdinc"])])
    ids, warnings = _analyse(
        tmp_path,
        {"a.c": WIDTH_ARMS},
        monkeypatch,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )

    assert ids == {"IMPL_NARROW"}
    assert [subtype for _, subtype in warnings] == ["builtin_header"]
    assert "'stdint.h'" in warnings[0][0]


def test_missing_shipped_headers_are_warned_about_once_per_run(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Without the shipped headers on disk, the analysis still parses every file,
    without them, and says so once, not once per file; each file that then misses a
    builtin header is named too."""
    monkeypatch.setattr(builtin_headers, "BUNDLED_RESOURCE_DIR", tmp_path / "gone")
    db = _db(
        tmp_path,
        [("a.c", ["-std=c11", "-nostdlibinc"]), ("b.c", ["-std=c11", "-nostdlibinc"])],
    )
    ids, warnings = _analyse(
        tmp_path,
        {"a.c": WIDTH_ARMS, "b.c": WIDTH_ARMS.replace("IMPL_", "IMPL_B_")},
        monkeypatch,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )

    assert ids == {"IMPL_NARROW", "IMPL_B_NARROW"}
    unavailable = [m for m, _ in warnings if "are not under" in m]
    assert len(unavailable) == 1
    assert str(tmp_path / "gone" / "include") in unavailable[0]
    assert "resource_dir" in unavailable[0]
    assert [s for _, s in warnings] == ["builtin_header"] * 3


INTRIN_UNITY = '#include <immintrin.h>\n#include "s.c"\n'


def test_an_includer_parse_that_misses_a_builtin_header_is_warned_about(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A source read through its includer is parsed as the includer's unit: the
    builtin header that unit misses is warned about, naming the includer."""
    db = _db(tmp_path, [("unity.c", ["-std=c11"])])
    ids, warnings = _analyse(
        tmp_path,
        {"unity.c": INTRIN_UNITY, "s.c": "// @s, IMPL_S, impl\n"},
        monkeypatch,
        preprocessor=PreprocessorConfig(compile_commands=db),
        analysed=["s.c"],
    )

    assert ids == {"IMPL_S"}
    assert len(warnings) == 1, warnings
    assert str(tmp_path / "unity.c") in warnings[0][0]
    assert "'immintrin.h'" in warnings[0][0]


def test_a_file_parsed_twice_is_warned_about_once(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A traced source that is also the includer of another is parsed twice, as its
    own unit and as the includer: the header it misses is warned about once."""
    db = _db(tmp_path, [("unity.c", ["-std=c11"])])
    ids, warnings = _analyse(
        tmp_path,
        {"unity.c": INTRIN_UNITY, "s.c": "// @s, IMPL_S, impl\n"},
        monkeypatch,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )

    assert ids == {"IMPL_S"}
    assert len(warnings) == 1, warnings
    assert str(tmp_path / "unity.c") in warnings[0][0]


def test_analyses_that_share_their_warnings_warn_once_across_them(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Two analyses given one :class:`BuiltinHeaderWarnings` (a build's directives,
    the CLI's projects) warn about the unavailable headers once, and about a file
    they both parse once."""
    monkeypatch.setattr(builtin_headers, "BUNDLED_RESOURCE_DIR", tmp_path / "gone")
    db = _db(tmp_path, [("a.c", ["-std=c11", "-nostdlibinc"])])
    shared = BuiltinHeaderWarnings()
    runs = [
        _analyse(
            tmp_path,
            {"a.c": WIDTH_ARMS},
            monkeypatch,
            preprocessor=PreprocessorConfig(compile_commands=db),
            shared=shared,
        )
        for _ in range(2)
    ]

    assert [len(warnings) for _, warnings in runs] == [2, 0]
    assert shared.unavailable
    assert shared.files == {tmp_path / "a.c"}


def test_the_cli_projects_share_their_warnings(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """``codelinks analyse`` runs one analysis per project: two projects over the
    same file warn once that the shipped headers are missing, and once about it."""
    from sphinx_codelinks.analyse import analyse as analyse_module
    from sphinx_codelinks.analyse.projects import AnalyseProjects
    from sphinx_codelinks.config import CodeLinksConfig

    monkeypatch.setattr(builtin_headers, "BUNDLED_RESOURCE_DIR", tmp_path / "gone")
    recorder = _Recorder()
    monkeypatch.setattr(analyse_module, "logger", recorder)
    source = tmp_path / "a.c"
    source.write_text("#include <stdint.h>\n// @a, IMPL_A, impl\n")
    db = _db(tmp_path, [("a.c", ["-std=c11", "-nostdlibinc"])])

    def project() -> dict:
        return {
            "analyse_config": SourceAnalyseConfig(
                src_files=[source],
                src_dir=tmp_path,
                get_oneline_needs=True,
                preprocessor=PreprocessorConfig(compile_commands=db),
            )
        }

    config = CodeLinksConfig()
    config.projects = {"one": project(), "two": project()}  # ty: ignore[invalid-assignment]
    projects = AnalyseProjects(config)
    projects.run()

    assert [len(a.oneline_needs) for a in projects.projects_analyse.values()] == [1, 1]
    messages = [message for message, _ in recorder.warnings]
    assert len(messages) == 2, messages
    assert sum("are not under" in m for m in messages) == 1
    assert sum("'stdint.h'" in m for m in messages) == 1


# --- in a build: once per build, the type rendered once ---------------------------

#: the fixture's project on the libclang engine, a source that misses an intrinsics
#: header, and a second ``src-trace`` of the project, so two directives analyse it
BUILD_FILES = {"src/intrin.cpp": "#include <immintrin.h>\nvoid intrin() {}\n"}
BUILD_TOML = "\n[codelinks.projects.src.analyse.preprocessor]\ndefines = []\n"
SECOND_DIRECTIVE = {"docs/page1.rst": "\n.. src-trace::\n   :project: src\n"}


def _builtin_warnings(app) -> list[str]:
    from sphinx_needs_testkit import build_warnings

    return [w for w in build_warnings(app) if "builtin header" in w]


def test_a_build_warns_about_a_missing_builtin_header_once(
    builtin_headers, tmp_path: Path, make_app
):
    """Two ``src-trace`` directives analyse the same source: the builtin header it
    misses is warned about once in the build, not once per directive."""
    from .test_need_id_refs import _build, _project

    _project(
        tmp_path, toml_extra=BUILD_TOML, files=BUILD_FILES, append=SECOND_DIRECTIVE
    )
    warnings = _builtin_warnings(_build(tmp_path, make_app))

    assert len(warnings) == 1, warnings
    assert "intrin.cpp" in warnings[0]
    assert "'immintrin.h'" in warnings[0]


def test_a_build_warns_once_that_the_shipped_headers_are_missing(
    builtin_headers, tmp_path: Path, make_app, monkeypatch: pytest.MonkeyPatch
):
    """Without the shipped headers, a build with two ``src-trace`` directives says so
    once; and the next build says so again."""
    from .test_need_id_refs import _build, _project

    monkeypatch.setattr(builtin_headers, "BUNDLED_RESOURCE_DIR", tmp_path / "gone")
    _project(tmp_path, toml_extra=BUILD_TOML, append=SECOND_DIRECTIVE)
    for _ in range(2):
        warnings = [
            w
            for w in _builtin_warnings(_build(tmp_path, make_app))
            if "are not under" in w
        ]
        assert len(warnings) == 1, warnings


def test_the_next_build_of_the_same_environment_warns_again(
    builtin_headers, tmp_path: Path, make_app, monkeypatch: pytest.MonkeyPatch
):
    """The record is per build, not per environment: a second build of the same
    application, which keeps its environment, warns again once."""
    from .test_need_id_refs import _build, _project

    monkeypatch.setattr(builtin_headers, "BUNDLED_RESOURCE_DIR", tmp_path / "gone")
    _project(tmp_path, toml_extra=BUILD_TOML)
    app = _build(tmp_path, make_app)
    index = tmp_path / "docs" / "index.rst"
    index.write_text(index.read_text(encoding="utf-8") + "\nMore.\n", encoding="utf-8")
    app.build()

    warnings = [w for w in _builtin_warnings(app) if "are not under" in w]
    assert len(warnings) == 2, warnings


def test_the_config_only_scan_shares_the_build_record(
    builtin_headers, tmp_path: Path, make_app, monkeypatch: pytest.MonkeyPatch
):
    """A project no directive traces is scanned after the reads, by the same build:
    the headers missing are warned about once across the directive and the scan."""
    from .test_need_id_refs import _build, _json, _project

    monkeypatch.setattr(builtin_headers, "BUNDLED_RESOURCE_DIR", tmp_path / "gone")
    other = (
        "\n[codelinks.projects.other]\n"
        'remote_url_pattern = "https://github.com/example/demo/blob/{commit}/{path}"\n'
        "\n[codelinks.projects.other.source_discover]\n"
        'src_dir = "../other"\ncomment_type = "cpp"\n'
        "\n[codelinks.projects.other.analyse.preprocessor]\ndefines = []\n"
    )
    _project(
        tmp_path,
        toml_extra=BUILD_TOML + other,
        files={"other/o.cpp": "// @need-ids: REQ_002\nvoid o() {}\n"},
    )
    app = _build(tmp_path, make_app)

    assert any(
        "other/o.cpp" in url for url in _json(app)["needs"]["REQ_002"]["code_url"]
    )
    warnings = [w for w in _builtin_warnings(app) if "are not under" in w]
    assert len(warnings) == 1, warnings


_SHOWS_WARNING_TYPES = sphinx.version_info >= (8,)


@pytest.mark.parametrize(
    ("show", "expected"),
    [
        # Sphinx renders the suffix itself, so the package logger adds none
        pytest.param(True, ["[codelinks.builtin_header]"], id="on"),
        # before Sphinx 8 the package logger appends it; from 8 nothing renders it
        pytest.param(
            False,
            [] if _SHOWS_WARNING_TYPES else ["[codelinks.builtin_header]"],
            id="off",
        ),
    ],
)
def test_the_builtin_header_type_is_rendered_at_most_once(
    builtin_headers, tmp_path: Path, make_app, show: bool, expected: list[str]
):
    """The warning's ``[codelinks.builtin_header]`` suffix appears once (or, on Sphinx
    8 and later with ``show_warning_types`` off, not at all), never twice."""
    from .test_need_id_refs import _build, _project

    _project(
        tmp_path,
        toml_extra=BUILD_TOML,
        files=BUILD_FILES,
        append={"docs/conf.py": f"\nshow_warning_types = {show}\n"},
    )
    warnings = _builtin_warnings(_build(tmp_path, make_app))

    assert len(warnings) == 1, warnings
    assert re.findall(r"\[codelinks\.[a-z_]+\]", warnings[0]) == expected
