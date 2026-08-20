"""Declarative marker-extraction tests.

Each case in ``tests/data/extraction/*.yaml`` supplies an input (``lang`` +
``config`` + ``source``); the extractor is run on it and the normalized output is
compared to a committed JSON snapshot. See ``tests/data/extraction/README.md``.
"""

import json
from pathlib import Path

import pytest
from tree_sitter import Node as TreeSitterNode
import yaml

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.models import Metadata
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


def _list_field_names(style: OneLineCommentStyle) -> set[str]:
    return {f["name"] for f in style.needs_fields if f.get("type") == "list[str]"}


# ---------------------------------------------------------------------------
# Normalization contract
#
# The snapshot mirrors the real per-marker payload the extractor produces
# (``analyse/models.py:Metadata.to_dict`` and its ``OneLineNeed`` /
# ``NeedIdRefs`` / ``MarkedRst`` subclasses), not a reduced projection of it,
# so a regression in ``filepath``, ``remote_url``, ``source_map`` (columns and
# end positions included), the scope text, or the ``MarkedContentType``
# discriminator is caught here. Common ``Metadata`` fields are surfaced on
# every entry (needs, need_refs, marked_rst) as: ``filepath``, ``remote_url``,
# ``source_map``, ``content_type`` (the ``MarkedContentType`` value — named
# ``content_type`` rather than ``type`` because a *need* entry already has a
# ``type`` key for the need's own field, e.g. "impl"), and ``scope``.
#
# ``needs`` keep the existing id/title/type/links/metadata decomposition
# instead of production's raw ``need`` dict: it is the same data either way,
# but the decomposition is what makes the payload comparable against a second
# implementation whose needs are a typed struct rather than a dict.
#
# The pre-existing ``line`` (and, for marked_rst, ``start_line``/``end_line``)
# keys are kept alongside the new full ``source_map`` rather than dropped:
# they duplicate the start row, but a second implementation's comparison
# tooling may already rely on them, and keeping them is free.
#
# Deliberately excluded (the only non-deterministic things here):
#   - the absolute prefix of ``filepath``: pytest's ``tmp_path`` differs per
#     run and per machine, so it is snapshotted relative to ``tmp_path``
#     instead (see ``_relative_filepath``).
#   - the raw ``SourceComment``/tree-sitter node objects: production itself
#     drops ``source_comment`` from ``to_dict()``, and ``tagged_scope`` is
#     captured as its full decoded text (see ``_normalize_scope``), so no
#     information is lost by not embedding the node objects themselves.
#
# ``remote_url`` is *not* excluded: the test body forces
# ``analyse.git_remote_url``/``git_commit_rev`` to ``None`` before ``run()``,
# so it is deterministically ``null`` regardless of the ambient git config of
# the machine running the tests, and is included like any other field.
# ---------------------------------------------------------------------------


def _relative_filepath(filepath: Path, root: Path) -> str:
    """Snapshot ``filepath`` relative to the test root (``tmp_path``).

    Production emits an absolute path; ``tmp_path`` is unique per test run and
    per machine, so a plain ``str()`` would make the snapshot non-deterministic.
    Relative-to-root (rather than ``.name``) keeps the value meaningful even if
    a future fixture nests its source file under a subdirectory of ``tmp_path``.
    """
    return filepath.relative_to(root).as_posix()


def _normalize_scope(node: TreeSitterNode | None) -> dict[str, str] | None:
    """Normalize a ``tagged_scope`` node exactly as production serializes it.

    ``Metadata.to_dict`` stores the associated node's full decoded text
    (``str(node.text.decode("utf-8"))``); this reproduces that verbatim so the
    snapshot can catch a wrong scope being selected, not just a
    differently-typed one. ``scope_type`` (the node's tree-sitter kind) is not
    part of production's output, but it is cheap, deterministic, and makes
    cross-language/cross-implementation comparison easier, so it rides along.
    ``None`` when there is no associated scope, matching production.
    """
    if node is None or not node.text:
        return None
    return {"scope_type": node.type, "scope_text": node.text.decode("utf-8")}


def _normalize_common(entry: Metadata, root: Path) -> dict:
    """The ``Metadata`` fields shared by every marked-content entry."""
    return {
        "filepath": _relative_filepath(entry.filepath, root),
        "remote_url": entry.remote_url,
        "source_map": entry.source_map,
        "content_type": entry.type.value,
        "scope": _normalize_scope(entry.tagged_scope),
    }


def _normalize(
    analyse: SourceAnalyse, style: OneLineCommentStyle, tmp_path: Path
) -> dict:
    core = {"id", "title", "type"}
    list_fields = _list_field_names(style)

    needs = []
    for n in analyse.oneline_needs:
        need = n.need
        links = {name: need[name] for name in list_fields if name in need}
        metadata = {
            k: v for k, v in need.items() if k not in core and k not in list_fields
        }
        needs.append(
            {
                "id": need.get("id", ""),
                "title": need.get("title", ""),
                "type": need.get("type", ""),
                "links": links,
                "metadata": metadata,
                "line": n.source_map["start"]["row"] + 1,
                **_normalize_common(n, tmp_path),
            }
        )
    needs.sort(key=lambda d: (d["line"], d["id"]))

    need_refs = []
    for ref in analyse.need_id_refs:
        line = ref.source_map["start"]["row"] + 1
        common = _normalize_common(ref, tmp_path)
        need_refs.extend(
            {
                "need_id": need_id,
                "line": line,
                "marker": ref.marker,
                **common,
            }
            for need_id in ref.need_ids
        )
    need_refs.sort(key=lambda d: (d["line"], d["need_id"]))

    marked_rst = [
        {
            "content": m.rst,
            "start_line": m.source_map["start"]["row"] + 1,
            "end_line": m.source_map["end"]["row"] + 1,
            **_normalize_common(m, tmp_path),
        }
        for m in analyse.marked_rst
    ]
    marked_rst.sort(key=lambda d: d["start_line"])

    warnings = [
        {"kind": w.sub_type, "line": w.lineno} for w in analyse.oneline_warnings
    ]
    warnings.sort(key=lambda d: (d["line"], d["kind"]))

    return {
        "needs": needs,
        "need_refs": need_refs,
        "marked_rst": marked_rst,
        "warnings": warnings,
    }


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

    assert snapshot_extraction == _normalize(analyse, style, tmp_path)
