import json
from pathlib import Path

import pytest

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.preproc import libclang_parser
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig

FIXTURE = Path(__file__).parent / "data" / "preproc" / "variants_branching.cpp"
HEADER = Path(__file__).parent / "data" / "preproc" / "header_standalone.hpp"


def _run_get_oneline_ids(defines):
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE],
        src_dir=FIXTURE.parent,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_rst=False,
        preprocessor=PreprocessorConfig(defines=defines),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return {n.need["id"] for n in analyse.oneline_needs}


def test_libclang_engine_excludes_inactive_markers():
    ids = _run_get_oneline_ids(
        ["VARIANT_A=1", "PLATFORM_LINUX=1", "PROTOCOL_VERSION=3"]
    )
    assert "IMPL_ALWAYS" in ids
    assert "IMPL_VAR_A" in ids
    assert "IMPL_VAR_B" not in ids  # inactive
    assert "IMPL_PROTO_3" in ids
    assert "IMPL_LINUX_A" in ids


def test_libclang_engine_other_variant():
    ids = _run_get_oneline_ids(["PROTOCOL_VERSION=1"])
    assert "IMPL_ALWAYS" in ids
    assert "IMPL_VAR_B" in ids
    assert "IMPL_VAR_A" not in ids
    assert "IMPL_PROTO_3" not in ids


def test_libclang_engine_via_compile_commands(tmp_path):
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(FIXTURE.parent),
                    "arguments": [
                        "clang++",
                        "-std=c++17",
                        "-DVARIANT_A=1",
                        "-DPROTOCOL_VERSION=3",
                        "-c",
                        str(FIXTURE),
                    ],
                    "file": str(FIXTURE),
                }
            ]
        )
    )
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE],
        src_dir=FIXTURE.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert "IMPL_VAR_A" in ids
    assert "IMPL_VAR_B" not in ids
    assert "IMPL_PROTO_3" in ids
    assert "IMPL_LINUX_A" not in ids


