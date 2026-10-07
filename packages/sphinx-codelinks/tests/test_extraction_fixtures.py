"""Declarative marker-extraction tests.

Each case in ``tests/data/extraction/*.yaml`` supplies an input (``lang`` +
``config`` + ``source``); the extractor is run on it and the normalized output is
compared to a committed JSON snapshot. See ``tests/data/extraction/README.md``.
"""

import json
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
import yaml

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.config import (
    NeedIdRefsConfig,
    OneLineCommentStyle,
    PreprocessorConfig,
    SourceAnalyseConfig,
)
from sphinx_codelinks.source_discover.config import CommentType

FIXTURE_DIR = Path(__file__).parent / "data" / "extraction"

# fixture ``lang`` -> (comment type, source-file extension)
LANG_MAP: dict[str, tuple[CommentType, str]] = {
    "cpp": (CommentType.cpp, "cpp"),
    "c": (CommentType.cpp, "c"),
    # A C/C++ header (.h): libclang infers C from the extension, so the engine
    # must pin the language to the -std or -std=c++17 yields a NULL TU.
    "cpp_header": (CommentType.cpp, "h"),
    "python": (CommentType.python, "py"),
    "csharp": (CommentType.cs, "cs"),
    "rust": (CommentType.rust, "rs"),
    "yaml": (CommentType.yaml, "yaml"),
    "go": (CommentType.go, "go"),
    "jsonc": (CommentType.jsonc, "jsonc"),
    "bash": (CommentType.bash, "sh"),
}


