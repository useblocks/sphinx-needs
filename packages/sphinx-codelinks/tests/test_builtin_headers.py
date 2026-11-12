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
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

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
        pytest.param(["-Xclang", "-nobuiltininc"], id="Xclang"),
    ],
)
def test_a_compile_command_that_chooses_its_builtin_headers_keeps_its_choice(
    builtin_headers, choice: list[str]
):
    """Step 2: a compile command with its own resource directory, or none, is left as
    it is, in every spelling clang accepts."""
    args = ["-std=c11", *choice]
    assert builtin_headers.resource_dir_args(args, None) == (args, False)


@pytest.mark.parametrize(
    "flag",
    [
        pytest.param("-nostdlibinc", id="nostdlibinc"),
        pytest.param("-nostdinc++", id="nostdinc++"),
        pytest.param("--resource=/opt/clang", id="resource-is-another-flag"),
    ],
)
def test_flags_that_keep_the_builtin_headers_choose_nothing(builtin_headers, flag: str):
    """``-nostdlibinc`` and ``-nostdinc++`` drop the C library's or the C++ library's
    headers, not the compiler's, and ``--resource`` is ``-fcompile-resource``: the
    shipped headers are still given."""
    args, _ = builtin_headers.resource_dir_args([flag], None)
    assert args == [flag, "-resource-dir", str(RESOURCE)]


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


def test_missing_shipped_headers_give_none_and_say_so(
    builtin_headers, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Step 4: when the shipped headers are not files (an archive import, a
    repackaging that dropped them), nothing is added and the caller is told."""
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
        ("sys/stdint.h", False),
        ("x86/immintrin.h", False),
        ("config.h", False),
        ("stdio.h", False),
    ],
)
def test_which_headers_are_builtin(builtin_headers, name: str, builtin: bool):
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
        )
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
    assert [s for _, s in warnings] == ["builtin_header"] * 3
