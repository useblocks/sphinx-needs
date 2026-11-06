"""A link condition holding brackets travels: authored, written to needs.json, and read
back by ``needimport`` and as external needs, in format 1 and in the draft "2a1".

A condition that ends in ``]`` (``"x" == tags[0]``) is the case the writer spelled but
the reader could not read: the authored need was refused, and an imported one lost the
condition without a word. Each condition here passes on its target, so a build that
reads it back right is a build without a warning.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

BETA = "[needs.beta]"

CONF = """\
project = "{project}"
extensions = ["sphinx_needs"]
exclude_patterns = ["_build"]
needs_json_format_version = {format!r}
needs_json_include_link_conditions = True
"""

#: (as authored, the link it is): each condition passes on its target
LINKS = [
    ('REQ_B["x" == tags[0]]', ("REQ_B", None, '"x" == tags[0]')),
    ('REQ_A.p1[[status in ["open"]]]', ("REQ_A", "p1", 'status in ["open"]')),
    # a condition that starts with `[` and ends with `]`: a space after the brackets
    ('REQ_B[ ["x"] == tags[:1]]', ("REQ_B", None, '["x"] == tags[:1]')),
    # one that starts with `[` and does not end with `]`
    (
        'REQ_B[["x"] == tags[:1] and True]',
        ("REQ_B", None, '["x"] == tags[:1] and True'),
    ),
]

INDEX = """\
Links
=====

.. req:: A
   :id: REQ_A
   :status: open

   With :np:`(p1) a part`.

.. req:: B
   :id: REQ_B
   :tags: x

.. req:: Linking
   :id: REQ_L
   :links: {links}
"""


def _write(srcdir: Path, files: dict[str, str]) -> Path:
    srcdir.mkdir(parents=True)
    for name, text in files.items():
        (srcdir / name).write_text(text, encoding="utf-8")
    return srcdir


def _build(make_app: Any, srcdir: Path) -> tuple[Any, Path]:
    app = make_app("needs", srcdir=srcdir, freshenv=True)
    try:
        app.build()
    finally:
        app.cleanup()
    return app, Path(app.outdir, "needs.json")


def _links(need: Any) -> list[tuple[str, str | None, str | None]]:
    """A need's links, sorted: a need keeps them in an order of its own."""
    return sorted(
        (
            (link.id, link.part, link.condition)
            for link in need.get_links("links", as_str=False)
        ),
        key=_order,
    )


def _order(link: tuple[str, str | None, str | None]) -> tuple[str, str, str]:
    return (link[0], link[1] or "", link[2] or "")


def _prefixed(
    links: list[tuple[str, str | None, str | None]], prefix: str
) -> list[tuple[str, str | None, str | None]]:
    return [(prefix + id_, part, condition) for id_, part, condition in links]


@pytest.mark.parametrize("format_version", [1, "2a1"])
def test_a_condition_with_brackets_survives_needs_json(
    make_app: Any, tmp_path: Path, format_version: int | str
) -> None:
    """``up`` authors the links and writes them; ``down`` reads that file with
    ``needimport`` (ids ``D_``) and as external needs (ids ``X_``). Every link keeps its
    condition, and every condition is evaluated and passes."""
    expected = sorted((link for _, link in LINKS), key=_order)
    index = INDEX.format(links=", ".join(written for written, _ in LINKS))
    up, up_json = _build(
        make_app,
        _write(
            tmp_path / "up",
            {
                "conf.py": CONF.format(project="up", format=format_version),
                "index.rst": index,
            },
        ),
    )
    assert [w for w in build_warnings(up) if BETA not in w] == []
    assert _links(SphinxNeedsData(up.env).get_needs_view()["REQ_L"]) == expected

    down_src = _write(
        tmp_path / "down",
        {
            "conf.py": CONF.format(project="down", format=format_version)
            + "needs_external_needs = [\n"
            '    {"base_url": "http://up.example", "json_path": "up.json", '
            '"id_prefix": "X_"}\n'
            "]\n",
            "index.rst": "Down\n====\n\n.. needimport:: up.json\n   :id_prefix: D_\n",
        },
    )
    shutil.copy(up_json, down_src / "up.json")
    down, down_json = _build(make_app, down_src)
    assert [w for w in build_warnings(down) if BETA not in w] == []

    needs = SphinxNeedsData(down.env).get_needs_view()
    for prefix in ("D_", "X_"):
        need = needs[f"{prefix}REQ_L"]
        assert _links(need) == _prefixed(expected, prefix), prefix
        assert need["has_dead_links"] is False, prefix

    # and ``down`` writes them as ``up`` did, prefixed
    (record,) = (
        r for r in _needs_records(down_json, format_version) if r["id"] == "D_REQ_L"
    )
    (up_record,) = (
        r for r in _needs_records(up_json, format_version) if r["id"] == "REQ_L"
    )
    assert record["links"] == _prefixed_record_links(up_record["links"], "D_")


def _needs_records(path: Path, format_version: int | str) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if format_version == "2a1":
        return data["needs"]
    version = data["current_version"]
    return list(data["versions"][version]["needs"].values())


def _prefixed_record_links(links: Any, prefix: str) -> Any:
    if isinstance(links, dict):  # 2a1: link type -> entries
        return {
            name: _prefixed_record_links(items, prefix) for name, items in links.items()
        }
    return [
        prefix + link if isinstance(link, str) else {**link, "id": prefix + link["id"]}
        for link in links
    ]
