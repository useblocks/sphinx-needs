"""Declarative marker-extraction tests.

Each case in ``tests/data/extraction/*.yaml`` supplies an input (``lang`` +
``config`` + ``source``); the extractor is run on it and the normalized output is
compared to a committed JSON snapshot. See ``tests/data/extraction/README.md``.
"""

import json
from pathlib import Path

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
# for the test. Production writes two independent artefacts, and so does
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
#   - warnings are a separate artefact, matching
#     ``AnalyseProjects.update_warnings()``/``dump_warnings()``: a flat list
#     of ``AnalyseWarning.__dict__`` records (``file_path``, ``lineno``,
#     ``msg``, ``type``, ``sub_type``). Production never folds these into the
#     data stream: ``dump_marked_content`` and ``dump_warnings`` are two
#     independent files, and CLI users are additionally handed the same
#     warnings via ``logger.warning`` (``cmd.py``). See ``_build_warnings``.
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
#      coincidence, and so a second implementation has a language-agnostic
#      value to compare against. It is appended after the real fields, so it
#      never disturbs the real shape.
#
# Nothing else is added, renamed, wrapped, or exploded: no ``content_type``
# rename of ``type``, no flattening of the ``need`` payload, no
# ``{scope_type, scope_text}`` wrapper around ``tagged_scope``, no per-need-id
# explosion of a ``need_ids`` entry, no ``line`` key.
# ---------------------------------------------------------------------------


def _relative_filepath(filepath: Path, root: Path) -> str:
    """Snapshot a filepath relative to the test root (``tmp_path``).

    Production emits an absolute path; ``tmp_path`` is unique per test run and
    per machine, so a plain ``str()`` would make the snapshot non-deterministic.
    Relative-to-root (rather than ``.name``) keeps the value meaningful even if
    a future fixture nests its source file under a subdirectory of ``tmp_path``.
    """
    return filepath.relative_to(root).as_posix()


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
    """Reproduce ``AnalyseProjects.dump_warnings()``'s payload for this case.

    ``update_warnings()`` builds its list the same way: ``__dict__`` of every
    ``AnalyseWarning`` collected during the run. The harness runs a single
    ``SourceAnalyse`` rather than a multi-project ``AnalyseProjects``, so
    ``analyse.oneline_warnings`` is the equivalent source list for one case.
    """
    records = []
    for warning in analyse.oneline_warnings:
        record = dict(warning.__dict__)
        record["file_path"] = _relative_filepath(Path(record["file_path"]), tmp_path)
        records.append(record)
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
        db.write_text(json.dumps(entries), encoding="utf-8")
        compile_commands = db
    elif "compile_commands_raw" in case:
        db = tmp_path / "compile_commands.json"
        db.write_text(case["compile_commands_raw"], encoding="utf-8")
        compile_commands = db
    elif "compile_commands_path" in case:
        compile_commands = tmp_path / case["compile_commands_path"]
    return PreprocessorConfig(
        defines=defines,
        compile_commands=compile_commands,
        std=case.get("std", "c++17"),
    )


@pytest.mark.parametrize("case", _load_cases())
def test_extraction_fixture(case: dict, tmp_path: Path, snapshot_extraction) -> None:
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
        preprocessor = _build_preprocessor(case, tmp_path)

    src_path = tmp_path / f"case.{ext}"
    src_path.write_text(case["source"], encoding="utf-8")

    cfg = SourceAnalyseConfig(
        src_files=[src_path],
        src_dir=tmp_path,
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

    # Two independent snapshots per case, mirroring the two independent files
    # production writes (see the normalization-contract comment above):
    # marked content under the default (unnamed) snapshot, warnings under a
    # separately named one.
    assert snapshot_extraction == _build_marked_content(analyse, tmp_path)
    assert snapshot_extraction(name="warnings") == _build_warnings(analyse, tmp_path)
