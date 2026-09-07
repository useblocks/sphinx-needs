"""Tests that need links and backlinks are sorted in needs.json and HTML output.

Regression tests for https://github.com/useblocks/sphinx-needs/issues/1371.
Sorting uses natural ordering so that ``REQ_2`` < ``REQ_9`` < ``REQ_10``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sphinx.testing.util import SphinxTestApp

_LINK_FIELD_TYPES = {"links", "backlinks"}


def _link_field_names(needs_json: dict[str, Any]) -> set[str]:
    """Return the set of fields whose ``field_type`` is a link or backlink.

    Reads from the ``needs_schema`` embedded in the needs.json output.
    Falls back to a small default set if no schema is present.
    """
    versions = needs_json.get("versions", {})
    if not versions:
        return {"links", "links_back", "parent_needs", "parent_needs_back"}
    schema = next(iter(versions.values())).get("needs_schema", {})
    properties = schema.get("properties", {})
    return {
        name
        for name, params in properties.items()
        if params.get("field_type") in _LINK_FIELD_TYPES
    }


def _link_fields_per_need(
    needs_data: dict[str, Any], link_fields: set[str]
) -> dict[str, dict[str, list[str]]]:
    """Extract only the (non-empty) link/backlink fields from each need."""
    result: dict[str, dict[str, list[str]]] = {}
    for need_id, need in needs_data.items():
        per_need = {
            field: need[field] for field in sorted(link_fields) if need.get(field)
        }
        if per_need:
            result[need_id] = per_need
    return result


def _html_link_refs(html: str, need_ids: set[str]) -> dict[str, list[str]]:
    """Extract the rendered link references per source need from HTML.

    The rendered output for each link section uses ``title="<source-need-id>"``
    on the anchor (set by sphinx-needs' role implementations) and the target
    need ID as the link text. This returns a dict mapping each source need to
    the ordered list of targets it links to (or that link to it, for the
    backlinks section). Self-references (a need's own header link) and
    non-need anchors (e.g. section permalinks) are skipped.
    """
    pattern = re.compile(
        r'href="#(?P<target>[^"]+)" title="(?P<source>[^"]+)">'
        r"(?P<text>[^<]+)</a>"
    )
    refs: dict[str, list[str]] = {}
    for m in pattern.finditer(html):
        source = m.group("source")
        target = m.group("target")
        text = m.group("text")
        if source not in need_ids:
            # Not a need's link section (e.g. section heading permalink).
            continue
        if source == target == text:
            # Self-reference (need's own header): skip.
            continue
        refs.setdefault(source, []).append(target)
    return refs


@pytest.mark.fixture_file("fixtures/sort_links.yml")
def test_links_sort(
    tmpdir: Path,
    content: dict[str, Any],
    make_app: Callable[..., SphinxTestApp],
    write_fixture_files: Callable[[Path, dict[str, Any]], None],
    snapshot,
) -> None:
    """Need links and backlinks are sorted in both needs.json and HTML output.

    Sorting uses natural ordering so embedded numbers compare as ints, and is
    unconditional with respect to ``needs_reproducible_json`` — see the
    ``reproducible_json_enabled`` / ``reproducible_json_disabled`` fixtures
    whose link snapshots must be byte-identical.
    """
    write_fixture_files(tmpdir, content)
    app: SphinxTestApp = make_app(srcdir=Path(tmpdir), freshenv=True)
    app.build()
    assert app.statuscode == 0

    needs_json = json.loads(Path(app.outdir, "needs.json").read_text("utf8"))
    versions = needs_json["versions"]
    needs_data = next(iter(versions.values()))["needs"]
    link_fields = _link_field_names(needs_json)
    assert _link_fields_per_need(needs_data, link_fields) == snapshot

    html = Path(app.outdir, "index.html").read_text("utf8")
    assert _html_link_refs(html, set(needs_data)) == snapshot

    app.cleanup()