def test_libclang_resilient_to_broken_code():
    broken = FIXTURE.parent / "variants_broken.cpp"
    cfg = SourceAnalyseConfig(
        src_files=[broken],
        src_dir=broken.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=[]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert ids == {"IMPL_DESPITE", "IMPL_AFTER_BROKEN"}


def test_libclang_resilient_to_half_typed_code():
    half = FIXTURE.parent / "half_typed.cpp"
    cfg = SourceAnalyseConfig(
        src_files=[half],
        src_dir=half.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=[]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    # All 4 markers survive at the token level even though 2 decls don't parse.
    assert {"IMPL_COMPLETE", "IMPL_HALF", "IMPL_AFTER", "IMPL_MID"} <= ids


def test_null_tu_warns_and_skips_but_batch_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A file whose translation unit cannot be loaded at all is skipped with a
    WARNING (not silently), and the rest of the batch still extracts.

    Real sources are recoverable under ``incomplete`` parsing, so the NULL-TU
    guard is exercised by forcing ``extract_active_comments`` to raise the
    ``TranslationUnitLoadError`` libclang would raise for an unloadable TU."""
    import clang.cindex

    good = tmp_path / "good.cpp"
    good.write_text("// @Good, IMPL_GOOD, impl, [REQ]\n")
    bad = tmp_path / "bad.cpp"
    bad.write_text("// @Bad, IMPL_BAD, impl, [REQ]\n")
    cfg = SourceAnalyseConfig(
        src_files=[bad, good],
        src_dir=tmp_path,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=[]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None

    real = libclang_parser.extract_active_comments

    def fake(src_path, args):
        if Path(src_path).name == "bad.cpp":
            raise clang.cindex.TranslationUnitLoadError("forced NULL TU")
        return real(src_path, args)

    monkeypatch.setattr(libclang_parser, "extract_active_comments", fake)

    warnings: list[str] = []

    class _Rec:
        def warning(self, *_a: object, **_k: object) -> None:
            warnings.append("w")

        def info(self, *_a: object, **_k: object) -> None:
            pass

        def debug(self, *_a: object, **_k: object) -> None:
            pass

    monkeypatch.setattr(analyse_module, "logger", _Rec())

    analyse.run()

    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert ids == {"IMPL_GOOD"}, "bad file skipped, good file survives"
    assert warnings, "a NULL translation unit must warn, not skip silently"


def test_libclang_active_matches_treesitter_when_all_active():
    """When every branch is active, libclang output == tree-sitter output."""
    # Tree-sitter path (no preprocessor block) sees ALL markers.
    ts_cfg = SourceAnalyseConfig(
        src_files=[FIXTURE], src_dir=FIXTURE.parent, get_oneline_needs=True
    )
    ts = SourceAnalyse(ts_cfg)
    ts.git_remote_url = None
    ts.git_commit_rev = None
    ts.run()
    ts_ids = {n.need["id"] for n in ts.oneline_needs}

    # libclang with both variants' guards satisfied is impossible (#else is
    # mutually exclusive), so compare the union over both variants instead.
    a = _run_get_oneline_ids(["VARIANT_A=1", "PLATFORM_LINUX=1", "PROTOCOL_VERSION=3"])
    b = _run_get_oneline_ids(["PROTOCOL_VERSION=1"])
    assert ts_ids == (a | b)


def test_libclang_skip_file_absent_from_compile_commands(tmp_path):
    """Files absent from a compile DB are skipped (spec §3.3)."""
    # DB contains only FIXTURE; half_typed.cpp is intentionally absent.
    other = FIXTURE.parent / "half_typed.cpp"
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(FIXTURE.parent),
                    "arguments": [
                        "clang++",
                        "-std=c++17",
                        "-DVARIANT_A=1",
                        "-DPROTOCOL_VERSION=3",
                        "-c",
                        str(FIXTURE),
                    ],
                    "file": str(FIXTURE),
                }
            ]
        )
    )
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE, other],
        src_dir=FIXTURE.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    # FIXTURE is in the DB — its markers must appear.
    assert "IMPL_VAR_A" in ids
    assert "IMPL_PROTO_3" in ids
    # half_typed.cpp is NOT in the DB — it must be skipped entirely.
    assert "IMPL_COMPLETE" not in ids
    assert "IMPL_HALF" not in ids
    assert "IMPL_AFTER" not in ids
    assert "IMPL_MID" not in ids


def test_header_extracted_when_absent_from_compile_commands(tmp_path):
    """A header absent from the DB is parsed standalone, not skipped."""
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(FIXTURE.parent),
                    "arguments": [
                        "clang++",
                        "-std=c++17",
                        "-DVARIANT_A=1",
                        "-c",
                        str(FIXTURE),
                    ],
                    "file": str(FIXTURE),
                }
            ]
        )
    )
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE, HEADER],
        src_dir=FIXTURE.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(compile_commands=db, defines=["VARIANT_A=1"]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    # The .cpp resolves its flags from the DB entry.
    assert "IMPL_VAR_A" in ids
    # The header is absent from the DB -> parsed standalone with global defines.
    assert "IMPL_HDR_ALWAYS" in ids
    assert "IMPL_HDR_VAR_A" in ids  # global defines carry VARIANT_A=1


def _run_header_ids(defines):
    cfg = SourceAnalyseConfig(
        src_files=[HEADER],
        src_dir=HEADER.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=defines),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return {n.need["id"] for n in analyse.oneline_needs}


def test_header_standalone_active_define():
    ids = _run_header_ids(["VARIANT_A=1"])
    assert "IMPL_HDR_ALWAYS" in ids  # include-guard body is active
    assert "IMPL_HDR_VAR_A" in ids  # #ifdef VARIANT_A active


def test_header_standalone_inactive_define():
    ids = _run_header_ids([])
    assert "IMPL_HDR_ALWAYS" in ids  # include-guard body still active
    assert "IMPL_HDR_VAR_A" not in ids  # #ifdef VARIANT_A inactive -> dropped


# Note: extraction-output goldens for this fixture now live in the declarative
# suite (tests/data/extraction/preproc_variants.yaml, both engines). The tests
# above cover libclang-specific behavior the declarative harness does not:
# inactive-branch exclusion via defines/compile_commands, resilience to broken or
# half-typed code, compile-DB resolution, the spec §3.3 skip, and standalone
# header handling.


PLAIN_H = Path(__file__).parent / "data" / "preproc" / "plain_header.h"


def test_libclang_extracts_c_extension_header_via_cpp_language():
    """A ``.h`` header still extracts its oneline markers (not dropped/crashing).

    Headers never appear in compile_commands.json, so they are parsed standalone
    with the global defines. libclang infers C from the ``.h`` extension; without
    pinning the language, ``-std=c++17`` makes clang reject the combo and return
    a NULL translation unit (``TranslationUnitLoadError``) — which previously
    aborted ``sphinx-build -b ubtrace -W``. The standalone flags now pin ``-x``
    to the ``-std`` (see ``defines_to_args``), so the header parses as C++ and its
    markers are extracted rather than lost.
    """
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE, PLAIN_H],
        src_dir=FIXTURE.parent,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_rst=False,
        preprocessor=PreprocessorConfig(
            defines=["VARIANT_A=1", "PLATFORM_LINUX=1", "PROTOCOL_VERSION=3"]
        ),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()  # must not raise TranslationUnitLoadError
    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert "IMPL_ALWAYS" in ids  # the .cpp translation unit extracts
    assert "IMPL_HDR_PLAIN" in ids  # the .h header extracts too (parsed as C++)
