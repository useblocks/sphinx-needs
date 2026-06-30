"""Declarative marker-extraction tests.

Each case in ``tests/data/extraction/*.yaml`` supplies an input (``lang`` +
``config`` + ``source``); the extractor is run on it and the normalized output is
compared to a committed JSON snapshot. See ``tests/data/extraction/README.md``.
"""

from pathlib import Path

import pytest
import yaml

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.config import (
    NeedIdRefsConfig,
    OneLineCommentStyle,
    SourceAnalyseConfig,
)
from sphinx_codelinks.source_discover.config import CommentType

FIXTURE_DIR = Path(__file__).parent / "data" / "extraction"

# fixture ``lang`` -> (comment type, source-file extension)
LANG_MAP: dict[str, tuple[CommentType, str]] = {
    "cpp": (CommentType.cpp, "cpp"),
    "c": (CommentType.cpp, "c"),
    "python": (CommentType.python, "py"),
    "csharp": (CommentType.cs, "cs"),
    "rust": (CommentType.rust, "rs"),
    "yaml": (CommentType.yaml, "yaml"),
    "go": (CommentType.go, "go"),
    "jsonc": (CommentType.jsonc, "jsonc"),
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


def _normalize(analyse: SourceAnalyse, style: OneLineCommentStyle) -> dict:
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
            }
        )
    needs.sort(key=lambda d: (d["line"], d["id"]))

    need_refs = []
    for ref in analyse.need_id_refs:
        line = ref.source_map["start"]["row"] + 1
        need_refs.extend({"need_id": need_id, "line": line} for need_id in ref.need_ids)
    need_refs.sort(key=lambda d: (d["line"], d["need_id"]))

    marked_rst = [
        {
            "content": m.rst,
            "start_line": m.source_map["start"]["row"] + 1,
            "end_line": m.source_map["end"]["row"] + 1,
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
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()

    assert snapshot_extraction == _normalize(analyse, style)