def _load_cases() -> list:
    cases = []
    for path in sorted(FIXTURE_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, case in data.items():
            cases.append(pytest.param(case, id=f"{path.stem}-{name}"))
    return cases


def _build_oneline_style(config) -> OneLineCommentStyle:
    if config in (None, "default"):
        return OneLineCommentStyle()
    kwargs = {
        key: config[key]
        for key in ("start_sequence", "end_sequence", "field_split_char")
        if key in config
    }
    if "needs_fields" in config:
        kwargs["needs_fields"] = config["needs_fields"]
    return OneLineCommentStyle(**kwargs)


# ---------------------------------------------------------------------------
# Normalization contract
#
# The snapshots mirror production's real output, not a projection invented
# for the test. Production produces two independent outputs, and so does
# this harness — as two separate snapshot assertions rather than one merged
# object (see the module docstring on ``snapshot_extraction`` usage in the
# test function below for why):
#
#   - marked content is exactly what ``SourceAnalyse.dump_marked_content``
#     writes to ``marked_content.json``: a flat list, taken verbatim from
#     ``analyse.all_marked_content`` (already sorted by ``(filepath,
#     source_map.start.row)`` by ``merge_marked_content``), with each entry's
#     real ``Metadata.to_dict()`` — the nested ``need`` / ``need_ids`` +
#     ``marker`` / ``rst`` payload, ``links`` as a plain list inside ``need``,
#     ``tagged_scope`` as the associated node's full decoded text (or
#     ``null``), and the real ``type`` discriminator value (``"need"`` /
#     ``"need-id-refs"`` / ``"rst"``). See ``_build_marked_content``.
#
#   - warnings are a separate output: a flat list of ``AnalyseWarning.__dict__``
#     records (``file_path``, ``lineno``, ``msg``, ``type``, ``sub_type``),
#     exactly what ``analyse.oneline_warnings`` holds. Production never folds
#     these into the data stream: ``dump_marked_content`` writes only the
#     marked content, and the warnings reach users separately — the
#     ``src-trace`` directive reports each as a ``codelinks.oneline`` build
#     warning, and ``codelinks analyse`` prints them via ``logger.warning``
#     (``cmd.py``). See ``_build_warnings``.
#
# Two deviations from the real thing, both deliberate:
#
#   1. Portability: ``filepath``/``file_path`` are rewritten relative to
#      ``tmp_path`` (see ``_relative_filepath``), since production emits an
#      absolute path that differs per run and per machine.
#   2. Additive: each marked-content entry gets one extra top-level key,
#      ``tagged_scope_type`` — the associated node's tree-sitter kind. This
#      is NOT part of production's output (``Metadata.to_dict()`` never emits
#      it); it rides alongside the real ``tagged_scope`` text so a
#      wrong-scope regression can be told apart from a same-text
#      coincidence, and so the same construct can be compared across
#      languages. It is appended after the real fields, so it
#      never disturbs the real shape.
#
# Nothing else is added, renamed, wrapped, or exploded: no ``content_type``
# rename of ``type``, no flattening of the ``need`` payload, no
# ``{scope_type, scope_text}`` wrapper around ``tagged_scope``, no per-need-id
# explosion of a ``need_ids`` entry, no ``line`` key.
# ---------------------------------------------------------------------------


def _write_exact(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` with exactly the bytes it contains.

    ``Path.write_text`` opens the file in text mode (``newline=None``), which
    makes Python translate every ``\\n`` to ``os.linesep`` on write. On
    Windows that turns an LF-only fixture into CRLF on disk, which shifts
    tree-sitter/libclang column positions at line ends, injects ``\\r`` into
    any multi-line ``tagged_scope`` text, and moves warning positions —
    so the same case would snapshot differently per platform. Writing through ``write_bytes`` bypasses text-mode translation
    entirely, so the file on disk always matches the fixture verbatim,
    independent of platform.
    """
    path.write_bytes(text.encode("utf-8"))


def _assert_portable_path(value: str) -> None:
    """Guard invariant: a snapshot path must be relative and slash-normalized.

    This is the enforced counterpart to ``_relative_filepath``'s
    ``as_posix()`` call — it exists so a future change to that function (or
    to production's path handling) can never silently let a non-portable
    path slip into a snapshot again.

    Checked in an OS-agnostic way: absoluteness is asked of the path types
    themselves rather than guessed from a leading character, because neither
    alone is sufficient — ``PureWindowsPath`` doesn't recognise a POSIX
    ``/abs/path`` as absolute (Windows absoluteness needs a drive), and
    ``PurePosixPath`` doesn't recognise a drive-relative ``C:\\Users\\a`` or a
    UNC ``\\\\server\\share`` as absolute. Testing with both catches every
    form: POSIX-absolute, drive-absolute, and UNC.
    """
    assert not PurePosixPath(value).is_absolute(), f"path must be relative: {value!r}"
    assert not PureWindowsPath(value).is_absolute(), f"path must be relative: {value!r}"
    assert "\\" not in value, (
        f"path must be slash-normalized (no backslashes): {value!r}"
    )


def _relative_filepath(filepath: Path, root: Path) -> str:
    """Snapshot a filepath relative to the test root (``tmp_path``).

    Production emits an absolute path; ``tmp_path`` is unique per test run and
    per machine, so a plain ``str()`` would make the snapshot non-deterministic.
    Relative-to-root (rather than ``.name``) keeps the value meaningful even if
    a future fixture nests its source file under a subdirectory of ``tmp_path``.

    The result is always forward-slash separated (``Path.as_posix()``), even
    on Windows, so a snapshot can never acquire a backslash path separator —
    every existing snapshot uses ``/`` and a mixed separator would make the
    same case snapshot differently per platform. ``_assert_portable_path``
    turns that guarantee into an enforced invariant rather than a remembered
    convention.
    """
    relative = filepath.relative_to(root).as_posix()
    _assert_portable_path(relative)
    return relative


def _build_marked_content(analyse: SourceAnalyse, tmp_path: Path) -> list[dict]:
    """Reproduce ``SourceAnalyse.dump_marked_content``'s payload verbatim.

    Consumes ``analyse.all_marked_content`` — the exact list production dumps,
    already sorted by ``(filepath, source_map.start.row)`` — and calls each
    entry's own ``to_dict()``, so both the shape and the ordering come from
    production itself rather than being re-derived from ``oneline_needs`` /
    ``need_id_refs`` / ``marked_rst`` separately.
    """
    items = []
    for entry in analyse.all_marked_content:
        scope_type = entry.tagged_scope.type if entry.tagged_scope is not None else None
        item = entry.to_dict()
        item["filepath"] = _relative_filepath(entry.filepath, tmp_path)
        # Additive, test-only field — see the module docstring above. Not
        # part of production's Metadata.to_dict().
        item["tagged_scope_type"] = scope_type
        items.append(item)
    return items


def _build_warnings(analyse: SourceAnalyse, tmp_path: Path) -> list[dict]:
    """Reproduce the warnings production reports for this case.

    ``analyse.oneline_warnings`` is the list the ``src-trace`` directive
    reports from and ``codelinks analyse`` prints: each ``AnalyseWarning`` is
    snapshotted as its ``__dict__``, with ``file_path`` made relative to
    ``tmp_path``.

    The one deviation from production: the records are sorted. Production
    reports them in the order the tree-sitter query captures arrive, which
    is not position-sorted and differs between two runs of the same input
    once more than one extractor is on, so no snapshot could pin it.
    """
    records = []
    for warning in analyse.oneline_warnings:
        record = dict(warning.__dict__)
        record["file_path"] = _relative_filepath(Path(record["file_path"]), tmp_path)
        records.append(record)
    records.sort(
        key=lambda r: (r["file_path"], r["lineno"], r["type"], r["sub_type"], r["msg"])
    )
    return records


def _build_preprocessor(case: dict, tmp_path: Path) -> PreprocessorConfig:
    """Build the libclang ``PreprocessorConfig`` for a case.

    ``compile_commands`` (a list of ``{file, arguments}`` entries) is materialized
    into a real ``compile_commands.json`` under ``tmp_path`` so the engine resolves
    per-file flags from it. ``compile_commands_raw`` instead writes a verbatim
    string as the DB (to exercise a present-but-malformed DB).
    ``compile_commands_path`` instead points at an explicit path (which may be
    intentionally absent, to exercise the fallback). Otherwise only the global
    ``defines`` apply.
    """
    defines = case.get("defines", [])
    compile_commands: Path | None = None
    if "compile_commands" in case:
        db = tmp_path / "compile_commands.json"
        entries = [
            {"directory": str(tmp_path), "file": e["file"], "arguments": e["arguments"]}
            for e in case["compile_commands"]
        ]
        _write_exact(db, json.dumps(entries))
        compile_commands = db
    elif "compile_commands_raw" in case:
        db = tmp_path / "compile_commands.json"
        _write_exact(db, case["compile_commands_raw"])
        compile_commands = db
    elif "compile_commands_path" in case:
        compile_commands = tmp_path / case["compile_commands_path"]
    return PreprocessorConfig(
        defines=defines,
        compile_commands=compile_commands,
        std=case.get("std", "c++17"),
    )


# A case's ``source`` is written with LF line endings unless the case sets
# ``line_endings`` to ``crlf`` or ``cr``; every ``\n`` is then replaced by that
# ending before the file is written. Such a case is also run a second time
# with LF endings, and the two outputs must be equal: line endings never change
# what is extracted, or where.
LINE_ENDINGS = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}


def _extract(case: dict, root: Path, source: str) -> tuple[list[dict], list[dict]]:
    """Run one case's ``source`` through ``SourceAnalyse`` under ``root``.

    Returns the normalized (marked content, warnings) pair.
    """
    comment_type, ext = LANG_MAP[case["lang"]]
    config = case.get("config")
    style = _build_oneline_style(config)

    markers = config.get("need_id_markers") if isinstance(config, dict) else None
    refs_config = NeedIdRefsConfig(markers=markers) if markers else NeedIdRefsConfig()

    # Which extractors to run. Defaults to all; a fixture narrows this (e.g. a
    # need-refs case sets ``extract: [need_refs]``) so unrelated markers — like
    # ``@need-ids:`` matching the ``@`` one-line start — don't add noise.
    extract = case.get("extract", ["oneline", "need_refs", "rst"])

    # Engine selection. The default tree-sitter path sees every comment; the
    # libclang path evaluates the preprocessor (``defines``) and excludes markers
    # in inactive #if/#ifdef branches. libclang needs the clang bindings.
    engine = case.get("engine", "treesitter")
    preprocessor = None
    if engine == "libclang":
        pytest.importorskip("clang.cindex")
        preprocessor = _build_preprocessor(case, root)

    src_path = root / f"case.{ext}"
    _write_exact(src_path, source)

    cfg = SourceAnalyseConfig(
        src_files=[src_path],
        src_dir=root,
        comment_type=comment_type,
        get_oneline_needs="oneline" in extract,
        get_need_id_refs="need_refs" in extract,
        get_rst="rst" in extract,
        oneline_comment_style=style,
        need_id_refs_config=refs_config,
        preprocessor=preprocessor,
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return _build_marked_content(analyse, root), _build_warnings(analyse, root)


@pytest.mark.parametrize("case", _load_cases())
def test_extraction_fixture(case: dict, tmp_path: Path, snapshot_extraction) -> None:
    line_endings = case.get("line_endings", "lf")
    source = case["source"].replace("\n", LINE_ENDINGS[line_endings])
    content, warnings = _extract(case, tmp_path, source)

    if line_endings != "lf":
        lf_root = tmp_path / "lf"
        lf_root.mkdir()
        assert (content, warnings) == _extract(case, lf_root, case["source"])

    # Two independent snapshots per case, mirroring the two independent outputs
    # production produces (see the normalization-contract comment above):
    # marked content under the default (unnamed) snapshot, warnings under a
    # separately named one.
    assert snapshot_extraction == content
    assert snapshot_extraction(name="warnings") == warnings
